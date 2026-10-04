"""Native alpha15 equivalence and first-key delay vs exact alpha14."""
import random,struct
from pathlib import Path
from test_bank128 import BankZX,UART,S

def pair():
 a,b=BankZX(),BankZX();b.write(24000,Path('build/alpha14-reference/bomber').read_bytes(),ram_page=0);return a,b

def hud():
 a,b=pair();r=random.Random(15)
 for case in range(256):
  count=1+case%4;records=r.randbytes(64);field=r.randbytes(1000);score=r.randrange(65536);time=r.randrange(65536)
  for z in [a,b]:
   z.poke(S('_players'),records);z.poke(S('_player_count'),[count]);z.poke(S('_game_mode'),[case&1]);z.poke(S('_draw_buf'),field);z.poke(S('_hi_score'),struct.pack('<H',score));z.poke(S('_time_left'),struct.pack('<H',time));z.poke(S('_stage'),[case]);z.poke(S('_enemies_left'),[case^31]);z.call('_draw_hud')
  assert a.read(S('_draw_buf'),1000)==b.read(S('_draw_buf'),1000),(case,'HUD bytes')
  assert a.read16(S('_hi_score'))==b.read16(S('_hi_score')),(case,'high score')
 print('PASS: 256 HUD states: 1-4 players, score/time extremes, modes, lives/wins and high-score update match alpha14')

def actors():
 a,b=pair();r=random.Random(1515)
 for case in range(768):
  players=bytearray(r.randbytes(64))
  for i in range(4):
   p=i*16;players[p]=r.randrange(2);players[p+2]=r.randrange(32);players[p+3]=r.randrange(1,38);players[p+4]=r.randrange(1,23);players[p+5]=r.choice([0,1,5,6,7,12,13,255]);players[p+7]=r.choice([0,1,2,3,4,254,255])
  field=bytes(r.choice([32]*8+[0x80,0x88,0x89,0xe0]) for _ in range(1000));counters=bytes([case%3,2]);positions=bytes([r.randrange(1,38),r.randrange(1,23)])
  for name in ['_players_anim_step','_check_pickups']:
   for z in [a,b]:
    z.poke(S('_net_active'),[1]);z.poke(S('_players'),players);z.poke(S('_draw_buf'),field);z.poke(S('_tmr_player_anim'),counters);z.poke(S('_game_mode'),[case&1]);z.poke(S('_exit_x'),positions);z.poke(S('_bonus_x'),positions if case%3==0 else players[3:5]);z.poke(S('_bonus_present'),[case&1]);z.poke(S('_exit_present'),[case&1]);z.poke(S('_exit_touched'),[0]);z.poke(S('_rand_seed'),struct.pack('<H',case+1));z.call(name)
   for n,k in [('_players',64),('_draw_buf',1000),('_bonus_present',1),('_exit_present',1),('_exit_touched',1),('_rand_seed',2)]:assert a.read(S(n),k)==b.read(S(n),k),(name,case,n)
 print('PASS: 1536 animation/movement/death/bonus/exit cases match alpha14 including score and RNG')

def empty():
 a,b=pair()
 for case in range(32):
  for name in ['_draw_bombs','_update_bombs','_draw_enemies','_enemy_ai']:
   for z in [a,b]:
    z.poke(S('_bombs'),bytes(40));z.poke(S('_enemies'),bytes(48));z.poke(S('_bomb_anim'),[case]);z.poke(S('_enemy_anim'),[case]);z.poke(S('_tmr_enemy_move'),[case%3,2]);z.call(name)
   for n,k in [('_bombs',40),('_enemies',48),('_bomb_anim',1),('_enemy_anim',1)]:assert a.read(S(n),k)==b.read(S(n),k),(name,case,n)
 # Exercise every fallback slot. Live bombs/enemies keep their original C path.
 for slot in range(8):
  for name,records,stride in [('_update_bombs','_bombs',5),('_draw_bombs','_bombs',5),('_draw_enemies','_enemies',6),('_enemy_ai','_enemies',6)]:
   for z in [a,b]:
    z.poke(S('_net_active'),[1]);z.poke(S('_bombs'),bytes(40));z.poke(S('_enemies'),bytes(48));z.poke(S(records)+slot*stride,bytes([1,5,5,2,3]+([0] if stride==6 else [])));z.poke(S('_draw_buf'),bytes([32])*1000);z.poke(S('_map_layer'),bytes([32])*1000);z.poke(S('_players'),bytes(64));z.poke(S('_bomb_anim'),[0]);z.poke(S('_enemy_anim'),[0]);z.poke(S('_tmr_enemy_move'),[0,2]);z.poke(S('_rand_seed'),b'\x34\x12');z.call(name)
   for n,k in [('_bombs',40),('_enemies',48),('_players',64),('_map_layer',1000),('_draw_buf',1000),('_bomb_anim',1),('_enemy_anim',1),('_rand_seed',2)]:assert a.read(S(n),k)==b.read(S(n),k),(name,slot,n)
 print('PASS: empty-list side effects and active-object fallbacks at all eight slots match alpha14')

def delay():
 for local in [0,1]:
  u=UART();u.payload=b'';z=BankZX(uart=u);p=S('_outbuf');z.poke(p,b'host\0');assert z.call('_tcp_open',p,80)==0
  for n,v in [('_net_delay',2),('_s_state',3),('_s_slot',local),('_s_slots',2),('_s_nbytes',4),('_s_full',3),('_menu_local',1),('_net_total',2),('_ws_open_now',1)]:z.poke(S(n),[v])
  z.call('_frames_clear');z.poke(S('_net_table'),[0,4,255,255]);z.poke(S('_menu_inputs'),[1,2,3,4]);z.call('_players_setup',2);z.call('_net_match_start');assert z.read8(S('_esp_input_delay'))==1
  # Exactly frame 0 is primed; frame 1 must not have a duplicate zero sample.
  assert z.read8(S('_have'))==1<<local and z.read8(S('_have')+1)==0
  z.press('P')
  for f in range(3):
   z.poke(S('_have')+f,[z.read8(S('_have')+f)|(1<<(1-local))]);z.poke(S('_data')+16*f+4*(1-local),bytes([8,0,0,0]));z.call('_net_lockstep_poll')
   assert z.read8(S('_players')+local*16+2)==(4 if f>=1 else 0),(local,f)
   assert z.read8(S('_players')+(1-local)*16+2)==8
   assert not z.read8(S('_net_abort'))
 for d in range(1,9):
  z.poke(S('_net_delay'),[d]);z.call('_esp_choose_delay');assert z.read8(S('_esp_input_delay'))==(1 if d==2 else d)
 print('PASS: HOST/JOIN first local key at frame 1 vs alpha14 frame 2; no duplicate primed input; slower-link delays retained')
if __name__=='__main__':hud();actors();empty();delay()
