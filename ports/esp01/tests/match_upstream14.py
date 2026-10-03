"""Cross-play shipped unmodified upstream ZX binary with ESP build, both roles."""
import sys,os,time
from pathlib import Path
sys.path.insert(0,'tools');sys.path.insert(0,'ports/esp01/tests')
from zxemu import ZX,sym_from_map
from test_bank128 import BankZX
class Client:
 def __init__(self,original):
  self.original=original; self.path='build/upstream-reference/bomber.map' if original else 'build/esp01-128/bomber.map'
  self.z=ZX(spectranet=True) if original else BankZX(real=True)
  if original:self.z.load('build/upstream-reference/bomber')
  else:self.z.pc=24000
  self.f=self.s('_flush_screen');self.z.set_breakpoint(self.f);self.seen={}
 def s(self,n):return sym_from_map(self.path,n)
 def r(self,n):return self.z.read8(self.s(n))
 def r16(self,n):return self.z.read16(self.s(n))
 def wr(self,n,b):self.z.poke(self.s(n),b)
 def step(self):
  p=self.z.step()
  if p==self.f and self.r('_net_active'):
   f=self.r16('_frame_no')
   if f>=16:self.seen[f//16*16]=self.r16('_state_hash')
  return p
 def press(self,k):self.z.press(k)
 def release(self,k):self.z.release(k)
a,b=Client(False),Client(True);both=(a,b)
def frames(n):
 counts=[0,0];deadline=time.time()+120
 while min(counts)<n:
  for _ in range(2):
   i=min(range(2),key=lambda i:link.now(i)) if 'link' in globals() else _
   c=both[i]
   if c.step()==c.f:counts[i]+=1
  assert time.time()<deadline,('timeout',[(hex(c.z.pc),c.r('_title_mode'),c.r('_net_abort')) for c in both])
def tap(c):c.press('SPACE');frames(4);c.release('SPACE');frames(2)
frames(4)
if os.environ.get('UPSTREAM_HISTORY')=='1':
 a.wr('_hit_x',[7,12]);b.wr('_hit_x',[22,3])
print('boot',[(c.r('_title_mode'),c.r('_net_device')) for c in both],flush=True)
h,j=(a,b) if os.environ.get('UPSTREAM_HOST')!='1' else (b,a)
h.wr('_menu_mode',[int(os.environ.get('GAME_MODE',1))]);h.wr('_menu_players',[2]);h.wr('_menu_net',[1]);h.wr('_menu_local',[1]);j.wr('_menu_net',[2]);j.wr('_menu_local',[1])
old=h.z.read(h.s('_net_code'),4);tap(h)
for _ in range(600):
 if h.z.read(h.s('_net_code'),4)!=old:break
 frames(1)
code=h.z.read(h.s('_net_code'),4);print('room',code,flush=True);j.wr('_net_code',code);tap(j);frames(4);tap(j);frames(60)
tap(j);tap(h)
for _ in range(300):
 if all(c.r('_title_mode')==0 for c in both):break
 frames(1)
assert all(c.r('_title_mode')==0 and c.r('_net_active') for c in both), 'both clients must enter a live match'
print('start',[(c.r('_title_mode'),c.r('_net_active'),c.r('_net_delay'),c.z.read(c.s('_net_table'),4).hex()) for c in both],flush=True)
if os.environ.get('UPSTREAM_TIMED_MS'):
 frames(8)
 arrived=[False,False]
 while not all(arrived):
  for i,c in enumerate(both):
   if not arrived[i] and c.step()==c.f:arrived[i]=True
 from timed_upstream14 import Link
 link=Link(both,int(os.environ['UPSTREAM_TIMED_MS']))
 print('timed link',os.environ['UPSTREAM_TIMED_MS'],flush=True)
a.press('P');b.press('O')
for _ in range(100):
 frames(1)
 if any(c.r('_net_abort') for c in both):break
print('end',[(c.r16('_frame_no'),c.r('_net_abort'),c.seen) for c in both],flush=True)
for c in both:c.z.screenshot('build/upstream-reference/'+('original' if c.original else 'esp')+'.png')
common=set(a.seen)&set(b.seen);bad=[f for f in common if a.seen[f]!=b.seen[f]]
print('mismatches',bad,flush=True)
if 'link' in globals():
 print('wire hashes',link.hashes,'bad',link.mism,'inputs',link.inputs,flush=True)
 assert not link.mism
assert common and not bad and not any(c.r('_net_abort') for c in both)
