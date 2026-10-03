"""Assemble alpha 9 routines in reclaimed WebSocket code space of alpha 8."""
from pathlib import Path
import sys,re,struct,subprocess,hashlib
sys.path.insert(0,'ports/esp01');from bank_layout import symbols
D=Path('build/esp01-128');M=symbols(D/'bomber.map')
g=bytearray((D/'bomber').read_bytes())
BM=symbols(D/'esp_bank.map');M['ESP_RECV']=BM['_tcp_recv'];M['ESP_SEND']=BM['_tcp_send'];M['_eb_rx_idle']=M['_ay_start']
assert hashlib.sha256(g).hexdigest()=='c8a9d470108916e433d503b7b3faa1c03423718b5a2a4aaec15b3fc817ac8520','requires exact alpha 8 game'
def asm(body,at):
 defined=set(re.findall(r'^(\w+):',body,re.M))
 eq=''.join(f'{k} EQU {v}\n' for k,v in M.items() if k not in defined and re.fullmatch(r'\w+',k) and v<=65535)
 Path('/tmp/a9.a80').write_text(f' ORG {at}\n OUTPUT "/tmp/a9.bin"\n'+eq+body+'\n OUTEND\n')
 subprocess.run([sys.argv[1],'/tmp/a9.a80'],check=True)
 return Path('/tmp/a9.bin').read_bytes()
def body(path,name):
 s=Path(path).read_text();a=s.index('__asm',s.index(name+'('))+5;return s[a:s.index('__endasm',a)]
def put(at,code):g[at-24000:at-24000+len(code)]=code
ws=asm(body('c/common/ws.c','ws_poll'),M['_ws_poll']);put(M['_ws_poll'],ws)
at=M['_ws_poll']+len(ws)
ay=asm(body('c/platform/zx/plat_zx.c','ay_tone'),at);put(at,ay)
put(M['_ay_tone'],b'\xc3'+struct.pack('<H',at));at+=len(ay)
update=asm(''' ld a,(_ay_active)
 or a
 ret z
 ld hl,8
 call _zx_ay
 ld hl,9
 call _zx_ay
 ld hl,10
 call _zx_ay
 xor a
 ld (_ay_active),a
 ret
''',at);old_update=M['_ay_update'];update_at=at;put(at,update);at+=len(update)
needle=b'\xcd'+struct.pack('<H',old_update)
pos=g.index(needle,M['_plat_frame_sync']-24000,M['_plat_frame_sync']-24000+200)
g[pos:pos+3]=b'\xcd'+struct.pack('<H',update_at)
assert at<=M['_ws_close'],(len(ws),len(ay),hex(at))
print('WS bytes',len(ws),'AY bytes',len(ay),'free WS space',M['_ws_close']-at)
rtt=asm(body('c/core/bomber.c','lobby_apply_rtt'),M['_lobby_apply_rtt']);put(M['_lobby_apply_rtt'],rtt)
s=Path('c/platform/zx/plat_zx.c').read_text();hud=s[s.index('fz_hud_colors:'):s.index('fz_bar:  defb 0')]
hudat=M['_lobby_apply_rtt']+len(rtt);helper=asm(hud,hudat);put(hudat,helper)
assert hudat+len(helper)+8<=M['_lobby_build_table']
stub=asm('    call %d\n    ei\n    pop ix\n    ret\n'%hudat,hudat+len(helper));put(hudat+len(helper),stub)
# Last flush instructions, preserving every renderer entry/branch address.
end=g.index(bytes.fromhex('fb dde1 c9'.replace(' ','')),M['_flush_screen']-24000,M['fz_chg3']-24000)+24000
put(end,b'\xc3'+struct.pack('<H',hudat+len(helper))+b'\x00')
# Joiner's clamp for LM_DELAY only (not the player-count clamp).
assert g[0x7bad-24000:0x7bb4-24000]==bytes.fromhex('d602d2b87b2102')
g[0x7bae-24000]=1;g[0x7bb3-24000]=1
assert g[0x7cef-24000:0x7cf4-24000]==bytes.fromhex('3e0332edeb')
g[0x7cf0-24000]=2
assert hudat+len(helper)+len(stub)<=M['_lobby_build_table']
print('RTT',len(rtt),'HUD',len(helper),'stub',len(stub))
for path,name,end in [('c/common/netdev_soft.c','net_send','_net_poll'),('c/common/netdev_soft.c','net_poll','_net_hash'),('c/core/video.c','print_num5','_print_num4'),('c/core/video.c','print_num4','_clear_buffers'),('c/core/player.c','put_player_char','_player_killed')]:
 code=asm(body(path,name),M['_'+name]);limit=M[end]
 assert len(code)<=limit-M['_'+name],(name,len(code),limit-M['_'+name])
 put(M['_'+name],code);print(name,len(code))
# Empty receive calls need no paging until the UART reports bytes/overflow.
recv_at=M['_ay_tone']+3
recv=asm(body('ports/esp01/tcp_bank128.c','tcp_recv'),recv_at)
assert recv_at+len(recv)<=M['_plat_frame_sync']
put(recv_at,recv);put(M['_tcp_recv'],b'\xc3'+struct.pack('<H',recv_at))
bankcall_at=M['_print_num4']+63
bankcall=asm(body('ports/esp01/tcp_bank128.c','bank_call'),bankcall_at)
assert bankcall_at+len(bankcall)<=M['_clear_buffers']
put(bankcall_at,bankcall);put(M['_bank_call'],b'\xc3'+struct.pack('<H',bankcall_at))
print('Idle RX bridge',len(recv),'bank call',len(bankcall))
# Alpha 8's appended AY continuation is now unused; reclaim its 76 bytes.
assert len(g)==41016
del g[-76:]
(D/'bomber').write_bytes(g)
p=D/'bomber.map';s=p.read_text()
for name in ['eb_return','eb_arg1','eb_arg2','eb_target','eb_sp','eb_page']:
 value=bankcall_at+M[name]-M['_bank_call']+4
 s=re.sub(r'('+name+r'\s*= \$)[0-9A-Fa-f]+',lambda x:x[1]+'%04X'%value,s)
s=re.sub(r'(_ay_update\s*= \$)[0-9A-Fa-f]+',lambda x:x[1]+'%04X'%update_at,s);s+='\n_eb_rx_idle = $%04X ; addr, local\n'%M['_eb_rx_idle'];s=re.sub(r'(__BSS_END_tail\s*= \$)[0-9A-Fa-f]+',lambda x:x[1]+'%04X'%(24000+len(g)),s);p.write_text(s)

# Bank-only discovery path: short AT probe, conservative escape guards.
M=symbols(D/'esp_bank.map');bank=bytearray((D/'esp_bank').read_bytes());bankat=0xc000+len(bank)
assert hashlib.sha256(bank).hexdigest()=='b8ed64ed4055b1ff50cf5621348bfa645f53b7b8d73afc6ad7f445996f6a835e','requires exact alpha 8 bank'
s=Path('ports/esp01/tcp_esp_fast.c').read_text()
probe=s[s.index('es_probe:'):s.index('es_command:')]
escape=s[s.index('es_escape_unknown:'):s.index('; Wait for DE ROM ticks;')]
code=asm(body('ports/esp01/tcp_esp_fast.c','tcp_present')+'\n'+probe+'\n'+escape,bankat)
bank[M['_command_present']-0xc000:M['_command_present']-0xc000+3]=b'\xc3'+struct.pack('<H',bankat)
bank.extend(code);assert 0xc000+len(bank)<=0xfdff
(D/'esp_bank').write_bytes(bank)
p=D/'esp_bank.map';s=p.read_text();s=re.sub(r'(__BSS_END_tail\s*= \$)[0-9A-Fa-f]+',lambda x:x[1]+'%04X'%(0xc000+len(bank)),s);p.write_text(s)
print('Quick probe bank extension',len(code))
