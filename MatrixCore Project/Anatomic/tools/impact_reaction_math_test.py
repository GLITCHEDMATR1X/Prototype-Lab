import math, json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def spring(x,v,dt,k=70.0,d=14.5):
    v += (-k*x-d*v)*dt; x += v*dt; return x,v

def sim(v0,steps=120,dt=1/120):
    x=0.0;v=v0;peak=0
    for _ in range(steps):
        x,v=spring(x,v,dt);peak=max(peak,abs(x))
    return peak,abs(x),abs(v)
auto=sim(30); shotgun=sim(58); sniper=sim(120)
checks={'ordered_strength':auto[0]<shotgun[0]<sniper[0], 'auto_bounded':auto[0]<6, 'shotgun_bounded':shotgun[0]<10, 'sniper_head_readable':sniper[0]>4, 'spring_recovers':sniper[1]<0.2}
out={'schema':'ascii_matter.pass25.impact_math.v1','result':'PASS' if all(checks.values()) else 'FAIL','checks':checks,'peak_deg':{'auto':auto[0],'shotgun':shotgun[0],'sniper':sniper[0]},'sniper_residual':sniper[1]}
(ROOT/'verification').mkdir(exist_ok=True)
(ROOT/'verification/pass25_impact_math.json').write_text(json.dumps(out,indent=2))
print(json.dumps(out,indent=2)); raise SystemExit(0 if out['result']=='PASS' else 1)
