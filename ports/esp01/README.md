# ESP-01 for MB03+ and eLeMeNt

ESP-01 port for MB03+ and eLeMeNt, using WiFi BIOS 2.0 by Busy and Hood.
The ordinary upstream ZX build keeps Spectranet. This port provides a
separate **128K game alpha 1** plus the standalone TCP alpha 3 test.

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
end handling. Hardware alpha 3 passed: 611 total bytes, 50 body bytes, two data reads,
ERROR CODE 0 and peer closed.

This is still a standalone test. Full-game memory measurement of alpha 2
with the current compiler ended at 69182 (0x10e3e), including BSS, beyond
48K RAM. The Spectranet baseline ended at 64385 (0xfb81). The test backend
must be reduced before shipping a complete game. BSS_END, not BSS_tail, is
the total allocation boundary in the z88dk linker map. The 128K game below solves this by paging the verified driver separately.

## BomberNet ESP-01 128K game alpha 1

Download `bombernet_esp01_128_alpha1.tap` from the `esp01-game-build` Actions
artifact. This is the complete game, with the upstream WebSocket/relay and
simulation unchanged (build id 0x0604). The standalone `esp01-tcp-test`
artifact remains available separately.

### Run on MB03+ / eLeMeNt

- Enable the ordinary **128K Spectrum paging mode** (port 7FFD must remain
  unlocked). A locked 48K mode cannot load this version.
- ESP must already be connected to Wi-Fi. Retain the working UART baud
  from the alpha 3 test; no credentials or baud changes are made.
- Load the TAP from its beginning. BASIC loads a bootstrap at 8000h, which
  relocates its short loader below the game at 5D00h. It switches to 48K ROM,
  verifies that banks 0 and 6 are distinct, loads the ESP bank, then the game.
- A persistent red border means the bank probe or tape block load failed.
  Reset before retrying in 128K mode. The loader does not return to BASIC.
- The title must offer NETWORK. Use QAOP and SPACE, select HOST, two total
  players and one local player; create a room and report its four-letter code.
  JOIN uses the original game's room-code input. A second compatible client
  is needed to start a network match.

### Memory and bank safety

Game origin 24000 (5DC0h), allocation end 64807 (FD27h), including all BSS;
728 bytes remain below SP=FFFFh. The verified driver occupies bank 6 from
C000h through D7A3h: 6052 allocated bytes and 10331 bytes below its own SP.
A 512-byte stack reserve is enforced independently for both images.

The bridge and its 256-byte staging area are linked first, below C000h.
It copies host names/send bytes before paging, reads received bytes back
only after restoring bank 0, and switches stacks with interrupts disabled
for the paging sequence. ROM interrupts run normally inside the driver.
IX/IY and BANKM at 5B5Ch are preserved/restored. No game/library routine runs
from the paged game bank while the ESP bank is selected.

The 256-byte printer buffer at 23296 (5B00h) is **not used** as staging.
On 128K it contains paging routines and BANKM at 23388; overwriting all of
it would corrupt the bank state. Reuse for a future unbanked 48K version
requires a separate audit of ROM/peripheral use.

### Validation and remaining hardware test

- GCC driver tests with address/undefined-behavior sanitizers pass.
- Both Z80 images compile and pass the allocation checks; all bridge entry
  points and shared bytes are checked to be below C000h.
- Compiled Z80 code runs with native 128K paging in `zx` 0.13.15 and a
  simulated UART: binary data, fragmented replies, bank-0 caller pointers,
  caller stack restoration and clean peer close pass.
- The loader's bank probe and exact raw tape addresses/lengths pass with a
  simulated ROM tape read. TAP block checksums are verified. Real tape/SD
  loading still needs hardware confirmation.
- The real upstream local relay accepts the compiled game's WebSocket
  handshake, room creation and leave. Two emulated games then run 60 steps,
  comparing state hashes at frames 16, 32 and 48: no mismatches/aborts.
  Stack watermark leaves roughly 395-403 bytes between game BSS and the
  deepest observed stack use. This is a tested scenario, not a proof of
  every stack path or real UART/game timing.
- The user confirmed that the 128K alpha starts successfully on real hardware.

### Rebuild

The Actions workflow assembles the supplied BIOS, links the ESP image,
exports its entry addresses, links the fixed game-side bridge first, packs
BASIC/loader/two images, and runs the emulator/relay tests. Local equivalents
are `build_game128.sh`, `bank_layout.py`, `link_game128.sh`, `pack_game128.py`
and `loader128.a80`. Use the same z88dk container and sjasmplus 1.20.3 as the
workflow; run the Python steps on the host outside the compiler container.


## BomberNet ESP-01 48K game alpha 1

`bombernet_esp01_48_alpha1.tap` is an unbanked game, built with the compact
Z80 ESP-AT backend. Select **48K mode / 48K BASIC** before loading it from
the beginning. Keep ESP baud and Wi-Fi setup as used for the 128K version.
The compact version uses the documented UART ports directly, with just the
required BIOS power-enable operation. It retains passive receive, checks
receive lengths before fetching, and reads at most 64 payload bytes per command.
No baud changes, RX clears during a connection, or hardware flow control.

The main image occupies 24000 (5DC0h) through 65016 (FDF8h), including BSS.
Allocation end 65017 leaves **518 bytes** below SP=65535. Fixed scratch also
uses 254 bytes of the printer buffer (5B00h..5BFDh) and the renderer's 256-byte
cache at 23744 (5CC0h)..23999 (5DBFh), after the ROM system variables and
before the game. The first flush clears the relocated cache. HOST/JOIN share
one synchronous path buffer. Game rules, player counts, relay protocol and
BUILD_ID are unchanged. The fixed areas overwrite BASIC workspace after
startup, so reset to return to BASIC. The 128K build keeps its own RAM layout.

**Do not launch this TAP while the 128K ROM paging services are active:**
its printer scratch overwrites their routines and BANKM. Use the 128K TAP
for that configuration instead.

Validation of the compiled 48K image:
- Binary stream with split UART responses, both receive-header formats,
  early CLOSED with data still pending, and clean final close.
- FIFO-full detection, 10-second timeout, AT error and missing receive length.
- TAP block checksums and CODE image, fixed-area bounds and 512-byte stack guard.
- Real upstream local relay: WebSocket upgrade, HOST/JOIN, ready and a two-player
  60-step network match. Hashes at frames 16/32/48 agree; no aborts. Stack
  watermark leaves 191/198 bytes above the allocated image in this test.

The 48K TAP awaits hardware testing. The 518-byte total stack allowance is
small; the observed watermark covers the tested two-player scenario, not every
possible game state. Start with NETWORK -> HOST, two players / one local,
then JOIN from a second instance as with the 128K version.
