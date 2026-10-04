"""Stable HUD colors and no intermediate attribute writes on native Z80."""
from pathlib import Path
from test_bank128 import BankZX,S
class TraceZX(BankZX):
 def __init__(self):
  self.expected=None;self.attr_writes=[];self.trapped=set();super().__init__()
  data=Path('build/esp01-128/bomber').read_bytes()
  # Trap all LD (HL),A instructions in the renderer plus new HUD helper.
  for lo,hi in [(S('_flush_screen'),0xc1b3),(0xaed6,0xaf48)]:
   for addr in range(lo,hi):
    if data[addr-24000]==0x77:self.set_breakpoint(addr);self.trapped.add(addr)
 def on_breakpoint(self):
  if self.pc in self.trapped and self.expected is not None and 0x5ae1<=self.hl<0x5aff:
   value=self.af>>8;want=self.expected[self.hl-0x5ae1]
   assert value==want,('temporary HUD attribute',hex(self.pc),hex(self.hl),value,want)
   self.attr_writes.append((self.hl,value))
  super().on_breakpoint()
def expected(z,count):
 base=z.read8(S('_zx_bar_attr'))&0xf8;out=[base]*30
 segments=[] if count==1 else [(0,2,7,2),(9,3,17,2)] if count==2 else [(0,1,6,2),(9,1,15,2),(18,1,24,2)] if count==3 else [(0,1,5,2),(7,2,12,3),(15,1,20,2)]+([(22,2,27,3)] if count==4 else [])
 for i,(label,n,life,m) in enumerate(segments):
  color=base|(z.read8(S('_player_attrs')+i)&7)
  out[label:label+n]=[color]*n;out[life:life+m]=[color]*m
 return out
def hud():
 for online in [0,1]:
  for count in [1,2,3,4]:
   z=TraceZX();z.poke(S('_player_count'),[count]);z.poke(S('_title_mode'),[0]);z.poke(S('_net_active'),[online]);z.call('_clear_buffers')
   for i in range(4):z.poke(S('_players')+16*i+9,[3]);z.poke(S('_players')+16*i+10,(1234+i).to_bytes(2,'little'))
   z.call('_draw_hud');z.call('_flush_screen');want=expected(z,count)
   assert list(z.read(0x5ae1,30))==want,(online,count,list(z.read(0x5ae1,30)),want)
   if online:z.screenshot('build/esp01-128/hud17-%d.png'%count)
   z.expected=want
   # Changed scores, lives/wins and time force actual HUD bitmap redraws.
   for mode in [0,1]:
    for score in [0,9,10,99,100,999,1000,65535]:
     z.poke(S('_game_mode'),[mode]);z.poke(S('_time_left'),score.to_bytes(2,'little'))
     for i in range(4):z.poke(S('_players')+16*i+9,[score%10]);z.poke(S('_players')+16*i+15,[score%7]);z.poke(S('_players')+16*i+10,score.to_bytes(2,'little'))
     z.call('_draw_hud');z.call('_flush_screen');assert list(z.read(0x5ae1,30))==want
   assert not z.attr_writes,('unchanged attributes should never be rewritten',online,count,z.attr_writes)
 print('PASS: 1-4 player HUD in online/offline modes; player labels and life/win groups stable; aligned three-player score and time black')
 print('PASS: changed HUD glyphs never write temporary attributes; stable attributes are not rewritten')
def scene():
 for title in [0,1]:
  a,b=BankZX(),BankZX();b.write(24000,Path('build/alpha16-reference/bomber').read_bytes(),ram_page=0)
  for z in [a,b]:
   z.poke(S('_title_mode'),[title]);z.poke(S('_player_count'),[2]);z.call('_clear_buffers')
   z.poke(S('_draw_buf'),bytes([32,0xc0,0xe0,0x80])*230+bytes([32])*80)
   z.call('_draw_hud');z.call('_flush_screen')
  assert a.read(0x4000,6144)==b.read(0x4000,6144),('pixels',title)
  assert a.read(0x5800,736)==b.read(0x5800,736),('field attributes',title)
  if title:assert a.read(0x5ae0,32)==b.read(0x5ae0,32),'title attributes'
 print('PASS: exact alpha16 pixels and playfield attributes; title rendering unchanged')
def aligned():
 for mode in [0,1]:
  for score in [0,9,10,999,9999,65535]:
   a,b=BankZX(),BankZX();b.write(24000,Path('build/alpha16-reference/bomber').read_bytes(),ram_page=0)
   for z in [a,b]:
    z.poke(S('_player_count'),[3]);z.poke(S('_game_mode'),[mode]);z.poke(S('_title_mode'),[0]);z.call('_clear_buffers');z.poke(S('_time_left'),(1000).to_bytes(2,'little'))
    for i in range(3):
     z.poke(S('_players')+16*i+9,[i+1]);z.poke(S('_players')+16*i+15,[i+4]);z.poke(S('_players')+16*i+10,score.to_bytes(2,'little'))
    z.call('_draw_hud')
   new=a.read(S('_draw_buf')+960,40);old=b.read(S('_draw_buf')+960,40)
   for i in range(3):
    assert new[12*i]==old[10*i]
    assert new[12*i+2:12*i+7]==old[10*i+2:10*i+7]
    assert new[12*i+8:12*i+10]==old[10*i+7:10*i+9]
   assert a.read16(S('_hi_score'))==b.read16(S('_hi_score'))
   assert new[35:]==bytes([0x30,1,0,0,0]),new
   a.call('_flush_screen');base=a.read8(S('_zx_bar_attr'))&0xf8
   for i in range(3):
    for cell in range(12*i+2,12*i+7):
     # Every pixel column occupied by a score glyph lies in black ink.
     for x in range(cell*6,cell*6+6):assert a.read8(0x5ae1+x//8)==base,(mode,score,i,x)
   for x in range(35*6,40*6):assert a.read8(0x5ae1+x//8)==base
 print('PASS: all three-player score/time glyph columns black; complete life/win groups colored, unchanged score digits and high-score values')
def unchanged():
 import random
 r=random.Random(17)
 for count in [1,2,4]:
  a,b=BankZX(),BankZX();b.write(24000,Path('build/alpha16-reference/bomber').read_bytes(),ram_page=0)
  for case in range(128):
   players=r.randbytes(64);field=r.randbytes(1000);time=r.randrange(65536);hi=r.randrange(65536)
   for z in [a,b]:
    z.poke(S('_players'),players);z.poke(S('_draw_buf'),field);z.poke(S('_player_count'),[count]);z.poke(S('_game_mode'),[case%2]);z.poke(S('_time_left'),time.to_bytes(2,'little'));z.poke(S('_hi_score'),hi.to_bytes(2,'little'));z.call('_draw_hud')
   assert a.read(S('_draw_buf'),1000)==b.read(S('_draw_buf'),1000),(count,case)
   assert a.read16(S('_hi_score'))==b.read16(S('_hi_score'))
 print('PASS: 384 randomized one/two/four-player HUD layouts match exact alpha16')
if __name__=='__main__':hud();scene();aligned();unchanged()
