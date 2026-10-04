from __future__ import annotations
import importlib.util, math, sys
from pathlib import Path
from panda3d.core import Vec3

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

FAIL=[]
def check(cond,msg):
    print(("PASS " if cond else "FAIL ")+msg)
    if not cond: FAIL.append(msg)

def room_map(level):
    return {r["id"]:r for r in g.layout["rooms"] if r.get("level")==level}

def center(rect):
    return ((rect[0]+rect[2])/2.0,(rect[1]+rect[3])/2.0)

def set_level(level):
    g.floor1_active = level=="floor1"
    g.basement_active = level=="basement"
    g.attic_active = level=="attic"

def cross_portal(level, po, lateral_a, lateral_b=None):
    rm=room_map(level)
    a=rm[po["rooms"][0]]["rect"]; b=rm[po["rooms"][1]]["rect"]
    ac=center(a); bc=center(b)
    if lateral_b is None: lateral_b=lateral_a
    px,py,_=map(float,po["center"])
    if po["axis"]=="x":
        left,right=(a,b) if ac[0] < bc[0] else (b,a)
        start=Vec3(float(left[2])-0.48, py+lateral_a, g.player.z)
        target=Vec3(float(right[0])+0.48, py+lateral_b, g.player.z)
    else:
        south,north=(a,b) if ac[1] < bc[1] else (b,a)
        start=Vec3(px+lateral_a, float(south[3])-0.48, g.player.z)
        target=Vec3(px+lateral_b, float(north[1])+0.48, g.player.z)
    set_level(level)
    g.player=Vec3(start)
    if g._blocked(g.player.x,g.player.y): return False,999.0
    # Deliberately use large 0.20m movement requests; Pass 89 must substep them.
    for _ in range(40):
        dv=target-g.player; dv.z=0
        d=dv.length()
        if d < 0.08: break
        dv.normalize(); g._move_player_swept(dv*min(0.20,d))
    return (Vec3(g.player-target).length()<0.14), Vec3(g.player-target).length()

# Every normal doorway gets center, off-center, and diagonal threshold crossings.
for level in ("floor2","floor1"):
    for po in [p for p in g.layout["portals"] if p.get("level")==level]:
        half=float(po["width"])/2.0
        # Stay inside the visible opening while still probing the jamb shoulders.
        off=min(0.22,max(0.12,half-0.22))
        for label,a,b in (("center",0.0,0.0),("edge-",-off,-off),("edge+",off,off),("diagonal",-off,off)):
            ok,d=cross_portal(level,po,a,b)
            check(ok,f"{level} {po['id']} {label} crossing clears threshold (remaining {d:.3f}m)")

# Basement walk-rect joins should not create player-width pinch points after radius inset.
r=float(g.PLAYER_RADIUS)
joins=[]
for i,a in enumerate(g.basement_walk_rects):
    A=(a[0]+r,a[1]+r,a[2]-r,a[3]-r)
    for j,b in enumerate(g.basement_walk_rects[i+1:],i+1):
        B=(b[0]+r,b[1]+r,b[2]-r,b[3]-r)
        ox=min(A[2],B[2])-max(A[0],B[0]); oy=min(A[3],B[3])-max(A[1],B[1])
        if ox>=0 and oy>=0:
            throat=min(ox,oy)
            joins.append((i,j,throat))
            check(throat>=0.50,f"basement walk join {i}->{j} has >=0.50m effective overlap ({throat:.3f}m)")
check(bool(joins),"basement walk network exposes measurable joins")

# Attic main-to-landing connector: probe its full useful center lane and diagonal approach.
set_level("attic")
for y0,y1,label in ((4.20,4.20,"center"),(3.92,3.92,"south lane"),(4.48,4.48,"north lane"),(3.92,4.48,"diagonal")):
    g.player=Vec3(8.10,y0,g.attic_z)
    target=Vec3(9.00,y1,g.attic_z)
    for _ in range(20):
        dv=target-g.player; dv.z=0
        d=dv.length()
        if d<0.06: break
        dv.normalize(); g._move_player_swept(dv*min(0.20,d))
    check(Vec3(g.player-target).length()<0.12,f"attic connector {label} crossing does not snag")

# Movement slice itself must stay smaller than a typical threshold shoulder.
check(g.MOVE_COLLISION_STEP <= 0.07, f"movement collision substep <=0.07m ({g.MOVE_COLLISION_STEP:.3f}m)")

g.userExit()
if FAIL:
    print(f"PASS89_THRESHOLDS=FAIL count={len(FAIL)}")
    raise SystemExit(1)
print("PASS89_THRESHOLDS=PASS")
