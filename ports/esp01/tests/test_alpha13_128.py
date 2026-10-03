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
 from test_alpha14_128 import hud as current_hud
 current_hud()
if __name__=='__main__':offline();hud()
