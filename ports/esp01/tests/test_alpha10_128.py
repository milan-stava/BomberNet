"""Actual Z80 audio isolation, clock phase and immediate presentation checks."""
from test_bank128 import BankZX,UART,S
class Audio(UART):
 def __init__(self):super().__init__();self.selected=0;self.regs={};self.writes=[]
 def output(self,p,v):
  if p==0xfffd:self.selected=v
  if p==0xbffd:self.regs[self.selected]=v;self.writes.append((self.selected,v))
  super().output(p,v)
u=Audio();z=BankZX(uart=u);z.poke(S('_net_active'),[1])
z.call('_plat_tone',0x0800,32)
assert u.regs[10]==12 and u.regs[4]+256*u.regs[5]==205
z.call('_plat_tone',0x060a,12)
assert u.regs[9]==12 and u.regs[2]+256*u.regs[3]==154
z.call('_plat_tone',0x020a,14)
assert [u.regs[i] for i in (8,9,10)]==[12,12,12]
assert not any(r in (11,12,13) for r,v in u.writes),'shared envelope must not retrigger effects'
z.call('_ay_update');assert [u.regs[i] for i in (8,9,10)]==[0,0,12]
z.call('_plat_tone',0x030a,14);assert u.regs[10]==12
z.call('_ay_update');assert [u.regs[i] for i in (8,9,10)]==[0,0,0]
print('PASS: independent bomb/death/step pitches and lifetimes; steps do not erase effects')
for mode in [0,1]:
 for behind in [3,4,5,6,20]:
  z=BankZX();z.poke(S('_net_active'),[mode]);now=z.read8(0x5c78);old=(now-behind)&255
  z.poke(S('_last_tick'),[old]);z.call('_plat_frame_sync')
  expected=(old+3)&255 if mode and behind<6 else now
  assert z.read8(S('_last_tick'))==expected,(mode,behind,z.read8(S('_last_tick')),expected)
print('PASS: preserves 60 ms clock phase, bounds catch-up, unchanged offline timing')
z=BankZX();z.poke(S('_net_active'),[1]);z.poke(S('_esp_defer_present'),[1]);z.poke(S('_last_tick'),[(z.read8(0x5c78)-3)&255])
z.poke(S('_draw_buf'),bytes([0x88])*1000);z.call('_tick_timers');assert z.read8(S('_draw_buf'))==0x88
z.poke(S('_net_active'),[0]);z.poke(S('_last_tick'),[(z.read8(0x5c78)-3)&255]);z.call('_tick_timers');assert z.read8(S('_draw_buf'))==32
print('PASS: defer presentation only during network gameplay, offline flush remains intact')
