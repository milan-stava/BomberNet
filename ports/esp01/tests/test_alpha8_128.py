"""Regression checks on actual Z80 match-seeding and AY/beeper output."""
import statistics
from test_bank128 import BankZX, UART, S

def hashed(z):
    z.call('_compute_state_hash');return z.read16(S('_state_hash'))

def history():
    a,b=BankZX(),BankZX()
    a.poke(S('_hit_x'),[7,12]);b.poke(S('_hit_x'),[22,3])
    assert hashed(a)!=hashed(b),'history affects the hash before reset'
    for z in (a,b):
        z.call('_rng_seed',1234)
        assert z.read(S('_hit_x'),2)==bytes(2)
        assert z.read16(S('_rand_seed'))==1234
    assert hashed(a)==hashed(b)
    a.call('_rng_seed',0);assert a.read16(S('_rand_seed'))==1
    print('PASS: differing prior hit histories produce equal hashes after match seeding')

class Audio(UART):
    def __init__(self):super().__init__();self.edges=[];self.regs={};self.selected=0
    def output(self,p,v):
        if p&255==254:self.edges.append((self.now(),v))
        if p==0xfffd:self.selected=v
        if p==0xbffd:self.regs[self.selected]=v
        super().output(p,v)

def sound():
    u=Audio();z=BankZX(uart=u)
    for ratio in (0x0100,0x020a,0x030a,0x0a00,0x0d00,0x0232,0x0a32):
        z.poke(S('_net_active'),[0]);u.edges=[];z.call('_plat_tone',ratio,14)
        gaps=[b[0]-a[0] for a,b in zip(u.edges,u.edges[1:]) if (a[1]^b[1])&16 and b[0]-a[0]<10000]
        half=statistics.median(gaps);beeper=3500000/(2*half)
        z.poke(S('_net_active'),[1]);t=z.now();z.call('_plat_tone',ratio,14)
        assert z.now()-t<3500  # under 1 ms, including initial channel muting/interrupt
        period=u.regs[0]+256*u.regs[1];ay=1773400/(16*period)
        assert abs(ay/beeper-1)<.025,(hex(ratio),beeper,ay)
        assert u.regs[8]==12
    print('PASS: AY pitch within 2.5% of measured beeper; independent channel duration, nonblocking')

if __name__=='__main__':history();sound()

