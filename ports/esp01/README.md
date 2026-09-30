# ESP-01 for MB03+ and eLeMeNt

Initial TCP driver for BomberNet, using WiFi BIOS 2.0 by Busy and Hood.
The original game build continues to use Spectranet. This directory contains
a standalone TCP test; game integration follows hardware validation.

## Download without installing a compiler

On branch `esp01-mb-el`, open **Actions → ESP01 MB03+ and eLeMeNt**.
After a successful build, download the `esp01-tcp-test` artifact and extract
`esp01_tcp_test.tap`. A green build verifies compilation and simulated UART
tests, not real ESP hardware or gameplay.

## Hardware test

ESP must already be associated with Wi-Fi, and UART baud must match ESP baud.
Close previous TCP connections before running the test. The adapter preserves
baud and credentials. Load the TAP normally. Expected output: AT OK, OPEN: 0,
SEND: 0, an HTTP response from api.mzpico.com:80, and received byte count.
Record the output on error. The test reports either peer close or driver
error as END, consistent with BomberNet's shared -1 return value.

## Driver

Single connection, CIPMUX=0, passive receive. Requests up to 512 bytes into a
1024-byte software ring; binary data is length framed. tcp_recv does not wait
for UART bytes. Open/send/close use bounded waits based on 50Hz ROM FRAMES;
interrupts must run. No UART FIFO clears during an active connection.

The BIOS adapter preserves IX and IY. FIFO full is treated conservatively as
an error. UART RTS/CTS is not required for this design, but actual AT timing,
notifications, baud rate, and close-with-unread-data behavior need hardware
validation. Upstream WebSocket and game synchronization are retained for
the subsequent integration.

## Validation

Host tests cover binary data, fragmented old/new CIPRECVDATA headers,
512-byte chunks, small caller buffers, empty reads, CLOSED, FIFO error and
timeout. Z80 build and actual hardware testing are tracked through Actions
and user testing. Do not treat this source-only initial port as a game release.
