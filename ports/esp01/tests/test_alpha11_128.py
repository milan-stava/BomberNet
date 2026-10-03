"""Reference comparisons and negotiation regressions on executed Z80 code."""
import json,random,struct
from pathlib import Path
from test_bank128 import BankZX,UART,S,D

def pair():
 a,b=BankZX(),BankZX()
 b.write(24000,Path('build/alpha10-reference/bomber').read_bytes(),ram_page=0)
 return a,b

def cpu():
 a,b=pair();rng=random.Random(11);times={n:[0,0,0] for n in ['_put_u','_h8','_move_player','_hash_frame_step']}
 def run(n,*args):
  ret=[]
  for i,z in enumerate((a,b)):
   t=z.now();ret.append(z.call(n,*args));times[n][i]+=z.now()-t
  times[n][2]+=1;return ret
 p=S('_outbuf')
 for v in [0,1,9,10,99,100,999,1000,9999,10000,65535]+[rng.randrange(65536) for _ in range(300)]:
  for z in (a,b):z.poke(p,b'?'*8)
  ra,rb=run('_put_u',p,v)
  assert ra==rb and a.read(p,8)==b.read(p,8)
 for v in range(256):
  hh=rng.randrange(65536)
  for z in (a,b):z.poke(S('_hh'),struct.pack('<H',hh))
  run('_h8',v);assert a.read16(S('_hh'))==b.read16(S('_hh'))
 for case in range(512):
  field=bytes(rng.choice([32]*16+[0x80,0x88,0x89,0xc0,0xe0]) for _ in range(1000))
  pl=bytearray(16);pl[0]=1;pl[2]=case&31;pl[3]=rng.randrange(1,38);pl[4]=rng.randrange(1,22);pl[6]=case&2
  for z in (a,b):
   z.poke(S('_players'),pl);z.poke(S('_draw_buf'),field);z.poke(S('_net_active'),[1])
  run('_move_player',S('_players'));assert a.read(S('_players'),16)==b.read(S('_players'),16),(case,pl.hex())
 for frame in range(1,33):
  for z in (a,b):z.poke(S('_frame_no'),struct.pack('<H',frame));z.poke(S('_hash_period'),[16])
  run('_hash_frame_step');assert a.read16(S('_state_hash'))==b.read16(S('_state_hash'))
 report={n:{'old_ms':old/count/3500,'new_ms':new/count/3500} for n,(new,old,count) in times.items()}
 print('PASS: decimal output, 256 hash bytes, 512 movement/collision cases and state hashes match alpha10')
 print(json.dumps(report,indent=2));(D/'alpha11-cpu.json').write_text(json.dumps(report,indent=2))

def negotiation():
 z=BankZX();fromp=S('_outbuf');datap=fromp+8
 def receive(slot,payload):
  z.poke(S('_ws_open_now'),[0]);z.poke(S('_ws_lost'),[0])
  z.poke(S('_mq_head'),[1]);z.poke(S('_mq_tail'),[0]);z.poke(S('_msgq'),bytes([slot,len(payload)])+payload.ljust(32,b'\0'))
  assert z.call('_net_msg_recv',fromp,datap)==len(payload)
  assert z.read8(fromp)==slot and z.read(datap,len(payload))==payload
 for kind in (1,2,4):
  for slot in range(4):
   z.poke(S('_esp_peer_fast'),[0]);z.poke(S('_esp_peer_legacy'),[0]);receive(slot,bytes([kind,42]))
   assert z.read8(S('_esp_peer_legacy'))==1<<slot and z.read8(S('_esp_peer_fast'))==0
   receive(slot,bytes([kind,42,0x45,11]));assert z.read8(S('_esp_peer_fast'))==1<<slot
 for payload in [b'',b'\1',b'\5\0',b'\1\0\x45',b'\1\0\x45\xff',b'\1\0\x45\x0b\0']:
  z.poke(S('_esp_peer_fast'),[0]);z.poke(S('_esp_peer_legacy'),[0]);receive(1,payload)
  assert z.read8(S('_esp_peer_fast'))==z.read8(S('_esp_peer_legacy'))==0
 for slot in [0,1]:
  other=1<<(1-slot)
  for delay in range(2,9):
   for members,slots in [(2,2),(3,3),(4,4)]:
    for legacy,fast in [(0,0),(other,0),(0,other),(other,other)]:
     for name,v in [('_net_delay',delay),('_s_members',members),('_s_slots',slots),('_s_slot',slot),('_esp_peer_legacy',legacy),('_esp_peer_fast',fast)]:z.poke(S(name),[v])
     z.call('_esp_choose_delay')
     expected=delay
     assert z.read8(S('_esp_input_delay'))==expected
 z.poke(S('_net_device'),[0]);z.call('_room_request',datap)
 assert not z.read8(S('_esp_peer_fast')) and not z.read8(S('_esp_peer_legacy'))
 print('PASS: legacy/enhanced/unknown peers, HOST/JOIN, conservative multi-peer and slow-link fallback, room reset')

def websocket_send():
 u=UART();u.payload=b'';z=BankZX(uart=u);p=S('_outbuf')+8
 z.poke(p,b'host\0');assert z.call('_tcp_open',p,80)==0
 for n in [0,1,125,126,159,160,161,256]:
  payload=bytes(i&255 for i in range(n));z.poke(p,payload);u.sent.clear()
  r=z.call('_send_frame',1,p,n)
  if n>160:assert r==11 and not u.sent;continue
  header=bytes([0x81,0x80|n])+bytes(4) if n<126 else bytes([0x81,0xfe,n>>8,n&255])+bytes(4)
  assert r==0 and bytes(u.sent)==header+payload,(n,r,bytes(u.sent).hex())
 z.poke(S('_s_state'),[2]);z.poke(S('_ws_open_now'),[1])
 for payload in [b'\1\x2a',b'\2\x2a',b'\4\1',b'\3\2',b'\x55\x12',b'\1']:
  src=S('_draw_buf');z.poke(src,payload);u.sent.clear();assert z.call('_net_msg_send',255,src,len(payload))==0
  msg=json.loads(bytes(u.sent)[6:]);expected=payload+(b'\x45\x0b' if len(payload)==2 and payload[0] in (1,2,4) else b'')
  assert msg==dict(op='msg',to=-1,data=expected.hex())
  assert z.read(src,len(payload))==payload
 print('PASS: WebSocket short/extended lengths, max-length rejection and channel framing')

def input_timing():
 for enhanced,delay in [(False,2),(True,2)]:
  u=UART();u.payload=b'';z=BankZX(uart=u);p=S('_outbuf')
  z.poke(p,b'host\0');assert z.call('_tcp_open',p,80)==0
  for name,v in [('_ws_open_now',1),('_s_state',3),('_s_slot',0),('_s_slots',2),('_s_members',2),('_s_nbytes',4),('_s_full',3),('_net_delay',2),('_menu_local',1),('_net_total',2),('_esp_peer_fast',2 if enhanced else 0),('_esp_peer_legacy',0 if enhanced else 2)]:z.poke(S(name),[v])
  z.poke(S('_s_base'),bytes(2));z.poke(S('_have'),bytes(16));z.poke(S('_data'),bytes(256));z.poke(S('_net_table'),bytes([0,4,255,255]));z.poke(S('_menu_inputs'),bytes([1,2,3,4]))
  z.call('_players_setup',2);z.call('_net_match_start');assert z.read8(S('_esp_input_delay'))==delay
  z.press('P')
  for f in range(3):
   z.poke(S('_have')+f,[z.read8(S('_have')+f)|2]);z.poke(S('_data')+f*16+4,bytes([8,0,0,0]))
   z.call('_net_lockstep_poll')
   assert z.read8(S('_net_abort'))==0
   assert z.read8(S('_players')+2)==(4 if f>=delay else 0),(enhanced,f)
   assert z.read8(S('_players')+18)==8
  z.poke(S('_net_abort'),[9]);old=z.read16(S('_net_frame'));z.call('_net_lockstep_poll')
  assert z.read16(S('_net_frame'))==old and all(z.read8(S('_players')+i*16+2)==0 for i in range(4))
 print('PASS: local key acts at the shared announced frame for legacy and enhanced peers; peer keys and abort clearing preserved')

if __name__=='__main__':
 if Path('build/alpha10-reference/bomber').exists():cpu()
 negotiation();websocket_send();input_timing()
