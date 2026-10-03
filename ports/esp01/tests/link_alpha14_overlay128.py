"""Label-only purple HUD overlay over the exact alpha13 game."""
from pathlib import Path
import sys,re,subprocess,struct,shutil,hashlib
sys.path.insert(0,'ports/esp01');from bank_layout import symbols
D=Path('build/esp01-128');R=Path('build/alpha13-reference')
if not R.exists():
 R.mkdir()
 for n in ['bomber','bomber.map','esp_bank','esp_bank.map']:shutil.copy(D/n,R/n)
M=symbols(R/'bomber.map');g=bytearray((R/'bomber').read_bytes())
assert hashlib.sha256(g).hexdigest()=='b580a1219bb7ff265ef8a2d8f8f6d60cf12710dce5f53693b60cf61c8434f860', 'requires exact alpha13 reference'
s=Path('c/platform/zx/plat_zx.c').read_text();body=s[s.index('fz_hud_colors:'):s.index('\nfz_bar:',s.index('fz_hud_colors:'))]
# fz_bar is a private assembler symbol not exported by SCC; derive address
# from the existing helper's first LD A,(fz_bar).
old=0x774a;assert g[old-24000]==0x3a
M['fz_bar']=int.from_bytes(g[old-23999:old-23997],'little')
eq=''.join(f'{k} EQU {v}\n' for k,v in M.items() if re.fullmatch(r'\w+',k) and v<=65535)
a=0xb172
Path('/tmp/a14.a80').write_text(f' ORG {a}\n OUTPUT "/tmp/a14.bin"\n'+eq+body+'\n OUTEND\n')
r=subprocess.run([sys.argv[1],'/tmp/a14.a80'],capture_output=True,text=True)
assert r.returncode==0,r.stdout+r.stderr
b=Path('/tmp/a14.bin').read_bytes();assert len(b)<=0xb259-a
assert M['_net_msg_recv_new']+109==a and M['_players_anim_step']==0xb259
g[a-24000:a-24000+len(b)]=b;g[old-24000:old-23997]=b'\xc3'+struct.pack('<H',a)
print('label HUD',hex(a),len(b))
parts=re.split(r'^; @routine (\w+) (\w+)\n',Path('ports/esp01/alpha14_fast.a80').read_text(),flags=re.M)
for i in range(1,len(parts),3):
 name,end,body=parts[i:i+3];at=M['_'+name]
 Path('/tmp/a14.a80').write_text(f' ORG {at}\n OUTPUT "/tmp/a14.bin"\n'+eq+body+'\n OUTEND\n')
 r=subprocess.run([sys.argv[1],'/tmp/a14.a80'],capture_output=True,text=True);assert not r.returncode,r.stdout+r.stderr
 b=Path('/tmp/a14.bin').read_bytes();assert at+len(b)<=M['_'+end],(name,len(b))
 g[at-24000:at-24000+len(b)]=b;print(name,len(b),hex(at))
# Skip the C colour renderer entirely when no visible player is dying.
old=M['_players_death_colour'];prefix=bytes(g[old-24000:old-24000+4]);assert prefix==bytes.fromhex('3b210000')
at=0xb172+102;M['_players_death_colour_full']=at
eq=''.join(f'{k} EQU {v}\n' for k,v in M.items() if re.fullmatch(r'\w+',k) and v<=65535)
source=Path('c/core/player.c').read_text();i=source.index('__asm',source.index('void players_death_colour(void) __naked'))+5
body=' defb '+','.join(map(str,prefix))+'\n jp '+str(old+4)+'\n'+source[i:source.index('__endasm',i)]
Path('/tmp/a14.a80').write_text(f' ORG {at}\n OUTPUT "/tmp/a14.bin"\n'+eq+body+'\n OUTEND\n')
r=subprocess.run([sys.argv[1],'/tmp/a14.a80'],capture_output=True,text=True);assert not r.returncode,r.stdout+r.stderr
b=Path('/tmp/a14.bin').read_bytes();assert at+len(b)<=0xb259
g[at-24000:at-24000+len(b)]=b;g[old-24000:old-23997]=b'\xc3'+struct.pack('<H',at+7)
print('death-colour fast check',len(b),hex(at))
(D/'bomber').write_bytes(g)

