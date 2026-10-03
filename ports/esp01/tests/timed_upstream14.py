"""Cycle-timed asymmetric TCP delivery, including serial UART, against original ZX."""
import collections,json,struct,random
from zxemu import sym_from_map
class Link:
 def __init__(self,clients,delay):
  self.cs=clients;self.start=[c.z.now() for c in clients];self.delay=delay*3500
  self.rx=[collections.deque(),collections.deque()];self.tx=[bytearray(),bytearray()];self.last=[0,0];self.busy=0;self.bt=304;self.rng=random.Random(14);self.hashes={};self.mism=[];self.inputs=0
  for i,c in enumerate(clients):
   z=c.z
   for n in ['_rx_pos','_rx_len','_f_state','_ws_lost']:c.wr(n,[0])
   if c.original:
    for sock in z.socks.values():sock.close()
    old=z._sn_call
    def call(i=i,z=z,old=old):
     if z.ix==0x3e12:
      self.feed(i,z.read(z.de,z.bc));z._sn_return(bc=z.bc)
     elif z.ix==0x3e24:z._sn_return(zero=not self.ready(i),bc=(z.bc&0xff00)|(4 if self.ready(i) else 0))
     elif z.ix==0x3e15:
      data=bytearray()
      while self.ready(i) and len(data)<min(z.bc,7):data.append(self.rx[i].popleft()[1])
      z.poke(z.de,data);z._sn_return(bc=len(data))
     else:old()
    z._sn_call=call
   else:
    u=z.uart;u.sock.close();u.sock=None;u.wire.clear()
    bm=lambda n:sym_from_map('build/esp01-128/esp_bank.map',n)
    for n in ['stream_head','stream_tail']:z.write(bm(n),(bm('stream_rx')&0xff00).to_bytes(2,'little'),ram_page=6)
    z.write(bm('stream_count'),bytes(2),ram_page=6)
    u.input=lambda p,i=i:self.input(i,p)
    u.output=lambda p,v,i=i:self.output(i,p,v)
  # Preserve all in-flight priming/player inputs across the transport handoff.
  for i,c in enumerate(clients):
   slot=i if clients[0].r('_menu_net')==1 else 1-i
   peer=clients[1-i]
   for f in range(peer.r16('_s_base'),c.r16('_net_frame')+c.r('_net_delay')):
    msg=dict(op='input',frame=f,slot=slot,data=c.z.read(c.s('_data')+(f&15)*16+slot*4,4).hex())
    self.queue(1-i,json.dumps(msg,separators=(',',':')).encode(),0)
 def now(self,i):return self.cs[i].z.now()-self.start[i]
 def ready(self,i):return bool(self.rx[i] and self.rx[i][0][0]<=self.now(i))
 def input(self,i,p):
  if p==0x133b:return int(self.ready(i))|(2 if self.now(i)<self.busy else 0)
  if p==0x143b:return self.rx[i].popleft()[1]
  if p==0x773b:return 0x30
  if p==0x713b:return 1
  return None
 def output(self,i,p,v):
  if p==0x133b:self.busy=self.now(i)+self.bt;self.feed(i,bytes([v]))
 def queue(self,i,payload,due):
  wire=bytes([129,len(payload)])+payload if len(payload)<126 else bytes([129,126])+struct.pack('>H',len(payload))+payload
  due=max(due,self.last[i])
  for b in wire:
   due+=self.bt if not self.cs[i].original else 20
   self.rx[i].append((due,b))
  self.last[i]=due
 def feed(self,i,raw):
  t=self.tx[i];t.extend(raw)
  while len(t)>=2:
   n=t[1]&127;h=2
   if n==126:
    if len(t)<4:return
    n=int.from_bytes(t[2:4],'big');h=4
   if len(t)<h+4+n:return
   key=t[h:h+4];p=bytes(x^key[k&3] for k,x in enumerate(t[h+4:h+4+n]));del t[:h+4+n]
   
   try:m=json.loads(p)
   except Exception:raise AssertionError((i,p.hex(),self.inputs,[(c.r16('_net_frame'),c.r('_net_abort')) for c in self.cs]))
   if m['op']=='hash':
    hashes=self.hashes.setdefault(m['frame'],{});hashes[i]=m['hash']
    if len(hashes)==2 and hashes[0]!=hashes[1]:self.mism.append(m['frame'])
   if m['op']!='input':continue
   self.inputs+=1
   slot=i if self.cs[0].r('_menu_net')==1 else 1-i
   m=dict(op='input',frame=m['frame'],slot=slot,data=m['data'])
   # TCP keeps byte order; jitter may batch deliveries but never reorders them.
   self.queue(1-i,json.dumps(m,separators=(',',':')).encode(),self.now(i)+self.delay+(0 if i==0 else self.delay//2)+self.rng.randrange(0,40)*3500)
