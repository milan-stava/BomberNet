"""Deterministic WebSocket relay after lobby, with UART and network time in Z80 cycles.

One-way delay includes ESP packetization/network time. UART TX and RX are each
serialized at 115200 baud, 8N1. No dependence on wall-clock server scheduling.
"""
import collections,json,struct
from test_bank128 import S
from zxemu import sym_from_map
class TimedLink:
 def __init__(self,a,b,delay_ms):
  self.z=[a,b];self.start=[a.now(),b.now()];self.delay=delay_ms*3500
  self.log=[]
  self.byte_ticks=round(3500000*10/115200);self.tx=[bytearray(),bytearray()]
  self.rx=[collections.deque(),collections.deque()];self.busy=[0,0];self.last_rx=[0,0]
  for i,z in enumerate(self.z):
   u=z.uart;u.sock.close();u.sock=None
   u.wire.clear()
   for name in ('_rx_pos','_rx_len','_f_state','_ws_lost'):z.poke(S(name),[0])
   bm=lambda n:sym_from_map('build/esp01-128/esp_bank.map',n)
   for name in ('stream_head','stream_tail'):z.write(bm(name),(bm('stream_rx')&0xff00).to_bytes(2,'little'),ram_page=6)
   z.write(bm('stream_count'),bytes(2),ram_page=6)
   u.input=lambda port,i=i:self.input(i,port)
   u.output=lambda port,value,i=i:self.output(i,port,value)
  print('handoff',[(z.read16(S('_net_frame')),z.read16(S('_s_base')),z.read8(S('_net_delay') if z.reference else S('_esp_input_delay')),z.read8(S('_s_slot'))) for z in self.z],flush=True)
  # Replay previously sent but not yet consumed input vectors across the
  # transport handoff; their payloads remain in each sender's 16-frame ring.
  for i,z in enumerate(self.z):
   peer=1-i;receiver=self.z[peer]
   delay=z.read8(S('_net_delay') if z.reference else S('_esp_input_delay'))
   for frame in range(receiver.read16(S('_s_base')),z.read16(S('_net_frame'))+delay):
    data=z.read(S('_data')+(frame&15)*16+i*4,4).hex()
    payload=json.dumps(dict(op='input',frame=frame,slot=i,data=data),separators=(',',':')).encode()
    receiver.uart.wire.extend(bytes([129,len(payload)])+payload)
 def now(self,i):return self.z[i].now()-self.start[i]
 def input(self,i,port):
  u=self.z[i].uart
  while self.rx[i] and self.rx[i][0][0]<=self.now(i):u.wire.append(self.rx[i].popleft()[1])
  if port==0x133b:return int(bool(u.wire))|(2 if self.now(i)<self.busy[i] else 0)
  if port==0x143b:return u.wire.popleft()
  if port==0x773b:return 0x30
  if port==0x713b:return 1
  return None
 def output(self,i,port,v):
  if port!=0x133b:return
  assert self.now(i)>=self.busy[i],'write while hardware TX busy'
  self.busy[i]=self.now(i)+self.byte_ticks
  t=self.tx[i];t.append(v)
  if len(t)<2:return
  n=t[1]&127;h=2
  if n==126:
   if len(t)<4:return
   n=int.from_bytes(t[2:4],'big');h=4
  if len(t)<h+4+n:return
  op=t[0]&15;key=t[h:h+4];payload=bytes(c^key[k&3] for k,c in enumerate(t[h+4:h+4+n]));t.clear()
  assert op==1,(i,'unexpected op',op,payload,self.now(i),self.log[:5],self.log[-5:],[(z.read16(S('_net_frame')),z.read16(S('_s_base')),z.read8(S('_net_abort')),z.read(S('_have'),16).hex()) for z in self.z])
  msg=json.loads(payload)
  if msg['op']!='input':return
  self.log.append((i,msg['frame'],self.now(i)))
  msg=dict(op='input',frame=msg['frame'],slot=i,data=msg['data'])
  payload=json.dumps(msg,separators=(',',':')).encode()
  wire=bytes([129,len(payload)])+payload if len(payload)<126 else bytes([129,126])+struct.pack('>H',len(payload))+payload
  peer=1-i;due=max(self.busy[i]+self.delay,self.last_rx[peer])
  for c in wire:
   due+=self.byte_ticks;self.rx[peer].append((due,c))
  self.last_rx[peer]=due
