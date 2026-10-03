"""Execute parser ordering and whole-label HUD regressions on native Z80."""
import itertools,json
from test_bank128 import BankZX,S

def parser():
 z=BankZX();p=S('_outbuf')
 for frame in [0,1,15,16,255,256,65530]:
  for slot in range(4):
   for keys in ['00000000','01020408','10000000','abcdef01']:
    msg=dict(op='input',frame=frame,slot=slot,data=keys)
    for order in itertools.permutations(msg):
     for sep in [(',',':'),(', ',': ')]:
      z.poke(S('_s_base'),frame.to_bytes(2,'little'));z.poke(S('_have'),bytes(16));z.poke(S('_data'),bytes([0x55])*256)
      z.poke(p,json.dumps({k:msg[k] for k in order},separators=sep).encode()+b'\0')
      z.call('_handle_line',p)
      idx=frame&15
      assert z.read8(S('_have')+idx)==1<<slot,(frame,slot,order)
      expected=bytearray([0x55]*256);expected[idx*16+slot*4:idx*16+slot*4+4]=bytes.fromhex(keys)
      assert z.read(S('_data'),256)==expected,(frame,slot,order,sep)
 print('PASS: 5376 input layouts: all JSON key orders, zero/movement/bomb keys, every slot, window indices and whitespace')

def hud():
 from test_alpha13_128 import hud as current_hud
 current_hud()
if __name__=='__main__':parser();hud()
