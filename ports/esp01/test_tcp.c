/* A plain HTTP request exercises DNS, TCP, binary-safe passive receive and
 * peer close. Run with Wi-Fi already connected and UART baud matching ESP.
 */
#include <stdio.h>
#include "tcp.h"
#include "esp_uart.h"
static uint8_t data[512];
static const uint8_t request[]="GET / HTTP/1.0\r\nHost: api.mzpico.com\r\nConnection: close\r\n\r\n";
int main(void) {
  uint8_t e;
  int16_t n;
  uint16_t total=0, start;
  puts("ESP01 MB/EL TCP alpha 1");
  if(!tcp_present()) {puts("AT failed. Check power/baud."); return 1;}
  puts("AT OK");
  e=tcp_open("api.mzpico.com",80);
  printf("OPEN: %u\n",e); if(e) return 1;
  e=tcp_send(request,sizeof(request)-1);
  printf("SEND: %u\n",e); if(e) {tcp_close(); return 1;}
  start=esp_ticks();
  while((uint16_t)(esp_ticks()-start)<1500) {
    n=tcp_recv(data,sizeof(data));
    if(n<0) {puts("END: closed or driver error"); break;}
    if(n) {
      /* Print only the first block, to keep the receive loop responsive. */
      if(!total) {uint16_t i; for(i=0;i<(uint16_t)n;i++) putchar(data[i]);}
      total+=(uint16_t)n; start=esp_ticks();
    }
  }
  printf("\nRECEIVED: %u bytes\n",total);
  tcp_close(); return 0;
}
