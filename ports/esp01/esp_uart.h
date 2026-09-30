#ifndef ESP_UART_H
#define ESP_UART_H
#include <stdint.h>
/* read: 0 empty, 1 byte, -1 FIFO full/error; write: 1 accepted, 0 busy */
void esp_uart_init(void);
int8_t esp_uart_read(uint8_t *byte);
uint8_t esp_uart_write(uint8_t byte);
uint16_t esp_ticks(void); /* 50 Hz, wraps modulo 65536 */
#endif
