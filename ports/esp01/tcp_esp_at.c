/* BomberNet TCP adapter, ESP-AT passive receive, one connection (CIPMUX=0).
 * No UART buffer clears during a connection. Binary payload is length framed.
 * tcp_recv never waits for a UART byte; open/send/close have bounded waits.
 */
#include <stdint.h>
#include <string.h>
#include "tcp.h"
#include "esp_uart.h"
#define RX_SIZE 1024
#define RX_MASK (RX_SIZE-1)
#define CHUNK 512
#define E_IO 1
#define E_TIMEOUT 2
#define E_PARAM 3
static uint8_t rx[RX_SIZE];
static uint16_t head, tail, remain, deadline, available;
static uint8_t line[96], llen, failed, closed, opened, pending;
static uint8_t busy, result, prompt, discard, ready, awaiting_prompt;
static uint8_t error_code, querying, query_seen;
static uint16_t read_commands;
static uint8_t tx[128];
static uint16_t txlen, txpos;

static uint16_t used(void) { return (uint16_t)(head-tail); }
static uint8_t expired(void) { return (uint16_t)(esp_ticks()-deadline)>=500; }
static void fault(void) { if (!error_code) error_code=4; failed=1; busy=0; txlen=txpos=0; }
static void start(const char *cmd) {
  uint16_t n=(uint16_t)strlen(cmd);
  memcpy(tx,cmd,n); txlen=n; txpos=0;
  busy=1; result=0; prompt=0; awaiting_prompt=0; deadline=esp_ticks();
}
static void finish_line(void) {
  line[llen]=0;
  if (!strcmp((char*)line,"OK") || !strcmp((char*)line,"SEND OK")) {
    if (busy && !awaiting_prompt) {
      result=1; busy=0;
      if (querying && !query_seen) fault();
      querying=0;
    }
  } else if (!strcmp((char*)line,"ERROR") || !strcmp((char*)line,"FAIL") ||
             !strcmp((char*)line,"SEND FAIL") || !strncmp((char*)line,"busy",4)) {
    result=2; busy=0; error_code=1;
  } else if (!strcmp((char*)line,"CLOSED") || !strcmp((char*)line,"WIFI DISCONNECT")) {
    closed=1;
  } else if (!strncmp((char*)line,"+CIPRECVLEN:",12)) {
    uint8_t i=12;
    uint16_t n=0;
    while (line[i]>='0' && line[i]<='9') {
      if (n>6553 || (n==6553 && line[i]>'5')) {fault(); return;}
      n=(uint16_t)((n<<3)+(n<<1)+line[i++]-'0');
    }
    if (i==12 || (line[i] && line[i]!=',')) {fault(); return;}
    available=n; pending=n ? 2 : 0; query_seen=1;
  } else if (!strncmp((char*)line,"+IPD,",5)) {
    pending=1;
  }
  llen=0;
}
static void consume(uint8_t b) {
  if (remain) {
    if (used()>=RX_SIZE) {fault(); return;}
    rx[head++ & RX_MASK]=b; --remain; return;
  }
  if (discard) { if (b=='\n') {discard=0; llen=0;} return; }
  if (b=='>' && !llen) {prompt=1; return;}
  if (b=='\r') return;
  if (b=='\n') {finish_line(); return;}
  /* Old ESP8266: +CIPRECVDATA,<n>:payload.
   * Also accepts newer +CIPRECVDATA:<n>,payload. */
  if (llen>=14 && !memcmp(line,"+CIPRECVDATA",12) &&
      (line[12]==',' || line[12]==':') &&
      ((line[12]==',' && b==':') || (line[12]==':' && b==','))) {
    uint8_t i;
    uint16_t n=0;
    for (i=13;i<llen;i++) {
      if (line[i]<'0' || line[i]>'9') {fault(); return;}
      if(n>CHUNK/10) {fault(); return;}
      n=(uint16_t)((n<<3)+(n<<1)+line[i]-'0');
      if (n>CHUNK) {fault(); return;}
    }
    if (n>(uint16_t)(RX_SIZE-used())) {fault(); return;}
    remain=(uint16_t)n; pending=(n!=0); llen=0; return;
  }
  if (llen==sizeof(line)-1) {discard=1; llen=0; return;}
  line[llen++]=b;
}
static void pump(void) {
  uint8_t b;
  uint16_t budget=2048;
  int8_t r;
  while (budget--) {
    r=esp_uart_read(&b);
    if (r<0) {error_code=5; fault(); return;}
    if (!r) break;
    consume(b);
    if (failed) return;
  }
  /* Limited work per call, no waiting for TX-ready. */
  budget=32;
  while (budget-- && txpos<txlen) {
    if (!esp_uart_write(tx[txpos])) break;
    txpos++;
  }
  if (busy && expired()) {error_code=2; fault();}
}
static uint8_t wait_idle(void) {
  while (busy && !failed) pump();
  return failed ? (error_code==2 ? E_TIMEOUT : E_IO) : result==2 ? E_IO : 0;
}
static uint8_t command(const char *cmd) {
  uint8_t e=wait_idle();
  if (e) return e;
  start(cmd); return wait_idle();
}
static char *put_u(char *p,uint16_t n) {
  char s[5]; uint8_t i=0;
  do {s[i++]=(char)('0'+n%10); n/=10;} while(n);
  while(i) *p++=s[--i];
  *p=0; return p;
}
uint8_t tcp_present(void) {
  if (ready) return 1;
  esp_uart_init(); head=tail=remain=0; llen=failed=closed=opened=pending=busy=discard=0;
  txlen=txpos=0;
  if (command("AT\r\n")) return 0;
  ready=1; return 1;
}
uint8_t tcp_open(const char *host,uint16_t port) {
  char cmd[128], *p;
  const char *h;
  uint8_t e;
  if (!host || !*host || strlen(host)>90 || !port) return E_PARAM;
  for(h=host;*h;h++) if (*h=='"' || *h=='\\' || (uint8_t)*h<32) return E_PARAM;
  if (!tcp_present()) return E_IO;
  tcp_close();
  failed=busy=closed=pending=discard=llen=result=awaiting_prompt=0;
  remain=head=tail=0; txlen=txpos=0; error_code=querying=query_seen=0; available=0; read_commands=0;
  if ((e=command("ATE0\r\n"))!=0) return e;
  /* Wi-Fi credentials are deliberately retained from existing ESP setup. */
  if ((e=command("AT+CIPMUX=0\r\n"))!=0) return e;
  if ((e=command("AT+CIPMODE=0\r\n"))!=0) return e;
  if ((e=command("AT+CIPDINFO=0\r\n"))!=0) return e;
  if ((e=command("AT+CIPRECVMODE=1\r\n"))!=0) return e;
  strcpy(cmd,"AT+CIPSTART=\"TCP\",\"");
  p=cmd+strlen(cmd); while(*host) *p++=*host++;
  *p++='"'; *p++=','; p=put_u(p,port); strcpy(p,"\r\n");
  if ((e=command(cmd))!=0) return e;
  if (closed) return E_IO;
  opened=1; pending=0; return 0;
}
uint8_t tcp_send(const uint8_t *buf,uint16_t n) {
  char cmd[32], *p;
  uint16_t i;
  uint8_t e;
  if (!opened || closed || failed) return E_IO;
  if (!n) return 0;
  if (!buf || n>2048) return E_PARAM;
  if ((e=wait_idle())!=0) return e;
  strcpy(cmd,"AT+CIPSEND="); p=put_u(cmd+11,n); strcpy(p,"\r\n");
  start(cmd); awaiting_prompt=1;
  while (!prompt && busy && !failed) pump();
  if (!prompt || failed || txpos!=txlen) {fault(); return E_IO;}
  deadline=esp_ticks(); result=0; busy=1; awaiting_prompt=0;
  for(i=0;i<n;i++) {
    while (!esp_uart_write(buf[i])) {pump(); if (failed || closed) return E_IO;}
    pump(); if (failed || closed) return E_IO;
  }
  return wait_idle();
}
int16_t tcp_recv(uint8_t *buf,uint16_t max) {
  uint16_t n=0, count;
  char cmd[32], *p;
  if (!buf && max) return -1;
  pump();
  if (failed) return -1;
  while(n<max && used()) buf[n++]=rx[tail++ & RX_MASK];
  if (n) return (int16_t)n;
  if (!opened || (closed && !busy && !remain && !pending)) return -1;
  if (!busy && result==2) {fault(); return -1;}
  if (max && !busy && pending) {
    if (pending==1) {
      querying=1; query_seen=0; start("AT+CIPRECVLEN?\r\n"); pump(); return 0;
    }
    count=available; if(count>CHUNK) count=CHUNK;
    if(count>RX_SIZE-used()) count=RX_SIZE-used();
    strcpy(cmd,"AT+CIPRECVDATA="); p=put_u(cmd+15,count); strcpy(p,"\r\n");
    pending=0; start(cmd); ++read_commands; pump();
  }
  return 0;
}
void tcp_close(void) {
  if (opened && !failed) (void)command("AT+CIPCLOSE\r\n");
  opened=0; closed=1; head=tail=remain=0;
}

uint8_t tcp_error(void) {return error_code;}
uint8_t tcp_peer_closed(void) {return closed;}
uint16_t tcp_read_commands(void) {return read_commands;}
