"""Bounded UART burst checks against the compiled fast 128K driver."""
from test_bank128 import UART, BankZX

class BusyUART(UART):
    def __init__(self):super().__init__();self.tx_wait=0
    def input(self,port):
        value=super().input(port)
        if port==0x133b and self.tx_wait:
            self.tx_wait-=1;value|=2
        return value
    def output(self,port,byte):
        if port==0x133b:
            assert not self.tx_wait,'driver wrote while TX busy'
            super().output(port,byte);self.tx_wait=2
        else:super().output(port,byte)

class FaultUART(UART):
    mode='normal'
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

def busy_send():
    uart=BusyUART();z=BankZX(uart=uart);z.poke(0xc100,b'host\0')
    assert z.call('_tcp_open',0xc100,80)==0
    payload=bytes(range(256))*2+bytes(range(88));z.poke(0xc100,payload)
    assert z.call('_tcp_send',0xc100,len(payload))==0
    assert uart.sent==payload
    assert z.call('_tcp_error')==0
    print('PASS: bounded command/payload bursts preserve every byte under TX backpressure')

def faults():
    for mode,error in [('fifo',5),('timeout',2)]:
        uart=FaultUART();uart.mode=mode;z=BankZX(uart=uart)
        assert z.call('_tcp_present')==0
        assert z.call('_tcp_error')==error,(mode,z.call('_tcp_error'))
    for mode,error in [('query_error',1),('missing_length',4)]:
        uart=FaultUART();z=BankZX(uart=uart)
        z.poke(0xc100,b'host\0');assert z.call('_tcp_open',0xc100,65535)==0
        assert 'AT+CIPSTART="TCP","host",65535' in uart.commands
        z.poke(0xc100,b'x');assert z.call('_tcp_send',0xc100,1)==0
        uart.mode=mode
        # An empty/unknown notification requires the defensive length query.
        # Known +IPD lengths now bypass it.
        from zxemu import sym_from_map
        from pathlib import Path
        uart.wire.clear()
        addr=sym_from_map(Path('build/esp01-128/esp_bank.map'),'es_ready')
        z.write(addr,b'\0',ram_page=6)
        addr=sym_from_map(Path('build/esp01-128/esp_bank.map'),'es_pending')
        z.write(addr,b'\1',ram_page=6)
        for _ in range(1000):
            if z.call('_tcp_recv',0xc100,17)==65535:break
        else:raise AssertionError(mode)
        assert z.call('_tcp_error')==error,(mode,z.call('_tcp_error'))
    print('PASS: fast bank UART full, bounded timeout, query errors, framing checks')
if __name__=='__main__':busy_send();faults()
