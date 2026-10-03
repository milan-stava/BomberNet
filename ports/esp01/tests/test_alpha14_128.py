"""Native Z80 renderer/timer equivalence and label-only HUD attributes."""
import random
from pathlib import Path
from test_bank128 import BankZX,S

def pair():
 a,b=BankZX(),BankZX();b.write(24000,Path('build/alpha13-reference/bomber').read_bytes(),ram_page=0);return a,b

def core():
 a,b=pair();rng=random.Random(14)
 for code in range(256):
  for name in ['_put_tile','_fill_2x2']:
   for z in [a,b]:z.poke(S('_draw_buf'),bytes([32])*1000);z.call(name,S('_draw_buf')+200,code)
   assert a.read(S('_draw_buf'),1000)==b.read(S('_draw_buf'),1000)
 for period in [0,1,2,3,4,10,20,254,255]:
  for counter in range(256):
   for z in [a,b]:z.poke(S('_tmr_time'),[counter,period]);z.call('_tick_timer',S('_tmr_time'))
   assert a.read(S('_tmr_time'),2)==b.read(S('_tmr_time'),2),(counter,period)
 for case in range(2048):
  field=bytes(rng.choice([32]*12+[0xc0,0xe0,0xff,0x88]) for _ in range(1000));records=bytearray(rng.randbytes(64))
  for i in range(4):
   p=i*16;records[p]=rng.randrange(2);records[p+3]=rng.randrange(1,38);records[p+4]=rng.randrange(1,23);records[p+5]=rng.choice([0,1,2,5,6,7,12,13,255]);records[p+8]=rng.randrange(2)
  for z in [a,b]:
   z.poke(S('_draw_buf'),field);z.poke(S('_players'),records);z.poke(S('_game_mode'),[case&1]);z.poke(S('_bombs'),bytes(48));z.call('_draw_players')
  assert a.read(S('_draw_buf'),1000)==b.read(S('_draw_buf'),1000),(case,'pixels')
  assert a.read(S('_players'),64)==b.read(S('_players'),64),(case,'players')
 for case in range(128):
  records=bytearray(rng.randbytes(64))
  for i in range(4):
   p=i*16;records[p]=rng.randrange(2);records[p+3]=rng.randrange(1,38);records[p+4]=rng.randrange(1,23);records[p+5]=rng.randrange(14);records[p+8]=rng.randrange(2)
  attrs=rng.randbytes(768)
  for z in [a,b]:z.poke(0x5800,attrs);z.poke(S('_players'),records);z.call('_players_death_colour')
  assert a.read(0x5800,768)==b.read(0x5800,768),(case,'death colours')
 print('PASS: death colours match in 128 mixed active/dead/lost-player cases')
 print('PASS: 512 tile writes, 2304 timer edges, 2048 four-player render/collision/death/scoring cases match alpha13')

def hud():
 for count in [1,2,3,4]:
  z=BankZX();z.poke(S('_player_count'),[count]);z.poke(S('_title_mode'),[0]);z.poke(S('_net_active'),[1]);z.call('_clear_buffers')
  # Use the real HUD builder and score fields, not synthetic pixel patterns.
  for i in range(4):z.poke(S('_players')+16*i+10,(1234+i).to_bytes(2,'little'))
  z.call('_draw_hud');z.call('_flush_screen')
  attrs=list(z.read(0x5ae1,30));base=z.read8(S('_zx_bar_attr'))&0xf8;expected=[base]*30
  inks=z.read(S('_player_attrs'),4)
  segments=[] if count==1 else [(0,2),(9,3)] if count==2 else [(0,1),(7,2),(15,1)]+([(22,2)] if count==4 else [])
  for i,(p,n) in enumerate(segments):expected[p:p+n]=[base|(inks[i]&7)]*n
  assert attrs==expected,(count,attrs,expected)
  assert base&0x38==0x18
  z.screenshot('build/esp01-128/hud14-%d.png'%count)
 print('PASS: purple HUD; only P1/P2 or compact digits colored, all scores/lives/time black; one player all black')
if __name__=='__main__':core();hud()
