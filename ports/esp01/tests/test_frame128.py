"""Compare the fast frame compositor with the compiled general reference."""
import random
from test_bank128 import BankZX,S,D

def main():
    z=BankZX();rng=random.Random(0x128)
    legacy=[];fast=[]
    for case in range(8):
        # frame_common follows a flush: only the last HUD row has drawing.
        before=b' '*960+bytes(rng.randrange(256) for _ in range(40))
        layer=bytes(32 if rng.randrange(3) else rng.randrange(256) for _ in range(1000))
        z.poke(S('_map_layer'),layer);z.poke(S('_draw_buf'),before)
        start=z.now();z.call('_composite_map');legacy.append(z.now()-start)
        expected=z.read(S('_draw_buf'),1000)
        z.poke(S('_draw_buf'),before)
        start=z.now();z.call('_composite_frame');fast.append(z.now()-start)
        assert z.read(S('_draw_buf'),1000)==expected,case
        assert z.read(S('_map_layer'),1000)==layer
    old=sum(legacy)/len(legacy)/3500;new=sum(fast)/len(fast)/3500
    assert new<old*.65,(old,new)
    print('PASS: frame compositor matches reference; %.2fms -> %.2fms, %.2fx CPU speedup'%(old,new,old/new))
    (D/'frame-bench.txt').write_text('compositor CPU at 3.5MHz: %.2fms -> %.2fms (%.2fx)\n'%(old,new,old/new))
if __name__=='__main__':main()


def availability():
    rng=random.Random(0x4156);z=BankZX()
    for base in [0,1,15,16,65520,65534,65535]:
        for slots in [1,2,4]:
            for count in [0,1,4,16]:
                full=(1<<slots)-1
                have=bytearray(rng.randrange(full) for _ in range(16))
                for i in range(count):have[(base+i)&15]=full
                expected=bytearray(have);end=base
                while end!=65535 and expected[end&15]&full==full:
                    expected[end&15]=0;end+=1
                z.poke(S('_s_base'),base.to_bytes(2,'little'))
                z.poke(S('_s_slots'),[slots]);z.poke(S('_s_full'),[0])
                z.poke(S('_have'),have)
                result=z.call('_avail_frame')
                assert result==(end-1 if end else 65535)
                assert z.read16(S('_s_base'))==end
                assert z.read(S('_have'),16)==expected
    print('PASS: assembly availability scan matches reference at window/wrap boundaries')

if __name__=='__main__':availability()


def sound_and_reset():
    from test_bank128 import UART
    class AudioUART(UART):
        def __init__(self):super().__init__();self.ay=[]
        def output(self,p,v):
            if p in (0xfffd,0xbffd):self.ay.append((p,v))
            super().output(p,v)
    uart=AudioUART();z=BankZX(uart=uart)
    z.poke(S('_net_active'),[0]);t=z.now();z.call('_plat_tone',0x030a,14);old=z.now()-t
    z.poke(S('_net_active'),[1]);t=z.now();z.call('_plat_tone',0x030a,14);fast=z.now()-t
    assert fast<old*.2,(old,fast)
    assert uart.ay[-2:]==[(0xfffd,8),(0xbffd,12)]
    z.poke(S('_net_active'),[0]);z.call('_plat_frame_sync')
    assert uart.ay[-2:]==[(0xfffd,8),(0xbffd,0)]
    # Stage reset is the deathmatch respawn boundary, not every death.
    z.call('_players_setup',2);z.poke(S('_game_mode'),[1])
    p=S('_players');z.poke(p+3,[10,10,13]);z.poke(p+8,[1])
    z.call('_players_stage_reset')
    assert z.read8(p+5)==1 and z.read8(p+8)==0 and z.read8(p)==1
    z.call('_draw_players')
    assert z.read8(S('_draw_buf')+410) in z.read(p+12,2)
    # Field offsets follow player_t in game.h (all byte fields before score).
    print('PASS: network AY tone %.3fms instead of %.3fms; volume stops after match'%(fast/3500,old/3500))

if __name__=='__main__':sound_and_reset()
