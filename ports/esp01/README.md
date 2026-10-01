# ESP-01 for MB03+ and eLeMeNt

ESP-01 port for MB03+ and eLeMeNt, based on the UART services documented in
WiFi BIOS 2.0 by Busy and Hood.
The ordinary upstream ZX build keeps Spectranet. This port provides a
separate **128K game alpha 4 (connection recovery and passive receive)**, **48K game alpha 1**,
and the standalone TCP alpha 3 test.

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

## BomberNet ESP-01 128K game alpha 1 (historical BIOS backend)

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


## BomberNet ESP-01 128K game alpha 2 — fast UART bank

Download **`bombernet_esp01_128_alpha2.tap`** from `esp01-game-build` after a
successful Actions run. Load from the beginning in **128K mode with paging
unlocked**, just as alpha 1. Wi-Fi association and UART baud stay as configured.
To compare network speed, use alpha 2 on both participating machines: lockstep
still waits for the slower peer. The 48K alpha 1 is unchanged by this work.

The driver in bank 6 now uses `tcp_esp_fast.c`, Z80 assembly accessing the
same UART ports directly; the full BIOS and C byte/parser layers are no longer
on the game path. Command and payload writes use bounded bursts of at most
32 bytes, respecting TX-busy and draining received notifications between
payload bursts. Passive reads fetch at most 192 bytes, preceded by a length
query. Both ESP response formats, trailing/early CLOSED, UART-full, AT errors
and 10-second operation deadlines remain covered. All scratch remains in bank
6 or the game's fixed staging area; no printer-buffer reuse in this build.
The core uses stronger compiler optimizations; game speed target (60ms/step),
movement rules, BUILD_ID and network protocol remain the same.

Measured immediate-UART CPU cost at 3.5MHz, including bridge/staging/paging:

| Payload | Alpha 1 | Alpha 2 | CPU speedup |
| --- | ---: | ---: | ---: |
| 32 bytes | 43.00ms | 9.05ms | 4.75x |
| 64 bytes | 64.34ms | 11.64ms | 5.53x |
| 128 bytes | 108.83ms | 16.80ms | 6.48x |
| 256 bytes | 195.38ms | 27.00ms | 7.24x |

These are instruction-cycle measurements with simulated UART responses, not
serial baud/ESP processing or server latency. The full-match profiler also
shows lower network handling time, but that includes waiting for an accelerated
emulator's local relay and is not a hardware frame-rate claim. Render/update
routines are recorded separately in `profile.json`; deterministic send costs
and the captured original baseline are in `bench.json` and
`tests/baseline128_bench.json`.

The main image including BSS is 40709 bytes, end 64709 (FCC5h), leaving 826
bytes below SP. The ESP bank including BSS is 2147 bytes, end 51299 (C863h),
leaving 14236 bytes below its own SP. The TAP is 43063 bytes. Loader/bank maps,
binary TCP with fragmented old/new headers, early/final close, TX-backpressure,
errors/timeouts, and a two-instance relay match of 90 steps pass. Hashes at
16/32/48/64/80 agree with no aborts; observed game stack headroom about
493–506 bytes. Real ESP/game speed still awaits user testing of alpha 2.


## 128K alpha 3: reduce network and drawing overhead

Load `bombernet_esp01_128_alpha3.tap` on both peers with 128K paging unlocked.
Wi-Fi association and UART baud requirements are unchanged. The TAP is 43,146
bytes. Game allocation ends at 64781, leaving 754 bytes below the initial
stack; the exercised network match leaves at least 420 bytes of stack headroom.
The 48K build is unchanged.

This version retains the 60 ms simulation step, movement rules and protocol
BUILD_ID. During the existing frame wait it advances network reception. The
banked UART pump reads at most 128 bytes and tolerates four consecutive empty
status probes, avoiding repeated bank calls for short UART gaps. It does not
require hardware flow control.

The main frame compositor copies the 960 playfield cells with unrolled LDI,
then overlays the 40 HUD cells. This is valid after the preceding screen flush
has cleared the drawing buffer. Other callers keep the general compositor.
An emulator comparison checks all 1000 output cells against the compiled
reference with randomized layers and HUD contents.

In the same emulated relay profile, compositor CPU time falls from about
11.9 to 5.24 ms, and network input processing from about 75 to 35 ms. The
interval from composition to the following frame synchronization falls from
100.5 to 57.7 ms; this excludes the screen flush and is not a hardware frame
rate measurement. The deterministic network match retains matching hashes.

The hardware target is to reduce alpha 2's measured 11-second screen crossing
closer to the local game's under-five-second crossing. Measure the same route
with alpha 3: a twofold gameplay speedup is a target, not yet a hardware result.


## 128K alpha 4: reconnect and passive reception

Load `bombernet_esp01_128_alpha4.tap` on both peers. Normal exit now finishes
an outstanding driver transaction, closes TCP and clears error/parser flags.
Opening also attempts to close any connection left by an earlier program.
An absent connection's CIPCLOSE error is discarded before probing AT again.
If AT cannot recover an unknown ESP state, only module power is cycled, using
ROM ticks for timing. Saved ESP Wi-Fi configuration is retained; association
must recover through the module's saved configuration. UART baud is unchanged.

Passive reception uses the available byte count from +IPD and CIPRECVLEN.
It reads known remaining bytes without issuing CIPRECVLEN for each chunk.
After that count is drained it checks once more, since new bytes may have
arrived during reception. The WebSocket RX buffer is 192 bytes in this build.
Simulation pacing, movement rules and the relay protocol remain unchanged.

Hardware feedback shows 20 MHz restores approximately local movement speed
and speeds the other peer too. That is consistent with lockstep waiting on
the slowest device. This build reduces driver command round trips; hardware
measurements at 3.5 MHz are still needed before claiming a specific speedup.
