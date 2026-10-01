/* HTTP diagnostic: count every byte, parse headers across receive blocks. */
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include "tcp.h"
#include "esp_uart.h"
static uint8_t data[512];
static char header[96];
static const uint8_t request[]="GET / HTTP/1.0\r\nHost: api.mzpico.com\r\nConnection: close\r\n\r\n";
int main(void) {
  uint8_t e, in_headers=1, overflow=0, have_length=0, ended=0;
  uint16_t start, i, hl=0;
  int16_t n;
  unsigned long total=0, body=0, expected=0;
  puts("ESP01 MB/EL TCP alpha 2");
  if(!tcp_present()) {printf("AT failed: %u\n",tcp_error()); return 1;}
  puts("AT OK");
  e=tcp_open("api.mzpico.com",80);
  printf("OPEN: %u\n",e); if(e) return 1;
  e=tcp_send(request,sizeof(request)-1);
  printf("SEND: %u\n",e); if(e) {tcp_close(); return 1;}
  start=esp_ticks();
  while((uint16_t)(esp_ticks()-start)<1500) {
    n=tcp_recv(data,sizeof(data));
    if(n<0) {ended=1; break;}
    if(n) {
      total+=(uint16_t)n; start=esp_ticks();
      for(i=0;i<(uint16_t)n;i++) {
        uint8_t b=data[i];
        if(!in_headers) {++body; continue;}
        if(b=='\r') continue;
        if(b=='\n') {
          header[hl]=0;
          if(!hl && !overflow) {in_headers=0; puts("HEADERS complete");}
          else if(!overflow) {
            if(!strncmp(header,"HTTP/",5)) puts(header);
            if(!strncmp(header,"Content-Length:",15)) {
              expected=strtoul(header+15,0,10); have_length=1;
              printf("CONTENT LENGTH: %lu\n",expected);
            }
          }
          hl=0; overflow=0;
        } else if(hl<sizeof(header)-1) header[hl++]=(char)b;
        else overflow=1;
      }
    }
  }
  printf("END: %s\n",!ended ? "test timeout" : tcp_error() ? "driver error" : tcp_peer_closed() ? "peer closed" : "connection ended");
  printf("ERROR CODE: %u\nREAD COMMANDS: %u\n",tcp_error(),tcp_read_commands());
  printf("RECEIVED: %lu bytes\nBODY: %lu bytes\n",total,body);
  if(in_headers) puts("RESULT: incomplete headers");
  else if(have_length) puts(body==expected ? "RESULT: complete HTTP response" : "RESULT: body length mismatch");
  else puts("RESULT: no Content-Length to verify");
  tcp_close(); return 0;
}
