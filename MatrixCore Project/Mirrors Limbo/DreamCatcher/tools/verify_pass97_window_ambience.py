from __future__ import annotations
import json, sys, wave
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

checks=[]
def check(name,cond,detail=''):
    checks.append(bool(cond)); print(('PASS' if cond else 'FAIL'),name,detail)

cfg=json.loads((ROOT/'data/window_audio.json').read_text())
events=cfg.get('events',{})
assets=[ROOT/p for p in events.get('assets',[])]
check('event layer enabled',events.get('enabled') is True)
check('four sparse event assets',len(assets)==4,str([p.name for p in assets]))
check('interval is sparse',float(events.get('min_interval',0))>=8 and float(events.get('max_interval',0))>=float(events.get('min_interval',0)),str((events.get('min_interval'),events.get('max_interval'))))
for p in assets:
    check(f'asset exists {p.name}',p.exists())
    if p.exists():
        with wave.open(str(p),'rb') as w:
            dur=w.getnframes()/float(w.getframerate())
            check(f'asset valid mono pcm {p.name}',w.getnchannels()==1 and w.getsampwidth()==2 and dur>1.5,f'{dur:.2f}s')

# Real Panda3D construction + event ownership.
sys.argv=[str(ROOT/'main.py'),'--headless']
import main
g=main.LockedHouseGame()
try:
    built=list(g.window_audio_sources.items())
    check('house window sources built',len(built)>=10,str(len(built)))
    check('all sources have one-shot bank',all(len(e.get('events',[]))==4 for _,e in built),str([len(e.get('events',[])) for _,e in built]))
    before=g.window_event_play_count
    g.window_event_timer=0.0
    g._update_window_audio_events(0.1)
    check('forced event selects one window',g.window_event_play_count==before+1,str((before,g.window_event_play_count,g.window_event_last_id)))
    first=g.window_event_last_id
    g.window_event_timer=0.0
    g._update_window_audio_events(0.1)
    check('consecutive event avoids same window',g.window_event_last_id!=first,str((first,g.window_event_last_id)))
    if first:
        g._set_window_boarded(first,True)
        g.window_event_last_id=None
        seen_boarded=False
        for _ in range(12):
            g.window_event_timer=0.0; g._update_window_audio_events(0.1)
            seen_boarded |= (g.window_event_last_id==first)
        check('boarded window excluded from random events',not seen_boarded,str(first))
    g.forest_active=True; before=g.window_event_play_count; g.window_event_timer=0.0; g._update_window_audio_events(0.1)
    check('forest suppresses house window events',g.window_event_play_count==before)
finally:
    try:g._runtime_cleanup()
    except Exception:pass
    try:g.destroy()
    except Exception:pass

print(f'PASS97_TOTAL={sum(checks)}/{len(checks)}')
raise SystemExit(0 if all(checks) else 1)
