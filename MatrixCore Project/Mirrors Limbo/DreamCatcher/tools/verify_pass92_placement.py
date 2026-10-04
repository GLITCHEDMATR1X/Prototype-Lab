from __future__ import annotations
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.argv=[str(ROOT/'main.py'),'--headless','--no-audio']
sys.path.insert(0,str(ROOT))
import main

def bounds(np, render):
    a,b=np.getTightBounds(render)
    return tuple(float(v) for v in (*a,*b))

def near(a,b,tol=0.025): return abs(a-b)<=tol

g=main.LockedHouseGame()
checks=[]
def check(name, cond, detail=''):
    checks.append((name,bool(cond),detail)); print(('PASS' if cond else 'FAIL'),name,detail)

# Dining table: actual grounded legs and realistic clearance over the seat.
top=g.render.find('**/f1-dining-table-top')
legs=list(g.render.findAllMatches('**/f1-dining-table-leg-*'))
check('dining_top_exists',not top.isEmpty())
check('dining_four_legs',len(legs)==4,f'count={len(legs)}')
if not top.isEmpty() and legs:
    tb=bounds(top,g.render); legbs=[bounds(n,g.render) for n in legs]
    floor=float(g.floor1_z)
    check('dining_legs_grounded',all(near(b[2],floor,0.02) for b in legbs),str([(round(b[2],3),round(b[5],3)) for b in legbs]))
    check('dining_legs_reach_top',all(abs(b[5]-tb[2])<0.06 for b in legbs),f'top_bottom={tb[2]:.3f}')
    chair=g.render.find('**/f1-dining-chair-seat')
    if not chair.isEmpty():
        cb=bounds(chair,g.render)
        check('dining_seat_below_table',cb[5] < tb[2]-0.12,f'seat_top={cb[5]:.3f} table_bottom={tb[2]:.3f}')
check('old_floating_table_removed',g.render.find('**/f1-dining-table').isEmpty())

# Kitchen: counter/sink/tap are supported; no carpet/rug/mat geometry exists there.
ctr=g.render.find('**/f1-kitchen-counter'); sink=g.render.find('**/f1-kitchen-sink'); tap=g.render.find('**/f1-kitchen-tap')
if not ctr.isEmpty() and not sink.isEmpty() and not tap.isEmpty():
    c=bounds(ctr,g.render); s=bounds(sink,g.render); t=bounds(tap,g.render)
    check('kitchen_counter_grounded',near(c[2],float(g.floor1_z),0.02),f'bottom={c[2]:.3f}')
    check('kitchen_sink_supported',s[2] <= c[5]+0.04 and s[5] >= c[5]-0.04,f'counter_top={c[5]:.3f} sink_bottom={s[2]:.3f}')
    check('kitchen_tap_supported',t[2] <= s[5]+0.04,f'sink_top={s[5]:.3f} tap_bottom={t[2]:.3f}')
# Names only: floor carpet is an audio zone, not visual geometry in floor1.
f1_carpet_named=[n.getName() for n in g.render.findAllMatches('**/*carpet*') if n.getName().startswith('f1-')]
check('no_floor1_floating_carpet_geometry',len(f1_carpet_named)==0,str(f1_carpet_named))

# Basement clue must be on the north-wall interior face, not floating in the corridor.
paper=g.render.find('**/basement-clue-paper')
if not paper.isEmpty():
    pb=bounds(paper,g.render); wall_face=12.70-0.14/2
    check('basement_clue_wall_mounted',abs(pb[4]-wall_face)<0.025,f'paper_north={pb[4]:.3f} wall_face={wall_face:.3f}')
    check('basement_clue_above_floor',pb[2] > float(g.basement_z)+0.9,f'bottom={pb[2]:.3f}')

# Stair rails must have grounded posts; rails themselves stay overhead and out of the lane.
posts=list(g.render.findAllMatches('**/basement-entry-rail-*-post-*'))
check('basement_rail_six_posts',len(posts)==6,f'count={len(posts)}')
if posts:
    pbs=[bounds(n,g.render) for n in posts]
    check('basement_rail_posts_grounded',all(near(b[2],float(g.basement_z),0.02) for b in pbs),str([round(b[2],3) for b in pbs]))

# Attic storage remains intentionally grounded; this pass should not disturb it.
storage=list(g.render.findAllMatches('**/attic-storage-[0-9]'))
check('attic_storage_present',len(storage)>=2,f'count={len(storage)}')
if storage:
    sbs=[bounds(n,g.render) for n in storage]
    check('attic_storage_grounded',all(near(b[2],float(g.attic_z),0.02) for b in sbs),str([round(b[2],3) for b in sbs]))

# Existing progression authority remains untouched.
check('forest_task_number_11',g.forest_task.get('id')=='forest_faith_11',str(g.forest_task.get('id')))
check('basement_task_number_12',g.basement_task.get('id')=='basement_clue_12',str(g.basement_task.get('id')))
check('attic_task_number_13',g.attic_task.get('id')=='attic_pylon_final_13',str(g.attic_task.get('id')))

fails=[c for c in checks if not c[1]]
print(f'PASS92_TOTAL={len(checks)} PASS={len(checks)-len(fails)} FAIL={len(fails)}')
try:g._runtime_cleanup()
except:pass
try:g.destroy()
except:pass
raise SystemExit(1 if fails else 0)
