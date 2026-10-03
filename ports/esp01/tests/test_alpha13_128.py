"""Run UI offline starts after every abort class and compare the original HUD."""
from pathlib import Path
from test_bank128 import BankZX,S
from zxemu import run_together

def offline():
 for reason in [0,4,5,7,9]:
  z=BankZX();z.pc=24000
  run_together([z],S('_flush_screen'),4)
  # Reproduce a prior online failure, with the title already returned.
  z.poke(S('_net_abort'),[reason]);z.poke(S('_net_waiting'),[1]);z.poke(S('_hash_period'),[16])
  z.press('SPACE');run_together([z],S('_flush_screen'),4)
  z.release('SPACE');run_together([z],S('_flush_screen'),8)
  assert z.read8(S('_title_mode'))==0,(reason,'returned to title')
  for name in ['_net_active','_net_abort','_net_waiting','_hash_period']:
   assert z.read8(S(name))==0,(reason,name,z.read8(S(name)))
  # Clear only the test corridor so an initial direction cannot meet a brick.
  z.poke(S('_map_layer'),bytes([32])*1000);z.poke(S('_players')+3,[5,5])
  z.press('P');run_together([z],S('_flush_screen'),12)
  assert z.read8(S('_players')+3)>5 and z.read8(S('_title_mode'))==0
  assert z.read8(S('_net_abort'))==0
 print('PASS: actual title -> offline match -> movement after DESYNC, drop, BREAK and timeout; stale hashing/wait flags cleared')

def hud():
 for count in [1,2,3,4]:
  a,b=BankZX(),BankZX();b.write(24000,Path('build/alpha11-reference/bomber').read_bytes(),ram_page=0)
  for z in [a,b]:
   z.poke(S('_player_count'),[count]);z.poke(S('_title_mode'),[0]);z.poke(S('_net_active'),[1])
   z.call('_clear_buffers');z.poke(S('_draw_buf')+960,bytes([0x92,0xae])+bytes([32])*38)
   z.call('_flush_screen')
  assert a.read(0x4000,6912)==b.read(0x4000,6912),count
  assert a.read8(S('_zx_bar_attr'))&0x38==0x18
 print('PASS: original purple HUD, pixels and attributes identical to alpha11 for 1/2/3/4 players')
if __name__=='__main__':offline();hud()
