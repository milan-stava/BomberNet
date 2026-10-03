# ESP01 MB/EL alpha13: offline recovery and shared input pipeline

Use runable/13Bomberman.tap (128K, 52512 bytes; BASIC header 13Bomberma).

A network abort left net_abort set when entering the next offline match. play_stage then returned after its first frame, making offline play appear broken. Reproduced with DESYNC flag 4: before the fix, offline returned to title at frame 1. Every run_game entry now clears net_active/net_abort/net_waiting/hash_period and the deferred-presentation flag before selecting the mode. Online then starts its own fresh state; offline keeps hashing disabled.

The experimental per-peer local input delay from alpha11 is withdrawn. All clients now use the lobby's announced delay and seed the same number of initial zero frames. Native speed optimizations and AY remain; response buffering can be longer than alpha11. This removes an experimental startup-timing variable. Hardware testing must establish whether any further original-client DESYNC issue remains.

The complete alpha11 renderer/HUD is restored, including purple background. No alpha12 black HUD overlay remains. The reproduced JSON key-order guard is retained; state-hash/DESYNC detection is still enabled.

Passed checks:
- Actual title -> offline start -> directional movement after stale DESYNC/drop/BREAK/timeout flags.
- Original HUD pixels and attributes match alpha11 for one to four players.
- Network directions held at net_match_start against legacy alpha10 in both HOST/JOIN orientations; matching hashes at frames 16/32/48, no abort.
- Live local relay sending op/frame/data/slot ordering from the beginning; matching hashes, no abort. This does not use the deterministic-link transport handoff, which was unsuitable for this early-input scenario.
- Full live-relay online match -> injected DESYNC -> PRESS FIRE -> title -> OFF -> offline movement on both clients, in deathmatch and cooperative modes.
- 5376 parser permutations; existing native arithmetic/movement/hash, AY, clock, bank/loader and UART/stream checks.
- Host C build and 100-frame ASan/UBSan smoke run (environment requires LeakSanitizer disabled). Full z88dk ESP source rebuild not run.

Reproduction uses exact alpha11 references in ports/esp01/tests/alpha11-reference.zip (unzip at repository root), then link_alpha13_overlay128.py with a real SjASMPlus path, followed by pack_game128.py. Driver bank and loader unchanged. Source changes mirror the assembled patch.
