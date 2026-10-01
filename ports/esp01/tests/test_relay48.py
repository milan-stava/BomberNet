"""Compiled game's WebSocket handshake/create/close through UART + local relay."""
import os, socket, subprocess, sys, time
from pathlib import Path
from test_compact48 import CompactZX as BankZX, D, S, B

def main():
    log=open(D/'relay-test.log','w')
    env=dict(os.environ,TCP_PORT='8766')
    server=subprocess.Popen([sys.executable,'-m','uvicorn','relay:app','--app-dir','relay','--host','127.0.0.1','--port','8765','--log-level','warning'],stdout=log,stderr=log,env=env)
    try:
        for _ in range(200):
            try:
                s=socket.create_connection(('127.0.0.1',8765),timeout=.1);s.close();break
            except OSError: time.sleep(.025)
        else:raise AssertionError('relay did not start')
        z=BankZX(real=True);z.pc=24000;z.run_until(S('_flush_screen'),20)
        assert z.read8(S('_net_device'))==3
        # Pointers above C000 exercise actual game variables in the caller bank.
        settings=S('_outbuf');code=S('_net_code');slot=S('_net_slot')
        z.poke(settings,b'\x01\x02')
        # Use the documented build id in this exact build.
        build=S('BUILD_ID') if 'BUILD_ID' in Path(str(B)+'.map').read_text() else 0x0604
        result=z.call('_net_create',build,2,settings,2,code,slot)
        assert result==0, ('create',result,z.uart.commands[-8:])
        room=z.read(code,4).decode();assert len(room)==4 and room.isalpha()
        assert z.read8(slot)==0
        assert z.call('_tcp_error')==0
        z.call('_net_leave')
        subprocess.run([sys.executable,'ports/esp01/tests/match48.py','60'],check=True,timeout=180)
        print('PASS: real game WebSocket handshake, relay room creation %s, 48K pointers and leave'%room)
    finally:
        server.terminate()
        try:server.wait(timeout=3)
        except subprocess.TimeoutExpired:server.kill();server.wait()
        log.close()

if __name__=='__main__':main()
