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

## Alpha 2

Continues draining passive receive data after CLOSED while data is pending.
The HTTP test prints status, total/body byte counts, Content-Length validation,
read-command count and a distinct end/error reason instead of long headers.
Error codes: 0 none, 1 ESP AT ERROR/FAIL/busy, 2 command timeout,
4 invalid receive framing or software ring full, 5 UART BIOS receive error.
An AT error after close is reported explicitly; it is not assumed to prove
that all data was received. Hardware verification is still required.
Mock tests cover CLOSED after the first 512 bytes with 88 bytes still buffered,
for both supported receive-header formats.

## Alpha 3: receive end test

Queries `AT+CIPRECVLEN?` before each passive read. The link-0 length is
parsed for both single-length and five-link replies. A zero length on a
closed connection ends cleanly, without a speculative CIPRECVDATA that
could return ERROR. Remaining bytes after CLOSED are still read; real
query/UART/framing errors remain errors. Requires CIPRECVLEN support.

Hardware alpha 2 received a complete 601-byte HTTP response with a 50-byte
body; its third passive read returned AT error. Alpha 3 tests the corrected
end handling. The test should print a complete HTTP response and ERROR CODE 0.

This is still a standalone test. Full-game memory measurement of alpha 2
with the current compiler ended at 69182 (0x10e3e), including BSS, beyond
48K RAM. The Spectranet baseline ended at 64385 (0xfb81). The test backend
must be reduced before shipping a complete game. BSS_END, not BSS_tail, is
the total allocation boundary in the z88dk linker map. Game size work is
postponed until this hardware test passes.
