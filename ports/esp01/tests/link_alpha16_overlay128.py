"""Stable HUD attribute overlay on exact alpha15; no simulation/timing changes."""
from pathlib import Path
import hashlib,re,struct,sys,subprocess,shutil
sys.path.insert(0,'ports/esp01');from bank_layout import symbols
D=Path('build/esp01-128');R=Path('build/alpha15-reference')
M=symbols(R/'bomber.map');g=bytearray((R/'bomber').read_bytes())
assert hashlib.sha256(g).hexdigest()=='ef146dbe2c87be8ec5fbd8fd45d151c560745fbcebe42db59e34fd47cbdbafe8'
M.update(fz_bar=0xc1b3,h16_two=0xb172,h16_compact=0xb190)
eq=''.join(f'{k} EQU {v}\n' for k,v in M.items() if re.fullmatch(r'\w+',k) and v<=65535)
def asm(body,at):
 Path('/tmp/a16.a80').write_text(f' ORG {at}\n OUTPUT "/tmp/a16.bin"\n'+eq+body+'\n OUTEND\n')
 r=subprocess.run([sys.argv[1],'/tmp/a16.a80'],capture_output=True,text=True);assert not r.returncode,r.stdout+r.stderr
 return Path('/tmp/a16.bin').read_bytes()
def put(at,b):g[at-24000:at-24000+len(b)]=b
# Attribute cells are eight pixels wide; HUD glyphs are six pixels wide.
# Color only full glyph spans for labels and life/win icon + count.
two=[0]*30;compact=[0]*30
for index,start,n in [(1,0,2),(1,7,2),(2,9,3),(2,17,2)]:two[start:start+n]=[index]*n
for index,start,n in [(1,0,1),(1,5,2),(2,7,2),(2,12,3),(3,15,1),(3,20,2),(4,22,2),(4,27,3)]:compact[start:start+n]=[index]*n
put(0xb172,bytes(two+compact))
b=asm(Path('ports/esp01/alpha16_hud.a80').read_text(),0xaed6);assert 0xaed6+len(b)<=M['_players_death_colour'];put(0xaed6,b)
assert g[0x774a-24000:0x774d-24000]==b'\xc3\x72\xb1';put(0x774a,b'\xc3\xd6\xae')
# Skip intermediate attribute stores for the active status row, preserving
# ordinary scene/title attributes. Replay the displaced complete instructions.
at=0xc106;prefix=bytes(g[at-24000:at-24000+7]);assert prefix==bytes.fromhex('dd21b5c12aa9c1')
guard='''
    ld a,(fz_bar)
    or a
    jr z,h16_original
    ld a,(_title_mode)
    or a
    jr nz,h16_original
    ld a,(0xc1b4)
    or a
    ret nz
h16_original:
'''+ ' defb '+','.join(map(str,prefix))+'\n jp '+str(at+7)+'\n'
b=asm(guard,0xb2bc);assert 0xb2bc+len(b)<=M['_check_pickups'];put(0xb2bc,b);put(at,b'\xc3\xbc\xb2')
(D/'bomber').write_bytes(g)
for n in ['bomber.map','esp_bank','esp_bank.map']:shutil.copy(R/n,D/n)
print('stable HUD colors:',len(Path('/tmp/a16.bin').read_bytes()),'guard bytes; unchanged game extent',hex(24000+len(g)))
