"""Exact alpha14 -> early input and native two-player HUD, using reclaimed code."""
from pathlib import Path
import hashlib,re,struct,sys,subprocess,shutil
sys.path.insert(0,'ports/esp01');from bank_layout import symbols
D=Path('build/esp01-128');R=Path('build/alpha14-reference')
if not R.exists():
 R.mkdir()
 for n in ['bomber','bomber.map','esp_bank','esp_bank.map']:shutil.copy(D/n,R/n)
M=symbols(R/'bomber.map');g=bytearray((R/'bomber').read_bytes())
assert hashlib.sha256(g).hexdigest()=='7c6910859851441028e59090ddaabce2b6e494d13ac8d7d699acd855662af51d'
eq=''.join(f'{k} EQU {v}\n' for k,v in M.items() if re.fullmatch(r'\w+',k) and v<=65535)
def asm(body,at):
 Path('/tmp/a15.a80').write_text(f' ORG {at}\n OUTPUT "/tmp/a15.bin"\n'+eq+body+'\n OUTEND\n')
 r=subprocess.run([sys.argv[1],'/tmp/a15.a80'],capture_output=True,text=True);assert not r.returncode,r.stdout+r.stderr
 return Path('/tmp/a15.bin').read_bytes()
def put(at,b):g[at-24000:at-24000+len(b)]=b
at=M['_draw_hud_multi'];b=asm(Path('ports/esp01/alpha15_hud.a80').read_text(),at);put(at,b)
frameat=at+len(b);hud_len=len(b)
assert g[M['_frame_common']-24000:M['_frame_common']-23997]==b'\xcd'+struct.pack('<H',M['_tick_timers'])
assert g[M['_frame']-23997:M['_frame']-23994]==b'\xcd'+struct.pack('<H',M['_input_poll'])
b=asm(Path('ports/esp01/alpha15_frame.a80').read_text(),frameat)
assert frameat+len(b)<=M['_draw_hud'];frame_len=len(b)
put(frameat,b);put(M['_frame'],b'\xc3'+struct.pack('<H',frameat))
source=Path('c/common/netdev_soft.c').read_text();i=source.index('__asm',source.index('void esp_choose_delay('))+5
b=asm(source[i:source.index('__endasm',i)],M['_esp_choose_delay']);assert len(b)<=56
put(M['_esp_choose_delay'],b)
# Fast returns for empty object lists, preserving animation side effects.
free=[[frameat+frame_len,M['_draw_hud']],[M['_draw_player']+127,M['_players_death_colour']]]
def allocate(n):
 for gap in free:
  if gap[1]-gap[0]>=n:a=gap[0];gap[0]+=n;return a
 raise AssertionError(('no space',n,free))
parts=re.split(r'^; @(helper|routine) (\w+) (\w+)\n',Path('ports/esp01/alpha15_empty.a80').read_text(),flags=re.M)
for i in range(1,len(parts),4):
 kind,name,end,body=parts[i:i+4]
 if kind=='routine':
  at=M['_'+name];b=asm(body,at);assert at+len(b)<=M['_'+end];put(at,b);continue
 old=M['_'+name];prefix=bytes(g[old-24000:old-24000+4]);assert prefix[0]==0x3b
 trampoline=allocate(7);M['_'+name+'_full']=trampoline
 eq=''.join(f'{k} EQU {v}\n' for k,v in M.items() if re.fullmatch(r'\w+',k) and v<=65535)
 put(trampoline,prefix+b'\xc3'+struct.pack('<H',old+4))
 n=len(asm(body,0x8000));a=allocate(n);b=asm(body,a);put(a,b);put(old,b'\xc3'+struct.pack('<H',a))
 print('empty-list',name,len(b),'at',hex(a))
parts=re.split(r'^; @routine (\w+) (\w+)\n',Path('ports/esp01/alpha15_players.a80').read_text(),flags=re.M)
for i in range(1,len(parts),3):
 name,end,body=parts[i:i+3];a=M['_'+name];b=asm(body,a);assert a+len(b)<=M['_'+end],(name,len(b));put(a,b)
 print(name,len(b),'at',hex(a))
(D/'bomber').write_bytes(g)
print('native HUD',hud_len,'bytes; early-input frame',frame_len,'bytes at',hex(frameat),'end',hex(24000+len(g)))
