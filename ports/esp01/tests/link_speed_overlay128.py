"""Link alpha 7 assembly changes into the tested alpha 6 images, preserving entries.
Run from repository root with SjASMPlus 1.20.3 executable as argv[1].
Normal source builds include the same changes without this compatibility link.
"""
from pathlib import Path
import sys,re,subprocess,struct,hashlib
sys.path.insert(0,'ports/esp01')
from bank_layout import symbols
D=Path('build/esp01-128');gm=symbols(D/'bomber.map');bm=symbols(D/'esp_bank.map')
game=bytearray((D/'bomber').read_bytes());bank=bytearray((D/'esp_bank').read_bytes())
assert hashlib.sha256(bank).hexdigest()=='2c81c8fbf14c01a49c66ce98b7e746ecdb251aa0e163fe61ac514d9b04e7f8d3', 'requires the alpha 6 reference images'
assert hashlib.sha256(game).hexdigest()=='2e8b3cec2c47ccd7a9fa976192ad7206908d45a6e75b2f59e0bc75e116160dea', 'requires the alpha 6 reference images'

def asm(body,origin,m):
    defined=set(re.findall(r'^([\w]+):',body,re.M))
    body=re.sub(r'^\s*__(?:end)?asm;?\s*$', '',body,flags=re.M)
    equ=''.join('%s EQU %d\n'%(k,v) for k,v in m.items() if k not in defined and re.fullmatch(r'\w+',k) and 0<=v<=65535)
    Path('/tmp/speed.a80').write_text('    ORG %d\n    OUTPUT "/tmp/speed.bin"\n'%origin+equ+body+'\n    OUTEND\n')
    subprocess.run([sys.argv[1],'/tmp/speed.a80'],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    return Path('/tmp/speed.bin').read_bytes()
def function(path,name):
    s=Path(path).read_text();a=s.index('__asm',s.index(name+'('))+len('__asm');return s[a:s.index('__endasm',a)]
def put(body,start,end,m,image,base):
    code=asm(body,start,m);assert len(code)<=end-start,(hex(start),len(code),end-start)
    image[start-base:end-base]=code+bytes(end-start-len(code));return start+len(code)
def jump(image,base,at,target):image[at-base:at-base+3]=b'\xc3'+struct.pack('<H',target)

bridge=Path('ports/esp01/tcp_bank128.c').read_text()
gm['ESP_SEND']=bm['_tcp_send'];gm['ESP_RECV']=bm['_tcp_recv']
sendend=put(function('ports/esp01/tcp_bank128.c','tcp_send'),gm['_tcp_send'],gm['_tcp_recv'],gm,game,24000)
recvend=put(function('ports/esp01/tcp_bank128.c','tcp_recv'),gm['_tcp_recv'],gm['_tcp_close'],gm,game,24000)
# The existing AY implementation retains its address and body. Redirect its
# first division step to the pitch mapping followed by the same shift.
pitch='''    ld a,h
    cp 2
    jr nz,pitch_div
    ld a,l
    cp 10
    jr nz,pitch_div
    ld l,0x8a
pitch_div:
    srl h
    rr l
    ret
'''
pitchend=put(pitch,recvend,gm['_tcp_close'],gm,game,24000)
pos=game.index(bytes.fromhex('cb3ccb1d'),gm['_ay_tone']-24000,gm['_ay_update']-24000)
game[pos:pos+4]=b'\xcd'+struct.pack('<H',recvend)+b'\x00'
# Clear only HUD during a net playfield frame; general/title paths clear all.
clear='''    ld b,125
    ld a,(_net_active)
    or a
    ret z
    ld a,(_title_mode)
    or a
    ret nz
    ld b,5
    ret
'''
pos=gm['fz_clr']-24000-2
assert game[pos-3:pos+2]==bytes.fromhex('212020067d')
# CALL helper sets HL=2020 and chooses the clear length; entry addresses stay fixed.
clear=clear.replace('    ld b,125','    ld hl,0x2020\n    ld b,125',1)
clearend=put(clear,sendend,gm['_tcp_recv'],gm,game,24000)
game[pos-3:pos+2]=b'\xcd'+struct.pack('<H',sendend)+b'\x00\x00'

s=Path('ports/esp01/tcp_esp_stream.c').read_text()
for name,body in [('tcp_send',function('ports/esp01/tcp_esp_stream.c','tcp_send')),('stream_pump',s[s.index('stream_pump:'):s.index('stream_receive_mode:')])]:
    at=0xc000+len(bank);code=asm(body,at,bm);bank.extend(code)
    jump(bank,0xc000,bm['_tcp_send'] if name=='tcp_send' else bm['stream_pump'],at)
# z88dk ALIGN applies within a section, so use the page-aligned address inside
# allocated padding for both pointers and wrapping (exactly 4096 bytes).
old=b'\x21'+struct.pack('<H',bm['stream_rx']);new=b'\x21'+struct.pack('<H',bm['stream_rx']&0xff00)
assert bank.count(old)==1;bank=bank.replace(old,new)
assert 0xc000+len(bank)<=0xfdff
# Reuse space freed by the assembly bridge; only the 45-byte slice table
# extends game allocation. This preserves more stack space than appending code.
body=function('c/core/game.c','hash_frame_step')
fast,table=body.split('hf_slices:')
at=24000+len(game)
gm['hf_slices']=at;gm['_hash_frame_step_general']=pitchend
put(fast,clearend,gm['_tcp_recv'],gm,game,24000)
general='    ld de,(_frame_no)\n    jp %d\n'%(gm['_hash_frame_step']+4)
put(general,pitchend,gm['_tcp_close'],gm,game,24000)
table=asm('hf_slices:'+table,at,gm)
assert len(table)==45 and at+len(table)<=0xfdff
entry=gm['_hash_frame_step']-24000
assert game[entry:entry+4]==b'\xed\x5b'+struct.pack('<H',gm['_frame_no'])
game[entry:entry+4]=b'\xc3'+struct.pack('<H',clearend)+b'\x00'
game.extend(table)
s=(D/'bomber.map').read_text()
s=re.sub(r'(__BSS_END_tail\s*= \$)[0-9A-Fa-f]+',lambda x:x[1]+'%04X'%(24000+len(game)),s)
s+='\n_hash_frame_step_general = $%04X ; addr, public\n'%pitchend
(D/'bomber.map').write_text(s)
(D/'bomber').write_bytes(game);(D/'esp_bank').write_bytes(bank)
s=(D/'esp_bank.map').read_text();s=re.sub(r'(__BSS_END_tail\s*= \$)[0-9A-Fa-f]+',lambda x:x[1]+'%04X'%(0xc000+len(bank)),s);(D/'esp_bank.map').write_text(s)
print('Speed link: bridge, pitch, HUD clear, register TX/RX pump; bank bytes',len(bank))
