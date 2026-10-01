"""Compiled compact ESP backend on a 48K Spectrum with UART I/O simulation."""
import struct
from pathlib import Path
from test_bank128 import UART, ZX, sym_from_map
D=Path('build/esp01')
B=D/'bombernet_esp01_48_alpha1'
S=lambda name:sym_from_map(str(B)+'.map',name)
class CompactZX(ZX):
    def __init__(self, real=False):
        self.uart=UART(real)
        super().__init__()
        self.set_on_output_callback(self.output)
        self.load(B)
    def _input(self,port):
        value=self.uart.input(port)
        if value is not None:return value
        return super()._input(port)
    def output(self,port,value):self.uart.output(port,value)
    def call(self,name,*args):
        words=[0x5b0f,*reversed(args)]
        self.sp=0xfff0-len(words)*2
        self.poke(self.sp,b''.join(struct.pack('<H',x) for x in words))
        self.pc=S(name);before=self.sp
        self.run_until(0x5b0f,20)
        assert self.sp==before+2,(name,'stack')
        return self.hl

def test_api():
    z=CompactZX()
    # Loading the binary includes zeroed BSS; reset ROM has initialized FRAMES/IY.
    assert z.call('_tcp_present')==1
    z.poke(0x5b10,b'api.mzpico.com\0')
    assert z.call('_tcp_open',0x5b10,80)==0
    msg=bytes([0,1,62,13,10,255]);z.poke(0x5b10,msg)
    assert z.call('_tcp_send',0x5b10,len(msg))==0
    assert z.uart.sent==msg
    got=bytearray()
    for _ in range(10000):
        n=z.call('_tcp_recv',0x5b10,17)
        if n==65535:break
        assert n<=17
        got.extend(z.read(0x5b10,n))
    else:raise AssertionError('receive never ended')
    assert got==z.uart.payload,(len(got),len(z.uart.payload))
    assert z.call('_tcp_error')==0 and z.call('_tcp_peer_closed')==1
    assert z.call('_tcp_read_commands')==10
    z.call('_tcp_close')
    print('PASS: compact Z80 UART driver, binary stream, fragmented headers, clean close')

def test_boot():
    z=CompactZX();z.run_until(S('_flush_screen'),20)
    assert z.read8(S('_net_device'))==3
    for _ in range(5):z.run_until(S('_flush_screen'),20)
    z.screenshot(D/'title48.png')
    print('PASS: 48K game boots and detects ESP')
if __name__=='__main__':test_api();test_boot()
