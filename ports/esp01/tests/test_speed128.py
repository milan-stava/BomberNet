"""Alpha 7: exact UART data, full RX ring, pixel equivalence and AY pitch."""
import random,sys
from pathlib import Path
from test_bank128 import BankZX,S,UART
sys.path.insert(0,'ports/esp01')
from bank_layout import symbols

def renderer():
    # Compare against the previous linked image, using the same source maps.
    ref=Path(sys.argv[1]);old=ref.joinpath('bomber').read_bytes();m=symbols(ref/'bomber.map')
    rng=random.Random(7);a=BankZX();b=BankZX();b.write(24000,old,ram_page=0)
    for title,net in [(1,0),(0,0),(0,1)]:
        for z in (a,b):
            z.poke(S('_title_mode'),[title]);z.poke(S('_net_active'),[net]);z.call('_clear_buffers')
        for frame in range(6):
            tiles=bytearray(b' '*1000)
            for i in range(35):tiles[rng.randrange(1000)]=rng.randrange(256)
            for z in (a,b):z.poke(S('_draw_buf'),tiles)
            t=a.now();a.call('_flush_screen');fast=a.now()-t
            t=b.now();b.call('_flush_screen');legacy=b.now()-t
            assert a.read(0x4000,6912)==b.read(0x4000,6912),(title,net,frame)
            assert a.read(S('_shadow_vram'),960)==b.read(S('_shadow_vram'),960)
            if net and not title:
                assert a.read(S('_draw_buf')+960,40)==b' '*40
                assert fast<legacy
            else:assert a.read(S('_draw_buf'),1000)==b.read(S('_draw_buf'),1000)
    print('PASS: title/local/network pixels identical; network clear saves %.2f ms'%((legacy-fast)/3500))

def full_ring():
    class Flood(UART):
        def __init__(self):super().__init__();self.payload=b''
    u=Flood();z=BankZX(uart=u);z.poke(0xc100,b'host\0');assert z.call('_tcp_open',0xc100,80)==0
    data=bytes(range(256))*16;u.wire.extend(data)
    for i in range(32):assert z.call('_tcp_send',0xc100,0)==0
    got=bytearray()
    for i in range(300):
        n=z.call('_tcp_recv',0xc100,17);assert n!=65535;got+=z.read(0xc100,n)
        if len(got)==len(data):break
    assert got==data,(len(got),len(data))
    z.call('_tcp_close');print('PASS: exactly full 4096-byte ring retains every byte before drain')

def sound():
    class AY(UART):
        def __init__(self):super().__init__();self.reg=0;self.v={}
        def output(self,p,v):
            if p==0xfffd:self.reg=v
            if p==0xbffd:self.v[self.reg]=v
            super().output(p,v)
    u=AY();z=BankZX(uart=u);z.poke(S('_net_active'),[1])
    for ratio,period in [(0x020a,0x028a>>3),(0x030a,0x030a>>3),(0x0100,0x0100>>3)]:
        z.call('_plat_tone',ratio,14);assert u.v[0]+256*u.v[1]==period
    print('PASS: high footstep period 65 -> 81; other tested pitches unchanged')

if __name__=='__main__':renderer();full_ring();sound()

def hash_slices():
    old=Path(sys.argv[1],'bomber').read_bytes();a=BankZX();b=BankZX();b.write(24000,old,ram_page=0)
    rng=random.Random(16);oldtime=[];newtime=[]
    for period in [1,2,7,16,32]:
        for frame in list(range(1,36))+[65534,65535,0]:
            layer=bytes(rng.randrange(256) for _ in range(1000))
            for z in (a,b):
                z.poke(S('_map_layer'),layer);z.poke(S('_hash_period'),[period]);z.poke(S('_frame_no'),frame.to_bytes(2,'little'))
            t=a.now();a.call('_hash_frame_step');fast=a.now()-t
            t=b.now();b.call('_hash_frame_step');legacy=b.now()-t
            for name in ['_map_acc','_hh','_state_hash']:assert a.read16(S(name))==b.read16(S(name)),(period,frame,name)
            if period==16 and frame%16:newtime.append(fast);oldtime.append(legacy)
    print('PASS: all hash slices match general reference incl wrap; regular slice %.2f -> %.2f ms'%(sum(oldtime)/len(oldtime)/3500,sum(newtime)/len(newtime)/3500))
if __name__=='__main__':hash_slices()
