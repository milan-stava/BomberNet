/* Game-side TCP bridge, linked FIRST so this entire file stays below C000.
 * Caller pointers and its stack may be in bank 0. Stage bytes in the unused
 * fixed-RAM staging area, then call bank 6 on its own stack.
 * No game function/library is called while bank 6 is mapped.
 */
#include <stdint.h>
#include <string.h>
#include "tcp.h"
#include "bank_entries.h"
extern uint8_t esp_stage[];
#define STAGE esp_stage
static uint16_t bank_call(uint16_t entry,uint16_t p1,uint16_t p2) __naked {
  __asm
    pop af
    pop de
    pop hl
    pop bc
    push bc
    push hl
    push de
    push af
    ld (eb_arg1),hl
    ld (eb_arg2),de
    ld (eb_target),bc
    push ix
    push iy
    ld (eb_sp),sp
    ld a,(0x5b5c)
    bit 5,a
    jr nz,eb_locked
    ld (eb_page),a
    and 0xf8
    or 6
    di
    ld bc,0x7ffd
    out (c),a
    ld (0x5b5c),a
    ld sp,65535
    ld hl,(eb_arg1)
    push hl
    ld hl,(eb_arg2)
    push hl
    ld hl,eb_return
    push hl
    ld hl,(eb_target)
    ei
    jp (hl)
eb_return:
    di
    ld a,(eb_page)
    ld bc,0x7ffd
    out (c),a
    ld (0x5b5c),a
    ld sp,(eb_sp)
    ei
    pop iy
    pop ix
    ret
eb_locked:
    ld hl,65535
    pop iy
    pop ix
    ret
; Fixed RAM state for page changes.
eb_arg1: defw 0
eb_arg2: defw 0
eb_target: defw 0
eb_sp: defw 0
eb_page: defb 0
  __endasm;
}
static uint8_t initialized(uint8_t mark) __z88dk_fastcall __naked {
  __asm
    ld a,(eb_init)
    ld e,a
    ld a,l
    ld (eb_init),a
    ld l,e
    ld h,0
    ret
eb_init: defb 0
    PUBLIC _esp_stage
defc _esp_stage = 23808
  __endasm;
}
uint8_t tcp_present(void) {
  if(!initialized(1) && bank_call(ESP_RESET,0,0)) {initialized(0); return 0;}
  return bank_call(ESP_PRESENT,0,0)==1;
}
uint8_t tcp_open(const char *host,uint16_t port) {
  uint16_t n;
  if(!host || !port) return 3;
  n=(uint16_t)strlen(host);
  if(!n || n>90) return 3;
  if(!tcp_present()) return 1;
  memcpy(STAGE,host,n+1);
  return (uint8_t)bank_call(ESP_OPEN,(uint16_t)STAGE,port);
}
uint8_t tcp_send(const uint8_t *buf,uint16_t n) {
  uint16_t part;
  uint8_t e;
  if(!buf && n) return 3;
  do {
    part=n>192 ? 192 : n;
    if(part) memcpy(STAGE,buf,part);
    e=(uint8_t)bank_call(ESP_SEND,(uint16_t)STAGE,part);
    if(e) return e;
    if(part) buf+=part;
    n-=part;
  } while(n);
  return 0;
}
int16_t tcp_recv(uint8_t *buf,uint16_t max) {
  int16_t n;
  if(!buf && max) return -1;
  if(max>192) max=192;
  n=(int16_t)bank_call(ESP_RECV,(uint16_t)STAGE,max);
  if(n>0) memcpy(buf,STAGE,(uint16_t)n);
  return n;
}
void tcp_close(void) {bank_call(ESP_CLOSE,0,0);}
uint8_t tcp_error(void) {return (uint8_t)bank_call(ESP_ERROR,0,0);}
uint8_t tcp_peer_closed(void) {return (uint8_t)bank_call(ESP_CLOSED,0,0);}
uint16_t tcp_read_commands(void) {return bank_call(ESP_READS,0,0);}
