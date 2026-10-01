#!/bin/sh
set -eu
cd "$(dirname "$0")/../.."
mkdir -p build/esp01 build/spectranet
core='c/core/bomber.c c/core/netplay.c c/core/data.c c/core/map.c c/core/game.c c/core/input.c c/core/video.c c/core/enemy.c c/core/bomb.c c/core/player.c'
common='c/platform/zx/plat_zx.c c/platform/zx/tables.c c/common/netdev_soft.c c/common/ws.c c/common/z80_loops.c'
flags='+zx -lndos -zorg=24000 -pragma-define:REGISTER_SP=65535 -pragma-define:CLIB_EXIT_STACK_SIZE=0 -pragma-define:CRT_ENABLE_STDIO=0 -pragma-define:CLIB_OPEN_MAX=0 -pragma-redirect:fputc_cons=zx_no_console -m -Ic/core -Ic/common -Ic/platform/zx'
zcc $flags -o build/spectranet/bomber $core $common c/platform/zx/tcp_spectranet.c
cp ports/esp01/WifiBios20_MB_EL.cod WifiBios20_MB_EL.cod
# Compile before packing a TAP, so the complete linker map can be inspected.
zcc $flags -Iports/esp01 -o build/esp01/bomber $core $common ports/esp01/tcp_esp_at.c ports/esp01/esp_uart_bios.c
