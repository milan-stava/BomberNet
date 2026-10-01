import re, sys
from pathlib import Path
for filename in sys.argv[1:]:
    text = Path(filename).read_text()
    symbols = dict((m[0], int(m[1],16)) for m in re.findall(r'^([^\s]+)\s+= \$([0-9A-Fa-f]+)', text, re.M))
    print(filename)
    for key in ['__head','__tail','__CODE_head','__CODE_tail','__RODATA_head','__RODATA_tail','__DATA_head','__DATA_tail','__BSS_head','__BSS_tail']:
        if key in symbols: print('%s: %d (0x%04x)' % (key, symbols[key], symbols[key]))
    end = symbols.get('__BSS_tail', symbols.get('__tail'))
    if end is not None: print('Free below SP=65535: %d bytes' % (65535-end))
