"""Reproduce the delivered alpha 6 recovery overlay on CI run 36942743981.

Run from repository root with the SjASMPlus 1.20.3 executable as argv[1].
The normal z88dk build already includes this source change and needs no overlay.
This linker preserves all existing bridge entries and adds the same assembly
recovery function from tcp_esp_fast.c. Then run pack_game128.py --prepare,
assemble loader128.a80 in build/esp01-128, and run pack_game128.py.
"""
import hashlib
from pathlib import Path
import sys,subprocess,re,struct
sys.path.insert(0,'ports/esp01')
from bank_layout import symbols
D=Path('build/esp01-128');m=symbols(D/'esp_bank.map');bank=bytearray((D/'esp_bank').read_bytes())
assert hashlib.sha256(bank).hexdigest() == '3558b76045401d0528869c5ceb8108606a2b87c46c13c5095c3680186d3b527e', 'requires unmodified CI bank from run 36942743981'
origin=0xc000+len(bank);assert origin==m['__BSS_END_tail']
start=m['es_present_probe'];end=m['es_present_ok']
needle=bytes.fromhex('013b70');hits=[i for i in range(start-0xc000,end-0xc000) if bank[i:i+3]==needle];assert len(hits)==1
hook=hits[0]+0xc000
source=Path('ports/esp01/tcp_esp_fast.c').read_text();routine=source[source.index('es_escape_unknown:'):source.index('; Wait for DE ROM ticks;')]
asm='    ORG %d\n    OUTPUT "/tmp/recovery.bin"\n'%origin
for name in ['es_pause','es_deadline','es_write','es_tick','es_clear','es_drain','es_crlf','es_start','es_pump','es_error','es_txptr','es_at','es_command','es_present_ok']:
 asm+='%s EQU %d\n'%(name,m[name])
asm+='''recovery_entry:
    call es_escape_unknown
    or a
    jr nz,recovery_power
    ld hl,es_at
    call es_command
    or a
    jp z,es_present_ok
recovery_power:
    ld bc,0x703b
    jp %d
'''%(hook+3)
asm+=routine+'    OUTEND\n';Path('/tmp/recovery.a80').write_text(asm)
subprocess.run([sys.argv[1],'/tmp/recovery.a80'],check=True)
extra=Path('/tmp/recovery.bin').read_bytes();bank[hook-0xc000:hook-0xc000+3]=b'\xc3'+struct.pack('<H',origin);bank.extend(extra)
assert 0xc000+len(bank)<=0xfdff
(D/'esp_bank').write_bytes(bank)
s=(D/'esp_bank.map').read_text();s=re.sub(r'(__BSS_END_tail\s*= \$)[0-9A-Fa-f]+',lambda x:x[1]+'%04X'%(0xc000+len(bank)),s);s+='\nlocal_recovery_entry = $%04X ; addr, local\n'%origin;(D/'esp_bank.map').write_text(s)
print('Linked recovery from source: %d bytes; preserved entry addresses, ring and BSS; hook %04x'%(len(extra),hook))
