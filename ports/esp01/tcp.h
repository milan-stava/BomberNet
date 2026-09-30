#ifndef TCP_H
#define TCP_H
#include <stdint.h>
uint8_t tcp_present(void);
uint8_t tcp_open(const char *host, uint16_t port);
uint8_t tcp_send(const uint8_t *buf, uint16_t n);
int16_t tcp_recv(uint8_t *buf, uint16_t max);
void tcp_close(void);
#endif
