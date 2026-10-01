#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "tcp.h"
#include "esp_uart.h"
static uint8_t wire[8192], sent[4096], payload[600];
static unsigned wh,wt, send_left, sent_n, payload_pos, calls, ticks;
static char cmd[256];
static unsigned cp;
static int no_response, modern, fifo_error, early_close;
static void enqueue(const void *s,unsigned n) {assert(wh+n<sizeof(wire)); memcpy(wire+wh,s,n);wh+=n;}
static void text(const char *s) {enqueue(s,(unsigned)strlen(s));}
void esp_uart_init(void) {}
uint16_t esp_ticks(void) {return (uint16_t)(ticks/100);}
int8_t esp_uart_read(uint8_t *b) {
  ticks++;
  if(fifo_error) return -1;
  /* Explicit gaps split every header and payload across pump calls. */
  if(++calls%3==0 || wt==wh) return 0;
  *b=wire[wt++];return 1;
}
uint8_t esp_uart_write(uint8_t b) {
  if(send_left) {
    sent[sent_n++]=b;
    if(!--send_left) text("\r\nSEND OK\r\n+IPD,600\r\n");
    return 1;
  }
  assert(cp+1<sizeof(cmd));cmd[cp++]=(char)b;
  if(b=='\n') {
    unsigned n;
    char header[64];cmd[cp]=0;cp=0;
    if(no_response) return 1;
    if(sscanf(cmd,"AT+CIPSEND=%u",&n)==1) {
      send_left=n;text("\r\nOK\r\n>");
    } else if(!strcmp(cmd,"AT+CIPRECVLEN?\r\n")) {
      snprintf(header,sizeof(header),"\r\n+CIPRECVLEN:%u,0,0,0,0\r\nOK\r\n",(unsigned)sizeof(payload)-payload_pos);
      text(header);
    } else if(sscanf(cmd,"AT+CIPRECVDATA=%u",&n)==1) {
      unsigned rest=sizeof(payload)-payload_pos;
      if(n>rest)n=rest;
      snprintf(header,sizeof(header),modern?"\r\n+CIPRECVDATA:%u,":"\r\n+CIPRECVDATA,%u:",n);
      text(header);enqueue(payload+payload_pos,n);payload_pos+=n;
      text("\r\nOK\r\n");
      if(early_close && payload_pos==512) text("\r\nCLOSED\r\n");
    } else if(strstr(cmd,"CIPSTART")) text("\r\nCONNECT\r\nOK\r\n");
    else text("\r\nOK\r\n");
  }
  return 1;
}
static void roundtrip(int format) {
  uint8_t output[600], message[]={0,1,'>',13,10,255};
  unsigned total=0,loops=0;
  int16_t n;
  modern=format;payload_pos=sent_n=0;
  assert(tcp_open("api.mzpico.com",80)==0);
  assert(tcp_send(message,sizeof(message))==0);
  assert(sent_n==sizeof(message) && !memcmp(sent,message,sizeof(message)));
  while(total<sizeof(output) && loops++<10000) {
    n=tcp_recv(output+total,17);
    assert(n>=0);total+=(unsigned)n;
  }
  assert(total==sizeof(output) && !memcmp(output,payload,sizeof(output)));
  /* Read to a zero-length reply; then a peer close must be reported. */
  if(!early_close) for(loops=0;loops<1000;loops++) assert(tcp_recv(output,17)>=0);
  text("\r\nCLOSED\r\n");
  for(loops=0;loops<1000;loops++) if(tcp_recv(output,17)<0)break;
  assert(loops<1000);
  tcp_close();
}
int main(void) {
  unsigned i;
  uint8_t b;
  for(i=0;i<sizeof(payload);i++)payload[i]=(uint8_t)i;
  memcpy(payload+30,"\r\nCLOSED\r\nOK\r\n>",16);
  assert(tcp_present());
  assert(tcp_open("bad\"host",80)==3);
  roundtrip(0);roundtrip(1);
  early_close=1;roundtrip(0);roundtrip(1);early_close=0;
  assert(tcp_open("api.mzpico.com",80)==0);
  fifo_error=1;assert(tcp_recv(&b,1)==-1);fifo_error=0;tcp_close();
  no_response=1;assert(tcp_open("api.mzpico.com",80)!=0);
  puts("PASS: binary send/receive, fragmented old/new headers, 512-byte chunks,");
  puts("small caller buffers, zero receive, CLOSED, early CLOSED with unread data, FIFO error and timeout.");
  return 0;
}
