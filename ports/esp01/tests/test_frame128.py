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
