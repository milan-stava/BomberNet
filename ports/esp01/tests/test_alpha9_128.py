"""Native-Z80 regressions: parser fragmentation, multichannel AY and HUD colors."""
import random,struct,sys
from test_bank128 import BankZX,UART,S
from pathlib import Path

def frame(payload,op=1):
    return bytes([128|op,len(payload)])+payload if len(payload)<126 else bytes([128|op,126])+struct.pack('>H',len(payload))+payload

def ws_machine():
    u=UART();u.payload=b'';z=BankZX(uart=u);z.poke(0xc100,b'host\0');assert z.call('_tcp_open',0xc100,80)==0
    z.poke(S('_ws_open_now'),[1]);return z,u

def parser():
    z,u=ws_machine();rng=random.Random(9)
    for n in [0,1,2,63,64,125,126,159,160,255,300,511]*3:
        payload=bytes(rng.randrange(33,127) for _ in range(n));wire=frame(payload);got=0
        while wire:
            count=rng.randrange(1,32);part,wire=wire[:count],wire[count:];u.wire.extend(part)
            value=z.call('_ws_poll')
            if value:assert not wire;got=value
        assert got and z.read(got,min(n,159)+1)==payload[:159]+b'\0',(n,got)
    u.wire.extend(frame(b'one')+frame(b'two'))
    assert z.read(z.call('_ws_poll'),4)==b'one\0'
    assert z.read(z.call('_ws_poll'),4)==b'two\0'
    u.sent.clear();u.wire.extend(frame(b'ping',9));assert z.call('_ws_poll')==0
    assert bytes(u.sent).endswith(bytes.fromhex('8a8400000000')+b'ping'),bytes(u.sent)
    u.wire.extend(frame(b'',8));assert z.call('_ws_poll')==0 and z.read8(S('_ws_open_now'))==0
    print('PASS: short/extended/oversized fragmented text, batched frames, ping/pong and close')

class Audio(UART):
    def __init__(self):super().__init__();self.reg=0;self.v={}
    def output(self,p,v):
        if p==0xfffd:self.reg=v
        if p==0xbffd:self.v[self.reg]=v
        super().output(p,v)

def audio():
    u=Audio();z=BankZX(uart=u);z.poke(S('_net_active'),[1])
    z.call('_plat_tone',0x080a,12);bomb=(u.v[2],u.v[3])
    z.call('_plat_tone',0x0232,10);effect=(u.v[4],u.v[5])
    z.call('_plat_tone',0x020a,14)
    assert (u.v[2],u.v[3])==bomb and (u.v[4],u.v[5])==effect
    assert [u.v[i] for i in (8,9,10)]==[12]*3 and u.v[7]==0x38
    z.poke(S('_net_active'),[0]);z.call('_plat_frame_sync')
    assert [u.v[i] for i in (8,9,10)]==[0]*3
    print('PASS: steps, bombs and effects retain separate audible AY channels; all mute on exit')

def rtt():
    z=BankZX();p=S('_outbuf')
    for values in ([1,1,1,1],[2,2,2,2],[3,3,3,3],[16,16,16,16],[255,255,255,255]):
        z.poke(p,values);z.call('_lobby_apply_rtt',p,values[0])
        assert z.read8(S('_net_delay'))==max(2,min(8,(max(values)+1)//2))
    print('PASS: measured announced delay 2..8 frames, slower connections retain margin')

def hud():
    from test_alpha12_128 import hud as current_hud
    current_hud()

if __name__=='__main__':parser();audio();rtt();hud()

def equivalence():
    a=BankZX();b=BankZX();b.write(24000,Path('build/alpha8-reference/bomber').read_bytes(),ram_page=0)
    rng=random.Random(1289);times={k:[0,0,0] for k in ['_print_num5','_net_send','_net_poll']}
    def timed(name,args):
        t=a.now();ra=a.call(name,*args);ta=a.now()-t
        t=b.now();rb=b.call(name,*args);tb=b.now()-t
        times[name][0]+=ta;times[name][1]+=tb;times[name][2]+=1
        return ra,rb
    p=S('_outbuf')
    for v in [0,1,9,10,99,100,999,9999,10000,65535]+[rng.randrange(65536) for _ in range(100)]:
        timed('_print_num5',(p,v));assert a.read(p,6)==b.read(p,6),(v,a.read(p,6),b.read(p,6))
        a.call('_print_num4',p,v);b.call('_print_num4',p,v);assert a.read(p,5)==b.read(p,5)
    for frame in [0,1,15,16,255,65520,65534,65535]+[rng.randrange(65536) for _ in range(50)]:
        for n in [1,2,4]:
            base=(frame-rng.randrange(20))&65535;have=bytes([15]*16);data=rng.randbytes(256);key=rng.randbytes(4)
            for z in (a,b):
                z.poke(S('_s_state'),[3]);z.poke(S('_s_nbytes'),[n]);z.poke(S('_s_slots'),[4]);z.poke(S('_s_slot'),[1])
                z.poke(S('_s_base'),struct.pack('<H',base));z.poke(S('_have'),have);z.poke(S('_data'),data);z.poke(p,key)
                z.poke(S('_ws_open_now'),[0]);z.poke(S('_ws_lost'),[0])
            ra,rb=timed('_net_send',(frame,p));assert ra==rb,(ra,rb)
            assert a.read(S('_data'),256)==b.read(S('_data'),256)
            assert a.read(S('_have'),16)==b.read(S('_have'),16)
            assert a.read(S('_outbuf'),100)==b.read(S('_outbuf'),100)
            ra,rb=timed('_net_poll',(frame,p+128,p+132));assert ra==rb
            assert a.read(p+128,20)==b.read(p+128,20),(frame,base,n,a.read(p+128,20).hex(),b.read(p+128,20).hex())
            assert a.read16(S('_s_base'))==b.read16(S('_s_base'))
    for k,(new,old,count) in times.items():print('BENCH %s: %.3f -> %.3f CPU ms'%(k,old/count/3500,new/count/3500))
    print('PASS: optimized numbers and network vectors match alpha 8 at window/wrap boundaries')

if __name__=='__main__' and Path('build/alpha8-reference/bomber').exists():equivalence()

def recovery():
    values=[]
    for old in (True,False):
        u=UART();u.raw=True;u.payload=b'';z=BankZX(uart=u)
        if old:
            z.write(24000,Path('build/alpha8-reference/bomber').read_bytes(),ram_page=0)
            z.write(0xc000,Path('build/alpha8-reference/esp_bank').read_bytes(),ram_page=6)
        t=z.now();assert z.call('_tcp_present')==1 and not u.raw
        values.append((z.now()-t)/3500000)
    assert values[0]>10 and values[1]<3,values
    print('PASS: inherited transparent ESP recovery %.2f -> %.2f simulated seconds'%tuple(values))

if __name__=='__main__' and Path('build/alpha8-reference/esp_bank').exists():recovery()

def hud_speed():
    a=BankZX();b=BankZX();b.write(24000,Path('build/alpha8-reference/bomber').read_bytes(),ram_page=0)
    for count in (1,2,4):
        for z in (a,b):
            z.call('_clear_buffers');z.call('_players_setup',count)
            z.poke(S('_time_left'),struct.pack('<H',1000));z.poke(S('_stage'),[1])
        t=a.now();a.call('_draw_hud');new=a.now()-t
        t=b.now();b.call('_draw_hud');old=b.now()-t
        assert a.read(S('_draw_buf')+960,40)==b.read(S('_draw_buf')+960,40)
        print('BENCH %d-player HUD: %.3f -> %.3f CPU ms'%(count,old/3500,new/3500))

if __name__=='__main__' and Path('build/alpha8-reference/bomber').exists():hud_speed()

def players():
    a=BankZX();b=BankZX();b.write(24000,Path('build/alpha8-reference/bomber').read_bytes(),ram_page=0)
    rng=random.Random(991);ta=tb=0
    for mode in (0,1):
        for old in range(256):
            records=rng.randbytes(64);code=rng.randrange(256);idx=rng.randrange(4)
            for z in (a,b):
                z.poke(S('_players'),records);z.poke(S('_game_mode'),[mode]);z.poke(S('_outbuf'),[old])
            t=a.now();a.call('_put_player_char',S('_players')+idx*16,S('_outbuf'),code);ta+=a.now()-t
            t=b.now();b.call('_put_player_char',S('_players')+idx*16,S('_outbuf'),code);tb+=b.now()-t
            assert a.read(S('_players'),64)==b.read(S('_players'),64),(mode,old,idx)
            assert a.read8(S('_outbuf'))==b.read8(S('_outbuf'))==code
    print('PASS: all player/terrain collision cases preserve death/scoring; CPU %.3f -> %.3f ms'%(tb/512/3500,ta/512/3500))

if __name__=='__main__' and Path('build/alpha8-reference/bomber').exists():players()

def ws_speed():
    a=BankZX();b=BankZX();b.write(24000,Path('build/alpha8-reference/bomber').read_bytes(),ram_page=0)
    new=old=0
    for n in range(1,63):
        wire=frame(b'X'*n)
        for z in (a,b):
            z.poke(S('_ws_open_now'),[1]);z.poke(S('_f_state'),[0]);z.poke(S('_rx'),wire)
            z.poke(S('_rx_pos'),[0,len(wire)])
        t=a.now();ra=a.call('_ws_poll');new+=a.now()-t
        t=b.now();rb=b.call('_ws_poll');old+=b.now()-t
        assert ra==rb and a.read(ra,n+1)==b.read(rb,n+1)
    print('BENCH complete WS text: %.3f -> %.3f CPU ms'%(old/62/3500,new/62/3500))

if __name__=='__main__' and Path('build/alpha8-reference/bomber').exists():ws_speed()

def idle_rx():
    class Overflow(UART):
        def __init__(self):super().__init__();self.overflow=False;self.payload=b''
        def input(self,p):return 4 if p==0x133b and self.overflow else super().input(p)
        def output(self,p,v):
            if p==0x7d3b and v==1:self.overflow=False
            super().output(p,v)
    u=Overflow();z=BankZX(uart=u);p=0xc100;z.poke(p,b'host\0');assert z.call('_tcp_open',p,80)==0
    assert z.call('_tcp_recv',p,64)==0
    pages=len(z.pages);t=z.now()
    for _ in range(100):assert z.call('_tcp_recv',p,64)==0
    assert len(z.pages)==pages,'empty reads must avoid paging'
    print('BENCH cached empty RX %.3f CPU ms'%((z.now()-t)/100/3500))
    # send pumps incoming bytes into the hidden ring and invalidates the shortcut.
    u.wire.extend(b'ABCD');assert z.call('_tcp_send',p,0)==0
    assert z.call('_tcp_recv',p,64)==4 and z.read(p,4)==b'ABCD'
    assert z.call('_tcp_recv',p,64)==0
    u.wire.extend(b'EFGH');assert z.call('_tcp_recv',p,0)==0
    got=bytearray()
    for _ in range(10):
        n=z.call('_tcp_recv',p,64);assert n!=65535;got+=z.read(p,n)
        if len(got)==4:break
    assert got==b'EFGH','zero-capacity reads must not hide ring data'
    assert z.call('_tcp_recv',p,64)==0
    u.overflow=True
    assert z.call('_tcp_recv',p,64)==65535 and z.call('_tcp_error')==5
    print('PASS: idle RX skips paging; sends, zero-capacity reads and overflow retain correct behavior')

if __name__=='__main__':idle_rx()

