"""Stable HUD attribute overlay on exact alpha16; no simulation/timing changes."""
from pathlib import Path
import hashlib,re,struct,sys,subprocess,shutil
sys.path.insert(0,'ports/esp01');from bank_layout import symbols
D=Path('build/esp01-128');R=Path('build/alpha16-reference')
M=symbols(R/'bomber.map');g=bytearray((R/'bomber').read_bytes())
assert hashlib.sha256(g).hexdigest()=='30ced5fd247905af443350ce162b13301ae5cccbe6fb51275a9cddf6c8c19b46'
M.update(fz_bar=0xc1b3,h16_two=0xb172,h16_compact=0xb190,h17_three=0xb1ae)
eq=''.join(f'{k} EQU {v}\n' for k,v in M.items() if re.fullmatch(r'\w+',k) and v<=65535)
def asm(body,at):
 Path('/tmp/a16.a80').write_text(f' ORG {at}\n OUTPUT "/tmp/a16.bin"\n'+eq+body+'\n OUTEND\n')
 r=subprocess.run([sys.argv[1],'/tmp/a16.a80'],capture_output=True,text=True);assert not r.returncode,r.stdout+r.stderr
 return Path('/tmp/a16.bin').read_bytes()
def put(at,b):g[at-24000:at-24000+len(b)]=b
# Preserve original compact HUD byte-for-byte; alter only color table/helper.
three=[0]*30
for index,start,n in [(1,0,1),(1,6,1),(2,7,2),(2,13,2),(3,15,1),(3,21,1)]:three[start:start+n]=[index]*n
put(0xb1ae,bytes(three))
body=Path('ports/esp01/alpha16_hud.a80').read_text().replace('    ld de,h16_compact\nh16_start:', '    ld de,h16_compact\n    cp 4\n    jr nz,h16_start\n    ld de,h17_three\nh16_start:')
b=asm(body,0xaed6);assert 0xaed6+len(b)<=M['_players_death_colour'];put(0xaed6,b)
(D/'bomber').write_bytes(g)
for n in ['bomber.map','esp_bank','esp_bank.map']:shutil.copy(R/n,D/n)
print('original HUD information/layout restored; only three-player colors changed')
