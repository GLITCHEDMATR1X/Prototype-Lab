from __future__ import annotations
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.argv=[str(ROOT/'main.py'),'--headless','--no-audio']

from panda3d.core import Vec3
import main

checks=[]
def check(name, cond, detail=''):
    ok=bool(cond); checks.append((name,ok,detail)); print(('PASS' if ok else 'FAIL'), name, detail)
    return ok

g=main.LockedHouseGame()
try:
    # Forest task should be the one bridge between rear hall and basement.
    check('forest task starts locked', g.forest_task['state']=='locked', str(g.forest_task))
    g.tv_task_10['state']='completed'
    g._issue_next_after_completion(10)
    check('task10 issues forest task', g.forest_task['state']=='active', g.task_broadcast_mode)
    check('forest broadcast is issue11', g.task_broadcast_mode=='issue11', str(g.task_broadcast_mode))

    # Enter forest and prove house is removed from view authority.
    g._enter_forest()
    check('forest active', g.forest_active)
    check('house hidden outside', g.scene_root.isHidden())
    check('forest visible', not g.forest_root.isHidden())
    check('return door initially open', abs(g.forest_door_hinge.getH()-62.0)<0.01, str(g.forest_door_hinge.getH()))

    g._forest_start_question()
    check('question stage', g.forest_dialogue_stage=='question')
    check('subtitle question', g.forest_subtitle['text']=='Do you believe in me?', g.forest_subtitle['text'])
    check('choice visible', not g.forest_choice.isHidden())

    # YES branch: calm permission, then return and acknowledge at TV.
    g._forest_choose(True)
    check('yes response stage', g.forest_dialogue_stage=='yes_response')
    check('yes subtitle', 'go to your room' in g.forest_subtitle['text'].lower(), g.forest_subtitle['text'])
    for _ in range(40): g._update_forest_encounter(.1)
    check('yes changes task', g.forest_task['state']=='changed', str(g.forest_task))
    check('door remains open after yes', abs(g.forest_door_hinge.getH()-62.0)<0.01, str(g.forest_door_hinge.getH()))
    g._leave_forest()
    check('yes returns to house', (not g.forest_active) and (not g.scene_root.isHidden()))
    check('returns to master floor', abs(g.player.z-g.floor_z)<0.01, str(g.player))
    g._ack_forest_task()
    check('forest completes on TV ack', g.forest_task['state']=='completed', str(g.forest_task))
    check('basement immediately issued', g.basement_task['state']=='active', str(g.basement_task))
    check('basement broadcast renumbered issue12', g.task_broadcast_mode=='issue12', str(g.task_broadcast_mode))

    # NO branch: rebuild only the encounter state, then prove growth/closure/sink/reset.
    g.basement_task['state']='locked'
    g.forest_task.update({'state':'active','choice':None,'completion_count':0})
    g._reset_forest_encounter(); g.forest_task['state']='active'
    g._enter_forest(); g._forest_start_question(); g._forest_choose(False)
    for _ in range(57): g._update_forest_encounter(.1)
    check('no branch punishment active', g.forest_dialogue_stage=='punish')
    check('entity grows', g.forest_entity_root.getScale().x>1.5, str(g.forest_entity_root.getScale()))
    check('door closes', abs(g.forest_door_hinge.getH())<1.0, str(g.forest_door_hinge.getH()))
    check('player sinks', g.player.z < -0.1, str(g.player.z))
    check('punishment line emitted', g.forest_no_line_played)
    check('punishment arms exist', not g.forest_punish_arms.find('**/forest-left-arm').isEmpty() and not g.forest_punish_arms.find('**/forest-right-arm').isEmpty())
    for _ in range(30): g._update_forest_encounter(.1)
    check('no branch resets run', not g.forest_active)
    check('forest task reset locked', g.forest_task['state']=='locked', str(g.forest_task))
    check('house restored after reset', not g.scene_root.isHidden())

    # Audio contracts: exact three required lines exist and are nontrivial WAVs.
    import wave
    for key in ('belief_question','belief_yes','belief_no'):
        p=ROOT/'assets'/'audio'/'forest_entity'/(key+'.wav')
        good=p.exists()
        dur=0.0
        if good:
            with wave.open(str(p),'rb') as w: dur=w.getnframes()/float(w.getframerate())
        check('audio '+key, good and dur>.5, f'{dur:.2f}s')
finally:
    try: g._runtime_cleanup()
    except Exception: pass
    try: g.destroy()
    except Exception: pass

fails=[x for x in checks if not x[1]]
print(f'PASS90_CHECKS={len(checks)-len(fails)}/{len(checks)}')
if fails:
    raise SystemExit(1)
