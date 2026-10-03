# ESP01 MB/EL alpha11 (128K)

Download: `runable/11Bomberman.tap` (52512 bytes). BASIC header: `11Bomberma`.

Native Z80 decimal formatting, WebSocket framing, movement, hash-byte update and lockstep polling reduce CPU overhead. AY behavior remains alpha10.

Two-device/two-slot sessions announced with delay 2 use local input delay 0 against positively identified legacy peers, or 1 against tagged enhanced peers. Unknown peers, larger rooms and larger announced delays retain conservative buffering. This removes queued local input frames, not physical network/animation latency. Peer capability state resets before room requests.

Validation: native equivalence tests, input timing/capability tests, bank/loader, compositor, AY, clock scheduling and UART/stream regressions passed. Deterministic 115200-baud UART + 40ms one-way link, alpha11 HOST versus legacy alpha10 JOIN at announced delay 2: 120/119 frames, seven matching state hashes, no abort; corridor crossing 4.29/4.33 seconds in emulation. Hardware speed remains to be measured.

TAP built using SjASMPlus overlay of tested alpha10 game image (SHA256 92bc53a06a3650c6f83771b8429f7270c9ed40965a9fd55cfa5496db0226f15e), unchanged alpha10 driver bank and reassembled loader. Changed routines are also mirrored in C source under ESP_FAST128; a full z88dk source build was not run in this environment. Overlay tool: ports/esp01/tests/link_alpha11_overlay128.py; references expected in build/alpha10-reference.
