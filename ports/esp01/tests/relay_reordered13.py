"""Test relay adapter: preserve protocol but reorder input JSON keys."""
import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[3]/'relay'))
import relay
send=relay.Conn.send
async def reordered_send(self,text):
 msg=json.loads(text)
 if msg.get('op')=='input':
  text=json.dumps(dict(op='input',frame=msg['frame'],data=msg['data'],slot=msg['slot']),separators=(',',':'))
 return await send(self,text)
relay.Conn.send=reordered_send
app=relay.app
