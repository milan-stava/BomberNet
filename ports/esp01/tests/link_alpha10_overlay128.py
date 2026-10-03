"""Reproduce alpha 10 from the exact alpha 9 reference images."""
from pathlib import Path
import sys,re,struct,subprocess
sys.path.insert(0,'ports/esp01')
from bank_layout import symbols
D=Path('build/esp01-128'); R=Path('build/alpha9-reference')
g=bytearray((R/'bomber').read_bytes());s=(R/'bomber.map').read_text();M=symbols(R/'bomber.map')
assert len(g)==40940
M['_ay_remaining']=24000+len(g);M['_esp_defer_present']=M['_ay_remaining']+3
g.extend(bytes(4))
def asm(body,at):
 defined=set(re.findall(r'^(\w+):',body,re.M))
 eq=''.join(f'{k} EQU {v}\n' for k,v in M.items() if k not in defined and re.fullmatch(r'\w+',k) and v<=65535)
 Path('/tmp/a10.a80').write_text(f' ORG {at}\n OUTPUT "/tmp/a10.bin"\n'+eq+body+'\n OUTEND\n')
 subprocess.run([sys.argv[1],'--sym=/tmp/a10.sym','/tmp/a10.a80'],check=True)
 sy= {k:int(v,16) for k,v in re.findall(r'^(\w+): EQU 0x([0-9A-Fa-f]+)',Path('/tmp/a10.sym').read_text(),re.M)}
 return Path('/tmp/a10.bin').read_bytes(),sy
def put(at,b):g[at-24000:at-24000+len(b)]=b
def jp(at,to):put(at,b'\xc3'+struct.pack('<H',to))
audio_at=M['_ws_poll']+347
b,sy=asm(Path('ports/esp01/alpha10_audio.a80').read_text(),audio_at)
assert audio_at+len(b)<=M['_ws_close'],len(b)
put(audio_at,b);jp(M['_ay_tone'],audio_at);M['_ay_update']=sy['update10']
body=Path('ports/esp01/alpha10_timing.a80').read_text()
sync,rest=body.split('; Present network')
b,_=asm(sync,M['_plat_frame_sync']);assert len(b)<=M['_plat_delay']-M['_plat_frame_sync'];put(M['_plat_frame_sync'],b)
at=M['_lobby_apply_rtt']+48+78+7
b,sy=asm('; Present network'+rest,at);assert at+len(b)<=M['_lobby_build_table'],len(b);put(at,b)
assert g[M['_frame']-24000:M['_frame']-24000+3]==b'\xcd'+struct.pack('<H',M['_frame_common'])
jp(M['_frame'],sy['frame10'])
for old,new in [('_flush_screen','flush10'),('_players_death_colour','colour10')]:
 needle=b'\xcd'+struct.pack('<H',M[old]);start=M['_tick_timers']-24000
 pos=g.index(needle,start,start+100);g[pos:pos+3]=b'\xcd'+struct.pack('<H',sy[new])
for k in ['_ay_update','__BSS_END_tail']:
 v=M[k] if k=='_ay_update' else 24000+len(g)
 s=re.sub(r'('+k+r'\s*= \$)[0-9A-Fa-f]+',lambda x:x[1]+'%04X'%v,s)
for k in ['_ay_remaining','_esp_defer_present']:s+='\n%s = $%04X ; addr, public\n'%(k,M[k])
(D/'bomber').write_bytes(g);(D/'bomber.map').write_text(s)
print('alpha10 game end',hex(24000+len(g)),'audio bytes',len(Path('/tmp/a10.bin').read_bytes()))
