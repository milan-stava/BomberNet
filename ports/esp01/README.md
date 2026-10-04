# ESP-01 for MB03+ and eLeMeNt

ESP-01 port for MB03+ and eLeMeNt, based on the UART services documented in
WiFi BIOS 2.0 by Busy and Hood.
The ordinary upstream ZX build keeps Spectranet. This port provides a
separate **128K game alpha 7 (faster UART, frame work and lower footstep)**, **48K game alpha 1**,
and the standalone TCP alpha 3 test.

## Download without installing a compiler

On branch `esp01-mb-el`, open **Actions → ESP01 MB03+ and eLeMeNt**.
For the complete 128K game, download `esp01-game-build` and extract
`bombernet_esp01_128_alpha7.tap`. The separate `esp01-tcp-test` artifact
contains the standalone `esp01_tcp_test.tap`. A green build verifies compilation and simulated UART
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


Once a send's payload has been written to UART, alpha 4 returns to the game
while SEND OK is still pending. The next send waits for that completion before
starting another command, and receive/close continue the parser. Late SEND FAIL
is reported as a lost connection. A delayed-ACK emulator test runs real game
computation between payload transmission and ACK release. This overlaps ESP
completion latency with game computation without predicting player input.


The receive command is now started within the same bank call, with two bounded
pump passes to consume an already available response. The frequent lockstep
availability scan is implemented in Z80 assembly and compared with a reference
across ring/wrap boundaries. Final alpha 4 TAP size: 43,385 bytes; game BSS ends
at 64847 (FD4F), leaving 688 bytes below the initial stack. The 90-step CI match
leaves at least 354 bytes unused above game allocation.

Simulated recovery, reopen, unknown-state power recovery, delayed ACK, late
SEND FAIL, and data arriving after a passive notification count all pass.
Two-player and four-player relay matches retain matching state hashes.
Send call time in one emulated relay profile is about 9.8 ms versus alpha 3's
20.7 ms, but this includes ESP/relay waiting. Full-match timing varies with
host scheduling and does not establish a twofold hardware movement speedup.
Test repeat HOST/JOIN after leaving a match and the same screen crossing at
3.5 MHz on both peers; saved Wi-Fi association is required after power recovery.


## 128K alpha 6: direct UART transport and nonblocking sound

Load `bombernet_esp01_128_alpha6.tap` on both peers, initially at 3.5 MHz.
The active WebSocket connection uses CIPRECVMODE=0, CIPMODE=1 and a single
CIPSEND to enter transparent TCP. There are no per-packet AT send/read commands.
A 4096-byte ring in bank 6 supplements the hardware's 2048-byte RX FIFO.
UART TX busy and RX overflow are checked; no hardware flow control is required
for the tested game traffic. Hardware testing remains necessary.

Leaving uses guarded +++ to return to command mode, then closes TCP. Initial
recovery first tries a guarded escape from an inherited transparent session,
preserving a volatile Wi-Fi association. If AT still fails, module power is
cycled. Hardware FIFO reset and CIPCLOSE=5 remove stale FIFO data and old
multiplexed sockets. Saved Wi-Fi settings and UART baud are unchanged.
WebSocket close/invalid framing and a ten-second frame-wait deadline handle
disconnection; the raw transport does not promise generic TCP EOF detection.

Footsteps and other network sounds now use nonblocking AY tones. One tone call
takes about 0.27 ms instead of 14.48 ms of blocking beeper code at 3.5 MHz.
Local play retains its original sound. The lobby clears queued messages on
leave/new room, keeps only one link-measurement ping outstanding, and permits
READY when no remote participant needs measurement. Re-HOST, peer ping/pong
and starting the next match are tested together.

The bank bridge reuses 192 bytes of completed loader RAM at 23808 (5D00),
ending immediately before the game at 24000. It does not use the printer
buffer. The game allocation ends at 64895 (FD7F); relay tests leave at least
306 bytes of stack headroom. Alpha 5 remains a passive-transport fallback.

A continuous walking corridor, installed before either peer's first simulation
step, compares alpha 4 and alpha 6. The measured work interval falls from
about 72.5 to 40.6 ms; screen flushing adds about 18 ms. This is an emulator
comparison including relay waiting, not a hardware movement-speed promise.
Two- and four-player matches keep matching state hashes. Tests cover 10 KB
ring wrap, TX busy/timeout, inherited raw-session recovery, close/reopen and
repeat HOST. Simulation pacing and movement rules remain unchanged.

Deathmatch keeps a killed player off screen until the next round. The stage
reset test verifies that a dead player becomes visible again in that round;
the reported intermittent disappearance has not otherwise been reproduced.

The delivered TAP is 51,966 bytes. It uses the successful CI run 36942743981
images plus a locally assembled 114-byte recovery function from the current
source, with existing bank entry addresses preserved. The exact reproducible
link is `tests/link_recovery_overlay128.py`; the ordinary source build includes
the same recovery directly. The final TAP is retested for loader, raw UART
recovery, WebSocket close, relay re-HOST and continuous walking.


## 128K alpha 7: faster UART and frame work

Load `bombernet_esp01_128_alpha7.tap` on both peers at 3.5 MHz. Hardware alpha 6
feedback: approximately six seconds across the screen, already playable.
Alpha 7 keeps the same transparent TCP setup/recovery and 60 ms simulation
pacing; its hardware crossing time remains to be measured.

The game-side send/receive bridge uses compact assembly and LDIR, retaining
bank-0 caller-pointer safety, 192-byte chunks and complete stack restoration.
Raw TX retains pointer and remaining length in registers inside each bounded
32-attempt burst. RX retains ring head/count in registers while pumping. TX
busy, RX overflow, ring-full and ten-second deadlines remain checked. The
4096-byte ring now starts at the page-aligned address in allocated padding: a
new full-ring test verifies that all 4096 bytes survive before any are drained.

During a network playfield flush only the 40 HUD cells are cleared; the next
fast compositor replaces all 960 playfield cells. Title/local paths retain full
clearing. Pixel and shadow comparisons against alpha 6 pass. This saves about
1.73 ms per flush. The common 16-frame map hash uses the exact original 25-row
slices from a table; other periods and hash-boundary frames retain the general
routine. Hash comparisons cover periods 1/2/7/16/32 and frame-number wrap.
A regular slice falls from about 3.52 to 2.14 ms. The higher footstep (020Ah)
uses AY period 81 instead of 65, lowering its frequency by about 20%; the
other tested pitches are unchanged and sound remains nonblocking.

In continuous walking, work between composition and frame synchronization
is about 35 ms versus alpha 6's 41 ms, excluding the screen flush (now about
16 ms versus 18 ms). Relay waits are included: this is an emulator comparison,
not a promise of a four-second hardware crossing. Two- and four-player games
and repeat HOST/READY pass without hash mismatches.

The delivered TAP is 52,186 bytes: bank image 11,039, game image 40,940 and
loader 100. Game allocation ends at 64940 (FDAC). The reproducible compatibility
link is `tests/link_speed_overlay128.py`, starting from the delivered alpha 6
images (CI run 36942743981 plus `link_recovery_overlay128.py`). It uses bridge
space freed by assembly and appends only the 45-byte hash table to the game.
Normal z88dk source builds include the changes directly. The 48K build is
unchanged. Gameplay rules, BUILD_ID and relay protocol are unchanged.


## 128K alpha 8: match reset and beeper-calibrated AY

Load `bombernet_esp01_128_alpha8.tap` on both peers. Match seeding now clears
inactive hit coordinates, which are part of the state hash. Previously an
offline match could leave different coordinates on the two machines and
cause DESYNC immediately on the next network match. Reset is at new match
seeding only; active coordinates are preserved between stages. Coop death
and respawn rules, 60 ms pacing and relay protocol remain unchanged.

AY pitch is calibrated against measured original beeper edges at 3.5 MHz;
seven representative ratios are within 2.5%. Footsteps use a one-shot decay
envelope lasting approximately 13.86 ms instead of sustaining until the next
network frame. The CPU returns in about 0.35 ms, without waiting for sound.
AY timbre still differs from beeper. Frame sync only mutes when leaving network
play; the envelope stops each network tone automatically.

RX copies use LDIR with an exact split at the 4096-byte ring boundary, retaining
192-byte staging, flow checks and deadlines. UART overflow, full-ring, wrap,
reconnect, loader, pixel/hash equivalence, two- and four-player native Z80
relay tests pass. Both network tests inject differing previous hit histories;
state hashes agree during movement. Hardware speed improvement remains to
be measured; emulator wall time is not a hardware crossing-time measurement.

Delivered TAP: 52,381 bytes; game 41,016, bank 11,158, loader 100 bytes.
Game allocation ends FDF8, leaving 519 bytes below FFFF. Tested stack watermark
leaves at least 185 bytes above allocation in these two/four-player scenarios.
The compatibility link `tests/link_alpha8_overlay128.py` requires the exact
alpha 7 image checksums, assembles current routines with SjASMPlus, and retains
existing entry addresses. Normal source builds include these changes directly.
This delivery is locally assembled and tested; no new GitHub Actions run is
claimed. Regression checks: `tests/test_alpha8_128.py`, and
`ESP_HISTORY=1 ESP_WALK=1 python ports/esp01/tests/test_relay128.py`.


## 128K alpha 14: label-only purple HUD and faster player drawing

Download `runable/14Bomberman.tap`. BASIC tape name begins `14Bomberma`
(the Spectrum header has ten characters). The purple status bar now colors
only P1/P2, or the compact player digits in three/four-player games. Scores,
lives, time and stage use black ink. Single-player text remains black.

Player rendering, the player loop, 2x2 tile writes and frame-timer updates
use native Z80 routines. A fast check skips the C death-color pass when no
visible player is dying. They preserve collision, death and scoring order.
On the deterministic two-local-player CPU benchmark, excluding frame pacing,
mean frame work falls from 40.019 ms to 38.247 ms at 3.5 MHz. This is CPU work,
not a measured hardware screen-crossing time; 60 ms gameplay pacing is retained.
AY audio and the shared input delay are unchanged.

Compatibility tests now run against the *unmodified published upstream ZX
binary*, using emulated Spectranet versus the banked ESP UART. HOST/JOIN both
pass; asymmetric cycle-timed network delivery with UART serialization,
seven-byte Spectranet reads and 0..39 ms jitter also passes. Runs at 120 ms
one-way base delay in both roles and 300 ms in the ESP-host role have matching
state hashes and no abort. These are emulator tests, not multi-Element hardware
tests or a claim that arbitrary AP/router behavior has been tested.

A separate prior-match problem is reproducible in the original client:
inactive hit coordinates remain hashed across matches. Our reset cannot clear
those variables inside the peer's original browser game. Restarting the browser
removes that state, consistent with the hardware report. The MZF served at
`https://mzpico.com/files/bombernet/bombernet.mzf` was byte-identical to the
upstream repository download (SHA256
`07374256e573cfdcc8a3b4bdea5cc01d696d0ca41c25df5c8cb32f4ab6ff47d4`).
Do not suppress DESYNC or require a shared AP as a workaround. Further hardware
checks should include two/four Element devices and repeated online/offline games.

Reproducibility: unpack `tests/alpha14-reference.zip` at repository root. It
contains exact alpha13/alpha10 game references and the upstream binaries/map.
With SjASMPlus 1.20.3 and the emulator dependencies:

```
python ports/esp01/tests/link_alpha14_overlay128.py /path/to/sjasmplus
python ports/esp01/pack_game128.py
python ports/esp01/tests/test_alpha14_128.py
python ports/esp01/tests/test_alpha13_128.py
python ports/esp01/tests/profile_alpha14.py
UPSTREAM_TIMED_MS=120 ESP_MATCH=ports/esp01/tests/match_upstream14.py python ports/esp01/tests/test_relay128.py
UPSTREAM_HOST=1 UPSTREAM_TIMED_MS=120 ESP_MATCH=ports/esp01/tests/match_upstream14.py python ports/esp01/tests/test_relay128.py
```

`UPSTREAM_HISTORY=1` is an intentional negative regression: inject different
legitimate prior-hit coordinates before seeding, and the original client's first
hash disagrees. It must fail, documenting the remaining cross-client history
issue rather than claiming it was fixed solely by changing the ESP build.
Native equivalence tests cover 512 tile writes, 2304 timer edges, 2048 four-player
render/collision/scoring cases and 128 death-color cases. Offline restarts,
WebSocket parsing, audio and loader checks also pass. TAP remains 52,512 bytes;
game remains 40,947 bytes, driver bank 11,358, loader 100. Helpers reuse existing
code gaps; the memory allocation end remains FDB3. Normal source builds include
the same routines; this delivered TAP uses the reproducible local assembly
link, not a newly claimed GitHub Actions build.


### Alpha 15: earlier input and less per-frame CPU work

Input is sampled before HUD drawing/compositing in network frames. For rooms
advertising two input frames, the ESP slot now chooses one frame and primes
exactly that frame count. This removes about 60 ms from the scheduled-input
component, not all network latency. Advertised delays of three through eight
frames are retained; the chosen count never changes after match seeding.
Frame numbers remain authoritative and the original peer keeps its own delay.

Native HUD, player animation/pickup routines, empty-object scans and bomb-key
filtering preserve the original state and animation side effects. Offline
input ordering, 60 ms pacing, AY audio, UART baud and purple HUD colors remain
unchanged. Only player labels are colored in multiplayer; other HUD text is black.

An identical deterministic CPU benchmark against alpha14 fell from 38.247475 ms
to 34.831121 ms per frame (8.93%). This excludes frame pacing and real network
waiting and does not promise a 10% hardware crossing-time improvement. Native
equivalence tests cover randomized HUD/player states and every live object slot.
Four independent emulated ESP clients pass startup movement and state hashes.
Unmodified upstream clients pass startup input, both host roles, timed network
delivery and cooperative bombs. The original-client prior-match history issue
described above remains; hash checks are not disabled.

Unpack `tests/alpha15-reference.zip` at repository root, then run:

```
python ports/esp01/tests/link_alpha15_overlay128.py /path/to/sjasmplus
python ports/esp01/pack_game128.py
python ports/esp01/tests/test_alpha15_128.py
PROFILE_REFERENCE=alpha14 python ports/esp01/tests/profile_alpha14.py
UPSTREAM_FORCE_DELAY=2 UPSTREAM_KEYS_ON_START=1 UPSTREAM_TIMED_MS=120 ESP_MATCH=ports/esp01/tests/match_upstream14.py python ports/esp01/tests/test_relay128.py
ESP_MATCH=ports/esp01/tests/match_four15.py python ports/esp01/tests/test_relay128.py
```

The TAP is built by the reproducible assembly overlay on exact alpha14 bytes.
Game size and memory end remain unchanged: 40,947 bytes / FDB3. The BASIC block
starts with version 15 (`15Bomberma`, limited to ten characters by TAP format).


### Alpha 16: stable status-bar colors

The renderer skips intermediate attribute stores for the active HUD row. The
final HUD helper writes an attribute only when its intended value changes,
instead of clearing the row to black and recoloring it on every frame. This
removes the repeated temporary colors that could be seen during a ULA scan.
Player labels plus the life/win icon and count use the corresponding player
ink on purple paper. Single-player remains entirely black on purple.
In the compact three/four-player layout, six-pixel glyphs share eight-pixel
attribute cells: coloring the complete life group also colors boundary pixels
of the adjacent fixed score zero. The two-player layout keeps these groups
separate. This is Spectrum attribute granularity, not attribute flickering.

No simulation, network-input policy or frame pacing is changed from alpha15.
Native tests change scores, lives/wins and time in online/offline layouts for
one through four players and trap actual attribute-store instructions: stable
HUD attributes are never rewritten. Pixels/playfield attributes match alpha15;
title rendering remains unchanged. Original-peer timed-network hashes pass.

Reproduce from `tests/alpha16-reference.zip` at repository root:

```
python ports/esp01/tests/link_alpha16_overlay128.py /path/to/sjasmplus
python ports/esp01/pack_game128.py
python ports/esp01/tests/test_alpha16_128.py
python ports/esp01/tests/test_alpha15_128.py
```

The delivered `runable/16Bomberman.tap` uses this exact-byte assembly overlay;
normal source includes the same renderer/helper. TAP size remains 52,512 bytes.


### Alpha 17: align the three-player HUD

Three-player blocks now start at logical columns 0, 12 and 24. Labels occupy
one dedicated attribute cell, five score glyphs stay in black cells, and the
life/win icon plus count start at local columns 8/9 in separate player-colored
cells. Time uses `T` plus four digits in columns 35..39 (the stage starts at
1000); the enemy-count field is omitted to make room. Four-player layout,
one/two-player HUD, simulation and networking remain unchanged. The alpha16
stable attribute update remains in place.

Native tests verify every pixel column occupied by three-player score and time
glyphs has black ink, life/win values match alpha16, and high-score updates
remain exact. Randomized one/two/four-player HUD bytes match alpha16. Stable
attribute writes, online/offline layouts and loader checks pass.

Reproduce by unpacking `tests/alpha17-reference.zip` at repository root:

```
python ports/esp01/tests/link_alpha17_overlay128.py /path/to/sjasmplus
python ports/esp01/pack_game128.py
python ports/esp01/tests/test_alpha17_128.py
```

The delivered TAP uses the exact alpha16 assembly overlay; normal source
includes the same compact HUD and attribute table. Game memory extent and TAP
size remain unchanged. Four-player attribute granularity described for alpha16
is unchanged; this release addresses the reported three-player layout.
