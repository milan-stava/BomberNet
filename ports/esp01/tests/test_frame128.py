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
