"""Compatibility assembly link on the delivered alpha 7 images; normal source builds need none."""
from pathlib import Path
import re,sys,struct,subprocess,hashlib
sys.path.insert(0,'ports/esp01')
from bank_layout import symbols
D=Path('build/esp01-128');gm=symbols(D/'bomber.map');bm=symbols(D/'esp_bank.map')
game=bytearray((D/'bomber').read_bytes());bank=bytearray((D/'esp_bank').read_bytes())
assert hashlib.sha256(game).hexdigest()=='aa9236d6f56029321b39bb3e3cee6fb164b7cc64f667a161d603f14561522fff','requires delivered alpha 7 game'
assert hashlib.sha256(bank).hexdigest()=='3b7dfd573a2b15fe167fddaf1aded213b0cbd4f190ac2042ae79836af699a18a','requires delivered alpha 7 bank'
def asm(body,origin,m):
 defined=set(re.findall(r'^([\w]+):',body,re.M))
 equ=''.join('%s EQU %d\n'%(k,v) for k,v in m.items() if k not in defined and re.fullmatch(r'\w+',k) and 0<=v<=65535)
 Path('/tmp/a8.a80').write_text('    ORG %d\n    OUTPUT "/tmp/a8.bin"\n'%origin+equ+body+'\n    OUTEND\n')
 subprocess.run([sys.argv[1],'/tmp/a8.a80'],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
 return Path('/tmp/a8.bin').read_bytes()
def function(path,name):
 s=Path(path).read_text();a=s.index('__asm',s.index(name+'('))+len('__asm');return s[a:s.index('__endasm',a)]
def jump(img,base,at,to):img[at-base:at-base+3]=b'\xc3'+struct.pack('<H',to)
# Same RNG seed rule, plus reset of inactive hashed hit coordinates.
rng='''    pop af
    pop hl
    push hl
    push af
    ld a,h
    or l
    jr nz,rng_valid
    inc hl
rng_valid:
    ld (_rand_seed),hl
    xor a
    ld (_hit_x),a
    ld (_hit_y),a
    ret
'''
code=asm(rng,gm['_rng_seed'],gm);assert len(code)<=gm['_h8']-gm['_rng_seed']
game[gm['_rng_seed']-24000:gm['_h8']-24000]=code+bytes(gm['_h8']-gm['_rng_seed']-len(code))
# Preserve AY entry; use old function space plus a short continuation/table.
body=function('c/platform/zx/plat_zx.c','ay_tone');first,tail=body.split('ay_pitch_ready:')
origin=24000+len(game);tail=asm('ay_pitch_ready:'+tail,origin,gm)
gm['ay_pitch_ready']=origin;gm['ay_periods']=origin+len(tail)-32
first=asm(first+'    jp ay_pitch_ready\n',gm['_ay_tone'],gm)
assert len(first)<=gm['_ay_update']-gm['_ay_tone'],len(first)
game[gm['_ay_tone']-24000:gm['_ay_update']-24000]=first+bytes(gm['_ay_update']-gm['_ay_tone']-len(first))
game.extend(tail);assert 24000+len(game)<=0xfdff,(len(tail),hex(24000+len(game)))
# Hardware envelope ends each tone; frame sync only mutes when leaving network play.
update=asm("    ld a,(_ay_active)\n    or a\n    ret z\n    ld a,(_net_active)\n    or a\n    ret nz\n    ld hl,8\n    call _zx_ay\n    xor a\n    ld (_ay_active),a\n    ret\n",gm['_ay_update'],gm)
assert len(update)<=gm['_plat_frame_sync']-gm['_ay_update']
game[gm['_ay_update']-24000:gm['_ay_update']-24000+len(update)]=update
# LDIR receive with exact ring-boundary split; preserve bank bridge entries.
origin=0xc000+len(bank);code=asm(function('ports/esp01/tcp_esp_stream.c','tcp_recv'),origin,bm)
jump(bank,0xc000,bm['_tcp_recv'],origin);bank.extend(code)
assert 0xc000+len(bank)<=0xfdff
for name,img,base in [('bomber',game,24000),('esp_bank',bank,0xc000)]:
 (D/name).write_bytes(img);p=D/(name+'.map');s=p.read_text();s=re.sub(r'(__BSS_END_tail\s*= \$)[0-9A-Fa-f]+',lambda x:x[1]+'%04X'%(base+len(img)),s);p.write_text(s)
print('Alpha 8 linked: sound extension %d bytes; game end %04x; bank end %04x'%(len(tail),24000+len(game),0xc000+len(bank)))
