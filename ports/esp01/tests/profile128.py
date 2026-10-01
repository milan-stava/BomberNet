"""Profile compiled game routines using real Z80 instruction T-states.
Inclusive TCP/lockstep time can contain waiting for the local relay; frame
render/update self time and immediate-UART microbenchmarks isolate CPU work.
The emulator is accelerated: these are not physical server latency figures.
"""
import collections, json, runpy, sys
from pathlib import Path
import test_bank128 as base
from test_bank128 import S

names=['_plat_frame_sync','_flush_screen','_composite_map','_input_poll',
       '_net_lockstep_poll','_tcp_send','_tcp_recv','_net_send','_net_hash',
       '_update_bombs','_enemy_ai','_draw_players','_hash_frame_step']
entries={S(name):name for name in names}
instances=[]
class ProfileZX(base.BankZX):
    def __init__(self,*args,**kwargs):
        self.tracked=[];self.stats=collections.defaultdict(list);self.enabled=False
        super().__init__(*args,**kwargs)
        for addr in entries:self.set_breakpoint(addr)
        instances.append(self)
    def on_breakpoint(self):
        super().on_breakpoint()
        if not self.enabled:
            if self.read8(S('_net_active')) and not self.read8(S('_title_mode')):self.enabled=True
            else:return
        now=self.now()
        while self.tracked and self.pc==self.tracked[-1]['ret'] and self.sp==self.tracked[-1]['sp']+2:
            item=self.tracked.pop();duration=now-item['start']
            self.stats[item['name']].append((duration,duration-item['child']))
            if self.tracked:self.tracked[-1]['child']+=duration
        if self.read8(0x5b5c)&7==6:return
        if self.pc in entries:
            ret=self.read16(self.sp);self.set_breakpoint(ret)
            self.tracked.append(dict(name=entries[self.pc],ret=ret,sp=self.sp,start=now,child=0))
base.BankZX=ProfileZX
sys.argv=['match128.py','90']
try:runpy.run_path('ports/esp01/tests/match128.py',run_name='__main__')
except SystemExit as e:
    if e.code:raise
reports=[]
for z in instances:
    stats={name:dict(calls=len(values),inclusive_ms=sum(v[0] for v in values)/len(values)/3500,
                    self_ms=sum(v[1] for v in values)/len(values)/3500)
           for name,values in z.stats.items() if values}
    reports.append(stats)
Path('build/esp01-128/profile.json').write_text(json.dumps(reports,indent=2))
print('PROFILE (mean Z80 ms at 3.5MHz; network routines may include waiting):')
for name in names:
    v=reports[0].get(name)
    if v:print('%-22s %3d calls total %7.2f self %7.2f'%(name,v['calls'],v['inclusive_ms'],v['self_ms']))
