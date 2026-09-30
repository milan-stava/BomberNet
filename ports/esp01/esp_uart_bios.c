/* z88dk sccz80 adapter. BIOS is assembled separately with sjasmplus.
 * Preserve IX/IY around BIOS calls; installer changes IXL.
 * No baud change: use the speed already configured in UART and ESP.
 */
#include "esp_uart.h"
uint8_t esp_byte;
static uint8_t read_byte(void) __naked {
  __asm
    push ix
    push iy
    scf
    call esp_bios+16
    ld (_esp_byte),a
    ld hl,255
    jr c,esp_read_done
    ld l,0
    jr z,esp_read_done
    inc l
esp_read_done:
    pop iy
    pop ix
    ret
  __endasm;
}
int8_t esp_uart_read(uint8_t *byte) {
  uint8_t r=read_byte();
  if(r==1) *byte=esp_byte;
  return (int8_t)r;
}
static uint8_t write_byte(void) __naked {
  __asm
    push ix
    push iy
    ld a,(_esp_byte)
    scf
    call esp_bios+18
    ld hl,0
    jr c,esp_write_done
    inc l
esp_write_done:
    pop iy
    pop ix
    ret
  __endasm;
}
uint8_t esp_uart_write(uint8_t byte) {esp_byte=byte; return write_byte();}
void esp_uart_init(void) __naked {
  __asm
    push ix
    push iy
    call esp_bios
    scf
    call esp_bios+4
    pop iy
    pop ix
    ret
  __endasm;
}
uint16_t esp_ticks(void) __naked {
  __asm
    ld hl,(0x5c78)
    ret
esp_bios:
    BINARY "WifiBios20_MB_EL.cod"
  __endasm;
}
