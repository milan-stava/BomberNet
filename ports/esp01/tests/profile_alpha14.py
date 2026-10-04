"""Count actual Z80 work with frame pacing excluded, before/after alpha14."""
from pathlib import Path
import statistics,os
from test_bank128 import BankZX,UART,S
from zxemu import run_together
for ref in [os.environ.get('PROFILE_REFERENCE','build/alpha13-reference'),'build/esp01-128']:
 u=UART();u.payload=b'';z=BankZX(uart=u)
 z.write(24000,Path(ref,'bomber').read_bytes(),ram_page=0);z.pc=24000
 run_together([z],S('_flush_screen'),4);z.poke(S('_menu_mode'),[1]);z.poke(S('_menu_players'),[2]);z.press('SPACE');run_together([z],S('_flush_screen'),4);z.release('SPACE');run_together([z],S('_flush_screen'),4)
 z.poke(S('_outbuf'),b'host\0');assert z.call('_tcp_open',S('_outbuf'),80)==0;z.call('_frames_clear');z.poke(S('_ws_lost'),[0]);z.poke(S('_s_started'),[1]);z.poke(S('_plat_frame_sync'),b'\xc9');z.poke(S('_s_nbytes'),[4]);z.poke(S('_s_state'),[3]);z.poke(S('_s_slots'),[1]);z.poke(S('_s_full'),[1]);z.poke(S('_s_slot'),[0]);z.poke(S('_net_delay'),[2]);z.poke(S('_net_table'),[0,1,255,255]);z.poke(S('_menu_local'),[2]);z.poke(S('_ws_open_now'),[1]);u.raw=True;u.raw_delivered=True
 z.call('_net_match_start');z.poke(S('_hash_period'),[16]);z.call('_compute_state_hash')
 cycles=[]
 for i in range(80):
  t=z.now();z.call('_frame');cycles.append((z.now()-t)/3500)
 print(ref,'avg/max ms',statistics.mean(cycles),max(cycles),'normal/hash',[statistics.mean([x for i,x in enumerate(cycles) if (i+1)%16!=0]),statistics.mean([x for i,x in enumerate(cycles) if (i+1)%16==0])],flush=True)
 print('state',[(n,z.read8(S(n))) for n in ['_net_abort','_s_state','_ws_open_now','_ws_lost']],u.commands[-5:],flush=True);assert z.read8(S('_net_abort'))==0
