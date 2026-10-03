"""Guard the fast JSON layout and restore a black multiplayer HUD on alpha11."""
from pathlib import Path
import sys,re,struct,subprocess,hashlib
sys.path.insert(0,'ports/esp01')
from bank_layout import symbols
D=Path('build/esp01-128');R=Path('build/alpha11-reference')
M=symbols(R/'bomber.map');g=bytearray((R/'bomber').read_bytes());ms=(R/'bomber.map').read_text()
assert len(g)==40947 and hashlib.sha256(g).hexdigest()=="5cd5c9226f4ec5d7797eb303f643f2daa98ab9b16bccf55e56f62d40db10a552"
# Unused tails reclaimed by alpha11 native routines. Keep each helper entirely
# in its own gap; compare against exact alpha11 bytes below before installing.
# Tail of alpha11 lockstep (352 bytes) and message-receive helper (109 bytes).
assert M['_net_lockstep_poll']==0x8d19 and M['_net_match_end']==0x8f57
assert M['_net_msg_recv_new']==0xb105 and M['_players_anim_step']==0xb259
free=[[0x8e79,0x8f57],[0xb172,0xb259]]
def asm(body,at):
 defined=set(re.findall(r'^(\w+):',body,re.M))
 eq=''.join(f'{k} EQU {v}\n' for k,v in M.items() if k not in defined and re.fullmatch(r'\w+',k) and v<=65535)
 Path('/tmp/a12.a80').write_text(f' ORG {at}\n OUTPUT "/tmp/a12.bin"\n'+eq+body+'\n OUTEND\n')
 r=subprocess.run([sys.argv[1],'/tmp/a12.a80'],capture_output=True,text=True)
 if r.returncode:raise RuntimeError(r.stdout+r.stderr)
 return Path('/tmp/a12.bin').read_bytes()
def allocate(body):
 n=len(asm(body,0x8000))
 for gap in free:
  if gap[1]-gap[0]>=n:at=gap[0];gap[0]+=n;return at,asm(body,at)
 raise AssertionError(('no space',n,free))
def put(at,b):g[at-24000:at-24000+len(b)]=b
s=Path('c/platform/zx/plat_zx.c').read_text();hud=s[s.index('fz_hud_colors:'):s.index('fz_bar:  defb 0')]
a,b=allocate(hud);put(a,b)
# Alpha9's post-flush continuation calls this fixed helper address.
assert g[0x774a-24000:0x774a-24000+3]==bytes.fromhex('3ab3c1')
put(0x774a,b'\xc3'+struct.pack('<H',a));print('HUD',len(b),hex(a))
s=Path('c/common/netdev_soft.c').read_text();i=s.index('    push hl',s.index('static uint8_t fast_input(const char *l) __z88dk_fastcall'))
guard=s[i:s.index('g12_fast:',i)].replace('    jr g12_fast','    jp g12_fast')
at=M['_fast_input'];prefix=bytes(g[at-24000:at-24000+6]);assert prefix[:3]==bytes.fromhex('7eb7ca')
M['g12_fast']=0x8000
body=guard+'g12_fast: defb '+','.join(map(str,prefix))+'\n jp '+str(at+6)+'\n'
a,b=allocate(body);put(a,b);put(at,b'\xc3'+struct.pack('<H',a));print('JSON guard',len(b),hex(a))
(D/'bomber').write_bytes(g);(D/'bomber.map').write_text(ms)
