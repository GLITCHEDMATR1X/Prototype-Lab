from __future__ import annotations
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.argv=[str(ROOT/'main.py'),'--headless','--no-audio']
import main
checks=[]
def check(name, cond, detail=''):
    checks.append(bool(cond)); print(('PASS' if cond else 'FAIL'), name, detail)
g=main.LockedHouseGame()
try:
    g.attic_active=True; g.attic_root.show(); g.attic_task.update({'state':'loosened','pylon_loosened':True})
    g._start_attic_finale()
    check('finale starts', g.finale_active and not g.finale_finished)
    g.finale_elapsed=3.9; g._attic_finale_runtime(type('T',(),{})())
    check('pylon visibly yields', abs(g.attic_pylon_root.getR())>5.0, str(g.attic_pylon_root.getR()))
    g.finale_elapsed=5.8; g._attic_finale_runtime(type('T',(),{})())
    check('hand enters after roof opens', not g.giant_hand_root.isHidden())
    check('remembered final line appears', g.finale_subtitle['text']=='You know why you are here.', repr(g.finale_subtitle['text']))
    g.finale_elapsed=8.4; g._attic_finale_runtime(type('T',(),{})())
    check('ending no longer promises another task', g.finale_message['text']=='END', repr(g.finale_message['text']))
    g.finale_elapsed=9.3; result=g._attic_finale_runtime(type('T',(),{})())
    check('final task completes', g.finale_finished and g.attic_task['state']=='completed', str(g.attic_task))
    g._reset_attic_finale()
    check('reset restores pylon transform', abs(g.attic_pylon_root.getR())<0.01 and abs(g.attic_pylon_root.getP())<0.01, str(g.attic_pylon_root.getHpr()))
finally:
    try:g._runtime_cleanup()
    except Exception:pass
    try:g.destroy()
    except Exception:pass
print(f'PASS98_TOTAL={sum(checks)}/{len(checks)}')
raise SystemExit(0 if all(checks) else 1)
