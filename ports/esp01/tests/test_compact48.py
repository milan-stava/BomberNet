"""Compiled compact ESP backend on a 48K Spectrum with UART I/O simulation."""
import struct
from pathlib import Path
from test_bank128 import UART, ZX, sym_from_map
D=Path('build/esp01')
B=D/'bombernet_esp01_48_alpha1'
S=lambda name:sym_from_map(str(B)+'.map',name)
class CompactZX(ZX):
    def __init__(self, real=False, uart=None):
        self.uart=uart or UART(real)
        super().__init__()
        self.set_on_output_callback(self.output)
        self.load(B)
    def _input(self,port):
        value=self.uart.input(port)
        if value is not None:return value
        return super()._input(port)
    def output(self,port,value):self.uart.output(port,value)
    def call(self,name,*args):
        words=[0x4100,*reversed(args)]
        self.sp=0xfff0-len(words)*2
        self.poke(self.sp,b''.join(struct.pack('<H',x) for x in words))
        self.pc=S(name);before=self.sp
        self.run_until(0x4100,20)
        assert self.sp==before+2,(name,'stack')
        return self.hl

def test_api(modern=False, early_closed=False):
    uart=UART()
    if modern:
        original=uart.text
        import re
        uart.text=lambda text:original(re.sub(r"\+CIPRECVDATA,(\d+):",r"+CIPRECVDATA:\1,",text))
    z=CompactZX(uart=uart)
    # Loading the binary includes zeroed BSS; reset ROM has initialized FRAMES/IY.
    assert z.call('_tcp_present')==1
    z.poke(0x4000,b'api.mzpico.com\0')
    assert z.call('_tcp_open',0x4000,80)==0
    msg=bytes([0,1,62,13,10,255]);z.poke(0x4000,msg)
    assert z.call('_tcp_send',0x4000,len(msg))==0
    assert z.uart.sent==msg
    if early_closed: z.uart.text('CLOSED\r\n')
    got=bytearray()
    for _ in range(10000):
        n=z.call('_tcp_recv',0x4000,17)
        if n==65535:break
        assert n<=17
        got.extend(z.read(0x4000,n))
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
def test_faults():
    class FaultUART(UART):
        mode='at'
        def input(self,port):
            if self.mode=='fifo' and port==0x133b:return 4
            return super().input(port)
        def output(self,port,byte):
            if port==0x133b and byte==10 and not self.left:
                cmd=bytes(self.cmd)+bytes([byte])
                if self.mode=='timeout':self.cmd.clear();return
                if self.mode in ('query_error','missing_length') and cmd==b'AT+CIPRECVLEN?\r\n':
                    self.cmd.clear();self.text('ERROR\r\n' if self.mode=='query_error' else 'OK\r\n');return
            super().output(port,byte)
    for mode,error in [('fifo',5),('timeout',2)]:
        uart=FaultUART();uart.mode=mode;z=CompactZX(uart=uart)
        assert z.call('_tcp_present')==0
        assert z.call('_tcp_error')==error,(mode,z.call('_tcp_error'))
    for mode,error in [('query_error',1),('missing_length',4)]:
        uart=FaultUART();z=CompactZX(uart=uart)
        z.poke(0x4000,b'host\0');assert z.call('_tcp_open',0x4000,65535)==0
        assert 'AT+CIPSTART="TCP","host",65535' in uart.commands
        z.poke(0x4000,b'x');assert z.call('_tcp_send',0x4000,1)==0
        uart.mode=mode
        for _ in range(1000):
            if z.call('_tcp_recv',0x4000,17)==65535:break
        else:raise AssertionError(mode)
        assert z.call('_tcp_error')==error,(mode,z.call('_tcp_error'))
    print('PASS: compact UART full, bounded timeout, AT error, missing receive length')
if __name__=='__main__':
    test_api();test_api(modern=True,early_closed=True);test_faults();test_boot()

