"""Deterministic immediate-ESP UART microbenchmark of the compiled bank.
UART status gaps are retained; no remote server or host scheduling involved.
T-states include bridge, staging, parser and bank switch at 3.5MHz.
"""
import json
from test_bank128 import BankZX,D
results=[]
for size in [1,32,64,128,256,600]:
    z=BankZX();z.uart.payload=b'';z.poke(0xc100,b'host\0')
    assert z.call('_tcp_open',0xc100,65535)==0
    payload=(bytes(range(256))*3)[:size];z.poke(0xc100,payload)
    start=z.now();assert z.call('_tcp_send',0xc100,size)==0;ticks=z.now()-start
    assert z.uart.sent==payload
    results.append(dict(send_bytes=size,tstates=ticks,cpu_ms=ticks/3500))
baseline=json.loads((__import__('pathlib').Path(__file__).parent/'baseline128_bench.json').read_text())
for old,new in zip(baseline,results):
    assert old['send_bytes']==new['send_bytes']
    new['speedup']=old['tstates']/new['tstates']
    # Require a material improvement, using CPU instructions rather than relay latency.
    assert new['tstates']<old['tstates']*0.6,(old,new)
print('UART benchmark at 3.5MHz:',results)
(D/'bench.json').write_text(json.dumps(results,indent=2))
