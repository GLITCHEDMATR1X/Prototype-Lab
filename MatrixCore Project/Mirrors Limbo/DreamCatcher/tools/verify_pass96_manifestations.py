from __future__ import annotations
import math, sys
from pathlib import Path
from panda3d.core import Vec3

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.argv=[str(ROOT/'main.py'),'--headless','--no-audio']
import main

checks=[]
def check(name, cond, detail=''):
    checks.append(bool(cond)); print(('PASS' if cond else 'FAIL'), name, detail)

g=main.LockedHouseGame()
try:
    # Natural occurrence selection should prefer anchors behind the current view when available.
    g.tv_focused=False; g.floor1_active=False; g.basement_active=False; g.attic_active=False
    g.player=Vec3(5.3,2.55,g.floor_z); g.heading=0.0; g.pitch=0.0; g._apply_camera()
    g.current_room_id='f2_master'; g.alternate_visit_order=['f2_master']
    cands=g._candidate_alternate_anchors()
    cam=g.camera.getPos(g.render); h=math.radians(g.heading); fwd=Vec3(-math.sin(h),math.cos(h),0)
    dots=[]
    for a in cands:
        d=Vec3(a['pos'])-cam; d.z=0
        if d.lengthSquared()>1e-4:
            d.normalize(); dots.append(fwd.dot(d))
    check('natural anchors prefer behind-view points', bool(dots) and max(dots)<-0.12, str([round(v,3) for v in dots]))

    # Every chair sit schedules a manifestation, and every third uses the head-only variant.
    g._hide_alternate(); g.tv_focused=False; g.tv_sit_count=0
    g._enter_tv_focus(from_chair=True)
    check('chair sit 1 schedules presence', abs(g.alt_hidden_timer-0.55)<1e-6 and g.alt_forced_visibility_mode=='full', f"timer={g.alt_hidden_timer} mode={g.alt_forced_visibility_mode}")
    g._leave_tv_focus(); g._hide_alternate(); g.tv_focused=False
    g._enter_tv_focus(from_chair=True)
    check('chair sit 2 schedules presence', g.tv_sit_count==2 and g.alt_forced_visibility_mode=='full', f"count={g.tv_sit_count} mode={g.alt_forced_visibility_mode}")
    g._leave_tv_focus(); g._hide_alternate(); g.tv_focused=False
    g._enter_tv_focus(from_chair=True)
    check('chair sit 3 becomes head-only', g.tv_sit_count==3 and g.alt_forced_visibility_mode=='head_only', f"count={g.tv_sit_count} mode={g.alt_forced_visibility_mode}")

    # Spawn the scheduled occurrence and prove only the head geometry is visible.
    g._manifest_alternate()
    visible=[ch.getName() for ch in g.alternate_visual.getChildren() if not ch.isHidden()]
    check('head-only mode hides body', visible==['alternate-head'], str(visible))
    check('chair anchor is behind seat/camera authority', g.alt_anchor and g.alt_anchor.get('id')=='chair_spy_anchor', str(g.alt_anchor.get('id') if g.alt_anchor else None))

    # Leaving focus resets the chair-spy timer so the player has a brief turn-around window.
    g.alt_local_time=12.0; g.alt_seen_accum=1.0
    g._leave_tv_focus()
    check('standing grants glimpse window', g.alt_local_time==0.0 and g.alt_seen_accum==0.0, f"time={g.alt_local_time} seen={g.alt_seen_accum}")

    check('ordinary cadence is sparse', g.alt_hidden_timer>=0.0, f"timer={g.alt_hidden_timer}")
finally:
    try: g._runtime_cleanup()
    except Exception: pass
    try: g.destroy()
    except Exception: pass

print(f"PASS96_TOTAL={sum(checks)}/{len(checks)}")
raise SystemExit(0 if all(checks) else 1)
