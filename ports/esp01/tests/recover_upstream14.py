"""Recover unchanged SCC Z80 routines/relocations from the published upstream TAP."""
from pathlib import Path
import re,sys,collections,struct
sys.path.insert(0,'ports/esp01');from bank_layout import symbols
R=Path('build/alpha10-reference');U=Path('build/upstream-reference')
a=(R/'bomber').read_bytes();tap=(U/'bombernet.tap').read_bytes();p=0
while p<len(tap):n=int.from_bytes(tap[p:p+2],'little');block=tap[p+2:p+2+n];p+=n+2
b=block[1:-1];(U/'bomber').write_bytes(b)
M=symbols(R/'bomber.map');ms=(R/'bomber.map').read_text()
funcs={}
for line in ms.splitlines():
 m=re.match(r'(_\w+)\s*= \$([0-9A-F]+).*addr,.*code_compiler',line)
 if m:funcs[m[1]]=int(m[2],16)

def ins(d,p):
 start=p;op=d[p];p+=1;index=False
 if op in [0xdd,0xfd]:index=True;op=d[p];p+=1
 if op==0xcb:return p+2 if index else p+1,[]
 if op==0xed:
  v=d[p];p+=1
  return (p+2,[p]) if v>>6==1 and (v&7)==3 else (p,[])
 x=op>>6;y=(op>>3)&7;z=op&7;q=y&1;t=y>>1
 mask=[];extra=0
 if x==0:
  if z==0 and y>=2:extra=1
  elif z==1 and q==0:extra=2;mask=[p]
  elif z==2 and t>=2:extra=2;mask=[p]
  elif z in [4,5] and y==6 and index:extra=1
  elif z==6:extra=1+int(index and y==6)
 elif x in [1,2]:extra=int(index and (z==6 or (x==1 and y==6)) and op!=0x76)
 elif x==3:
  if z in [2,4] or (z==3 and y==0) or (z==5 and q==1 and t==0):extra=2;mask=[p]
  elif z==3 and y in [2,3] or z==6:extra=1
 return p+extra,mask

def pattern(raw):
 mask=[];p=0
 try:
  while p<len(raw):
   p2,mm=ins(raw,p)
   if p2>len(raw):break
   mask+=mm;p=p2
 except IndexError:pass
 tokens=[re.escape(bytes([c])) for c in raw[:p]]
 for m in mask:
  if m+1<p:tokens[m]=b'.';tokens[m+1]=b'.'
 return b''.join(tokens),mask,p
addresses=sorted(set(funcs.values()));found={};rel=collections.defaultdict(collections.Counter)
for name,at in funcs.items():
 end=next((x for x in addresses if x>at),at+120)
 raw=a[at-24000:min(end-24000,at-24000+180)]
 if len(raw)<20:continue
 pat,mask,n=pattern(raw)
 if n<20:continue
 hits=list(re.finditer(pat,b,re.S))
 if len(hits)!=1:continue
 target=24000+hits[0].start();found[name]=target
 for m in mask:
  if m+1>=n:continue
  old=int.from_bytes(raw[m:m+2],'little');new=int.from_bytes(b[hits[0].start()+m:hits[0].start()+m+2],'little')
  if old>=24000 and new>=24000:rel[old][new]+=1
for name,at in M.items():
 if at in rel and name not in found:
  best,count=rel[at].most_common(1)[0]
  if len(rel[at])==1:found[name]=best
(U/'bomber.map').write_text('\n'.join(f'{n} = ${v:04X} ; addr, recovered' for n,v in sorted(found.items()))+'\n')
print('code routines',len(funcs),'matched',len(found))
for n in ['_flush_screen','_frame','_net_match_start','_input_poll','_net_lockstep_poll','_frame_no','_state_hash','_menu_net','_net_code','_players','_map_layer','_rng_seed','_hit_x','_title_mode','_net_delay','_net_active']:
 print(n,hex(found[n]) if n in found else 'MISSING')
