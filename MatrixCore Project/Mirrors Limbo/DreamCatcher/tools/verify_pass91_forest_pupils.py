from __future__ import annotations
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.argv=[str(ROOT/'main.py'),'--headless','--no-audio']
import main

checks=[]
def check(name, cond, detail=''):
    ok=bool(cond); checks.append((name,ok,detail)); print(('PASS' if ok else 'FAIL'), name, detail)
    return ok

g=main.LockedHouseGame()
try:
    g.forest_task.update({'state':'active','choice':None,'completion_count':0})
    g._enter_forest()
    check('two pupil nodes', len(g.forest_pupil_nodes)==2, str(len(g.forest_pupil_nodes)))
    initial=[p.getScale() for p in g.forest_pupil_nodes]
    check('pupils start beady', all(p.x <= .011 and p.z <= .010 for p in initial), str(initial))
    g._forest_start_question()
    for _ in range(18): g._update_forest_encounter(.1)
    middle=[p.getScale() for p in g.forest_pupil_nodes]
    check('question grows pupils', all(m.x > i.x and m.z > i.z for i,m in zip(initial,middle)), f'{initial} -> {middle}')
    for _ in range(20): g._update_forest_encounter(.1)
    question_late=[p.getScale() for p in g.forest_pupil_nodes]
    check('question growth remains bounded', all(.025 < p.x < .0365 for p in question_late), str(question_late))
    g._forest_choose(False)
    for _ in range(25): g._update_forest_encounter(.1)
    final=[p.getScale() for p in g.forest_pupil_nodes]
    check('punishment reaches Alternate-sized pupils', all(abs(p.x-.036)<.0015 and abs(p.z-.028)<.0015 for p in final), str(final))
    check('pupils remain dark', all(p.getColor().x <= .01 for p in g.forest_pupil_nodes), str([p.getColor() for p in g.forest_pupil_nodes]))
    g._reset_forest_encounter()
    reset=[p.getScale() for p in g.forest_pupil_nodes]
    check('reset restores beady pupils', all(p.x <= .011 and p.z <= .010 for p in reset), str(reset))
finally:
    try: g._runtime_cleanup()
    except Exception: pass
    try: g.destroy()
    except Exception: pass
fails=[x for x in checks if not x[1]]
print(f'PASS91_CHECKS={len(checks)-len(fails)}/{len(checks)}')
if fails: raise SystemExit(1)
