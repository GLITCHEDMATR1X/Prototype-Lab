import json, math
from pathlib import Path
R = Path(__file__).resolve().parents[1]
OUT = R / 'verification' / 'memory_rewind_math.json'
OUT.parent.mkdir(parents=True, exist_ok=True)
CORE=.050; RADIUS=.26; BLOOM=.16; REWIND=2.20

def smooth01(v):
    v=max(0.0,min(1.0,v)); return v*v*(3.0-2.0*v)

def influence(dist, age=1.0):
    strength=min(1.0,max(0.0,age)/BLOOM)
    if dist>=RADIUS:return 0.0
    if dist<=CORE:local=1.0
    else:
        local=1.0-(dist-CORE)/(RADIUS-CORE)
        local=smooth01(local)
    return max(0.0,min(1.0,local*strength))

dists=[0.0,.03,.07,.12,.18,.25,.26]
vals=[influence(d) for d in dists]
monotonic=all(vals[i]>=vals[i+1] for i in range(len(vals)-1)) and vals[0]==1.0 and vals[-1]==0.0
# Two impacts happened 3 seconds apart. At the current moment the old one is 5s old and the new one is 2s old.
old_age,new_age=5.0,2.0
rewound=[]
for step in range(1,5):
    amount=1.0*REWIND
    old_age=max(0,old_age-amount); new_age=max(0,new_age-amount)
    rewound.append({'step':step,'old_age':old_age,'new_age':new_age})
recent_disappears_first=(rewound[0]['new_age']==0 and rewound[0]['old_age']>0)
all_restore=(rewound[-1]['new_age']==0 and rewound[-1]['old_age']==0)
# A tiny recorded trajectory; rewinding to t=.5 should interpolate exactly between its .25 and .75 samples.
samples=[(0.0,(0,0,1),0),(0.25,(1,0,1.5),20),(0.75,(3,0,1.0),60),(1.0,(4,0,.1),80)]
def pose(age):
    if age<=samples[0][0]: return samples[0][1],samples[0][2]
    if age>=samples[-1][0]: return samples[-1][1],samples[-1][2]
    for a,b in zip(samples,samples[1:]):
        if a[0]<=age<=b[0]:
            q=(age-a[0])/(b[0]-a[0])
            p=tuple(a[1][i]+(b[1][i]-a[1][i])*q for i in range(3))
            r=a[2]+(b[2]-a[2])*q
            return p,r
p,r=pose(.5)
interpolation_ok=all(abs(a-b)<1e-8 for a,b in zip(p,(2.0,0.0,1.25))) and abs(r-40.0)<1e-8
result={
    'gradient_distances':dists,'gradient_influences':vals,'gradient_monotonic':monotonic,
    'rewind_speed':REWIND,'rewind_age_steps':rewound,'recent_event_reverses_first':recent_disappears_first,
    'complete_restore_reached':all_restore,'trajectory_interpolation':{'pose':p,'roll':r,'pass':interpolation_ok},
    'result':'PASS' if all((monotonic,recent_disappears_first,all_restore,interpolation_ok)) else 'FAIL'
}
OUT.write_text(json.dumps(result,indent=2)); print(json.dumps(result,indent=2))
raise SystemExit(0 if result['result']=='PASS' else 1)
