from pathlib import Path
import ast, json, math
ROOT=Path(__file__).resolve().parents[1]
source=(ROOT/'main.py').read_text()
tree=ast.parse(source)
vals={}
for n in tree.body:
    if isinstance(n,ast.Assign) and len(n.targets)==1 and isinstance(n.targets[0],ast.Name):
        name=n.targets[0].id
        if name.startswith('HEAD_TRACK_'):
            try: vals[name]=float(ast.literal_eval(n.value))
            except Exception: pass
YAW=vals['HEAD_TRACK_YAW_LIMIT']; UP=vals['HEAD_TRACK_PITCH_UP_LIMIT']; DOWN=vals['HEAD_TRACK_PITCH_DOWN_LIMIT']; SPEED=vals['HEAD_TRACK_SPEED_DPS']
def target(dx,dy,dz):
    planar=math.hypot(dx,dy)
    h=math.degrees(math.atan2(dx,-dy))
    p=-math.degrees(math.atan2(dz,max(planar,1e-8)))
    return max(-YAW,min(YAW,h)), max(-UP,min(DOWN,p))
def approach(cur,tgt,dt):
    step=SPEED*dt; d=tgt-cur
    return tgt if abs(d)<=step else cur+math.copysign(step,d)
checks={}
checks['center_yaw']=abs(target(0,-3,0)[0])<1e-9
checks['right_positive']=target(2,-3,0)[0]>20
checks['left_negative']=target(-2,-3,0)[0]<-20
checks['up_negative_pitch']=target(0,-3,2)[1]<-20
checks['down_positive_pitch']=target(0,-3,-2)[1]>20
checks['yaw_clamp']=abs(target(100,-.01,0)[0]-YAW)<1e-9
checks['up_clamp']=abs(target(0,-.01,100)[1]+UP)<1e-9
checks['down_clamp']=abs(target(0,-.01,-100)[1]-DOWN)<1e-9
checks['bounded_speed']=abs(approach(0,50,1/60)-SPEED/60)<1e-9
checks['no_overshoot']=approach(49,50,1/60)==50
out={'limits':{'yaw_deg':YAW,'pitch_up_deg':UP,'pitch_down_deg':DOWN,'speed_dps':SPEED},'samples':{'right':target(2,-3,0),'left':target(-2,-3,0),'up':target(0,-3,2),'down':target(0,-3,-2)},'checks':checks,'pass':all(checks.values())}
(ROOT/'verification/head_tracking_math.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps(out,indent=2))
raise SystemExit(0 if out['pass'] else 1)
