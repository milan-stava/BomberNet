"""Raw UART WebSocket transport: bounded TX/RX, ring wrap and mode recovery."""
from test_bank128 import BankZX,UART,D,STREAM
from test_fast128 import busy_send,old_application

class RingUART(UART):
    def __init__(self):
        super().__init__();self.payload=b'';self.source=bytes(range(256))*40;self.offset=0
    def poll(self):
        if self.raw and self.raw_delivered and not self.wire and self.offset<len(self.source):
            self.wire.extend(self.source[self.offset:self.offset+256]);self.offset+=256

def ring():
    u=RingUART();z=BankZX(uart=u);z.poke(0xc100,b'host\0')
    assert z.call('_tcp_open',0xc100,80)==0
    z.poke(0xc100,b'x');assert z.call('_tcp_send',0xc100,1)==0
    got=bytearray()
    for _ in range(10000):
        n=z.call('_tcp_recv',0xc100,17)
        assert n!=65535
        got.extend(z.read(0xc100,n))
        if len(got)==len(u.source):break
    else:raise AssertionError('ring drain stalled')
    assert got==u.source
    assert not any(c.startswith('AT+CIPSEND=') or c.startswith('AT+CIPRECV') and c.endswith('?') for c in u.commands)
    assert z.call('_tcp_error')==0
    z.call('_tcp_close');assert not u.raw
    assert z.call('_tcp_open',0xc100,80)==0
    print('PASS: 10KB binary RX ring wraps, bounded FIFO batches, raw transfer and command-mode reconnect')

if __name__=='__main__':
    assert STREAM
    busy_send();old_application();ring()
