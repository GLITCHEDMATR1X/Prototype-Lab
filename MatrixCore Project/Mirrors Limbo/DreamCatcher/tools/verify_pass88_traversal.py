from __future__ import annotations
import importlib.util, math, sys
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.argv = ["main.py", "--headless", "--no-audio"]
spec = importlib.util.spec_from_file_location("locked_house_main", ROOT / "main.py")
mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(mod)
g = mod.LockedHouseGame()
for name in ("frame-update", "main-update"):
    try: g.taskMgr.remove(name)
    except Exception: pass

FAIL = []

def check(cond: bool, msg: str):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond: FAIL.append(msg)

def reachable(active_attr, start, target, radius, bounds, step=0.08):
    g.floor1_active = g.basement_active = g.attic_active = False
    setattr(g, active_attr, True)
    x0,y0,x1,y1 = bounds
    def key(x,y): return (round((x-x0)/step), round((y-y0)/step))
    def pos(k): return (x0+k[0]*step, y0+k[1]*step)
    sk=key(float(start.x),float(start.y))
    if g._blocked(float(start.x),float(start.y)): return False, 999
    q=deque([sk]); seen={sk}
    while q:
        k=q.popleft()
        for dx,dy in ((1,0),(-1,0),(0,1),(0,-1)):
            nk=(k[0]+dx,k[1]+dy)
            if nk in seen: continue
            nx,ny=pos(nk)
            if nx<x0 or nx>x1 or ny<y0 or ny>y1: continue
            if not g._blocked(nx,ny): seen.add(nk); q.append(nk)
    tx,ty=float(target.x),float(target.y)
    best=min(math.hypot(pos(k)[0]-tx,pos(k)[1]-ty) for k in seen)
    return best <= radius, best


# Floor 1 remains a connected bridge between upstairs return and basement access.
f1_rooms=[r["rect"] for r in g.floor1_rooms.values()]
f1_bounds=(min(r[0] for r in f1_rooms)-0.5,min(r[1] for r in f1_rooms)-0.5,max(r[2] for r in f1_rooms)+0.5,max(r[3] for r in f1_rooms)+0.5)
ok,d=reachable("floor1_active", g.floor1_entry_pos, g.floor1_return_pos, 1.45, f1_bounds)
check(ok, f"floor1 entry reaches upstairs return (nearest {d:.3f}m)")
ok,d=reachable("floor1_active", g.floor1_entry_pos, g.floor1_basement_pos, 1.45, f1_bounds)
check(ok, f"floor1 entry reaches basement access (nearest {d:.3f}m)")
for po in [q for q in g.layout["portals"] if q.get("level")=="floor1"]:
    px,py,_=map(float,po["center"])
    check(not g._blocked(px,py), f"floor1 portal {po['id']} center traversable")

# Floor 2 authored doorways remain open after the vertical-route repair.
g.floor1_active=g.basement_active=g.attic_active=False
for po in [q for q in g.layout["portals"] if q.get("level")=="floor2"]:
    px,py,_=map(float,po["center"])
    check(not g._blocked(px,py), f"floor2 portal {po['id']} center traversable")

# Basement authored movement route must reach both objective and exit.
ok,d=reachable("basement_active", g.basement_entry_pos, g.basement_clue_pos, 1.20, (2.0,0.5,15.2,13.0))
check(ok, f"basement entry reaches clue (nearest {d:.3f}m)")
ok,d=reachable("basement_active", g.basement_entry_pos, g.basement_exit_pos, 1.65, (2.0,0.5,15.2,13.0))
check(ok, f"basement entry reaches exit (nearest {d:.3f}m)")

# No visual basement wall may occupy the effective walk-lane interior.
r=float(g.PLAYER_RADIUS)
for i,(cx,cy,w,d) in enumerate(g.basement_wall_segments):
    wx0,wy0,wx1,wy1 = cx-w/2, cy-d/2, cx+w/2, cy+d/2
    overlaps=[]
    for j,(x0,y0,x1,y1) in enumerate(g.basement_walk_rects):
        ex0,ey0,ex1,ey1=x0+r,y0+r,x1-r,y1-r
        ox=max(0,min(wx1,ex1)-max(wx0,ex0)); oy=max(0,min(wy1,ey1)-max(wy0,ey0))
        if ox>1e-6 and oy>1e-6: overlaps.append(j)
    check(not overlaps, f"basement wall {i} stays outside walk lanes")

# Attic route and connector must be continuous without slab-area overlap.
ok,d=reachable("attic_active", g.attic_entry_pos, g.attic_pylon_pos, 1.55, (0,0,12,10))
check(ok, f"attic entry reaches pylon interaction ring (nearest {d:.3f}m)")
ok,d=reachable("attic_active", g.attic_entry_pos, g.attic_entry_pos, 1.40, (0,0,12,10))
check(ok, f"attic exit remains reachable (nearest {d:.3f}m)")
a,b=g.attic_walk_rects
ox=max(0,min(a[2],b[2])-max(a[0],b[0])); oy=max(0,min(a[3],b[3])-max(a[1],b[1]))
check(ox*oy == 0, "attic main/landing slabs have no coplanar area overlap")

# Entering each vertical space must face the playable route, not a wall.
g.basement_task["state"]="active"
g._enter_basement()
check(abs(g.heading-90.0)<0.01, "basement entry faces along the open corridor")
g.attic_task["state"]="active"
g._enter_attic()
check(abs(g.heading-90.0)<0.01, "attic entry faces main attic opening")

g.userExit()
if FAIL:
    print(f"PASS88_TRAVERSAL=FAIL count={len(FAIL)}")
    raise SystemExit(1)
print("PASS88_TRAVERSAL=PASS")
