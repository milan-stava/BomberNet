# ESP-01 alpha 10 (128K)

Network gameplay presents the newly simulated frame immediately rather than at the next 60 ms frame boundary. Animation-only screens retain their previous presentation path. Simulation rules, input delay negotiation, and the wire protocol are unchanged.

The network frame limiter retains its 60 ms clock phase after small overruns, with resynchronization after a delay of at least six TV frames. Offline timing is unchanged.

AY steps, bombs, and other effects use independent channel volumes and lifetimes. A step no longer retriggers a shared envelope and masks another effect. Pitch follows the measured beeper mapping. Network audio remains nonblocking; all channels mute after leaving a match.

Validation: native Z80 loader/driver, UART fragmentation/backpressure/recovery, AY pitch and channel isolation, frame phase, HUD attributes, state hashing, and local relay matches with two and four players passed. Hardware crossing time and perceived input latency need measurement on a 3.5 MHz machine; a four-second crossing is a target, not a measured result.

Download: runable/10Bomberman.tap on branch esp01-mb-el. BASIC header is 10Bomberma (Spectrum's ten-character limit). TAP size 52509 bytes; game end FDB0; ESP bank end EC5E. The reproducible compatibility assembler uses build/alpha9-reference images plus link_alpha10_overlay128.py; normal source builds include equivalent changes.
