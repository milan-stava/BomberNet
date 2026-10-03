"""Assemble alpha 11 into the exact saved alpha 10 image and reclaimed code space."""
from pathlib import Path
import re,sys,struct,subprocess,hashlib
sys.path.insert(0,'ports/esp01')
from bank_layout import symbols
D=Path('build/esp01-128');R=Path('build/alpha10-reference')
g=bytearray((R/'bomber').read_bytes());original=bytes(g);ms=(R/'bomber.map').read_text();M=symbols(R/'bomber.map')
assert len(g)==40944
for name in ['esp_peer_legacy','esp_peer_fast','esp_input_delay']:
 M['_'+name]=24000+len(g);g.append(0)
parts=re.split(r'^; @(routine|helper) (\w+)(?: (\w+))?\n',Path('ports/esp01/alpha11_fast.a80').read_text(),flags=re.M)
units=[dict(kind=parts[i],name=parts[i+1],end=parts[i+2],body=parts[i+3]) for i in range(1,len(parts),4)]
for u in units:
 if u['kind']=='helper':M['_'+u['name']+'_new']=0x8000
M['_esp_choose_delay']=0x8000
M['_net_msg_send_general']=M['_net_msg_recv_general']=0x8000
def asm(body,at):
 defined=set(re.findall(r'^(\w+):',body,re.M))
 eq=''.join(f'{k} EQU {v}\n' for k,v in M.items() if k not in defined and re.fullmatch(r'\w+',k) and v<=65535)
 Path('/tmp/a11.a80').write_text(f' ORG {at}\n OUTPUT "/tmp/a11.bin"\n'+eq+body+'\n OUTEND\n')
 r=subprocess.run([sys.argv[1],'--sym=/tmp/a11.sym','/tmp/a11.a80'],capture_output=True,text=True)
 if r.returncode:raise RuntimeError(r.stdout+r.stderr)
 sy={k:int(v,16) for k,v in re.findall(r'^(\w+): EQU 0x([0-9A-Fa-f]+)',Path('/tmp/a11.sym').read_text(),re.M)}
 return Path('/tmp/a11.bin').read_bytes(),sy
free=[]
for u in units:
 if u['kind']!='routine':continue
 u['at']=M['_'+u['name']];u['limit']=M['_'+u['end']]
 b,_=asm(u['body'],u['at']);assert u['at']+len(b)<=u['limit'],(u['name'],len(b),u['limit']-u['at'])
 free.append([u['at']+len(b),u['limit']])
def allocate(n):
 for gap in free:
  if gap[1]-gap[0]>=n:a=gap[0];gap[0]+=n;return a
 raise AssertionError(('no code space',n,free))
# Host announces at least two frames. The independent local delay is selected
# at match start, only after a positively identified two-machine lobby.
s=Path('c/core/bomber.c').read_text();i=s.index('__asm',s.index('static void lobby_apply_rtt('))+5
rtt=s[i:s.index('__endasm',i)].replace('    or a\n    jr nz,r9_nonzero\n    inc a','    cp 2\n    jr nc,r9_nonzero\n    ld a,2')
units.append(dict(kind='helper',name='lobby_apply_rtt',body=rtt))
for u in units:
 if u['kind']!='helper':continue
 b,_=asm(u['body'],0x8000);u['at']=allocate(len(b));M['_'+u['name']+'_new']=u['at']
 if u['name']=='esp_choose_delay':M['_esp_choose_delay']=u['at']
# Preserve the complete first instructions in the old C message functions.
for name in ['net_msg_send','net_msg_recv']:
 at=M['_'+name];prefix=original[at-24000:at-24000+4]
 assert prefix[0]==0xc5 and prefix[1] in (0x3a,0xcd)
 body=' defb '+','.join(str(v) for v in prefix)+'\n jp '+str(at+4)+'\n'
 a=allocate(7);M['_'+name+'_general']=a;units.append(dict(kind='support',name=name+'_general',body=body,at=a))
at=M['_room_request'];prefix=original[at-24000:at-24000+4]
assert prefix[0]==0xc5 and prefix[1]==0x3a
body=' xor a\n ld (_esp_peer_legacy),a\n ld (_esp_peer_fast),a\n defb '+','.join(str(v) for v in prefix)+'\n jp '+str(at+4)+'\n'
a=allocate(14);units.append(dict(kind='helper',name='room_request',body=body,at=a))
for u in units:
 b,sy=asm(u['body'],u['at']);g[u['at']-24000:u['at']-24000+len(b)]=b
 for k,v in sy.items():
  if k not in M:M[k]=v
 if u['kind']=='helper' and u['name']!='esp_choose_delay':
  old=M['_'+u['name']]-24000;g[old:old+3]=b'\xc3'+struct.pack('<H',u['at'])
 print(u['name'],len(b),'bytes at',hex(u['at']))
for k in ['__BSS_END_tail']:
 ms=re.sub(r'('+k+r'\s*= \$)[0-9A-Fa-f]+',lambda x:x[1]+'%04X'%(24000+len(g)),ms)
existing=symbols(R/'bomber.map')
for k,v in M.items():
 if k not in existing and 0<=v<=65535:ms+='\n%s = $%04X ; addr, local\n'%(k,v)
(D/'bomber').write_bytes(g);(D/'bomber.map').write_text(ms)
print('end',hex(24000+len(g)),'remaining reclaimed code bytes',sum(b-a for a,b in free))
