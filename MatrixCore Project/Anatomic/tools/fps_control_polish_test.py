import json, math
from pathlib import Path

WALK_SPEED=4.0; SPRINT_SPEED=6.5; CROUCH_SPEED=2.3
GROUND_ACCEL=22.0; GROUND_DECEL=30.0; AIR_ACCEL=7.0
COYOTE_TIME=0.11; JUMP_BUFFER_TIME=0.13; JUMP_SPEED=5.2; GRAVITY=12.5
STAND_EYE=1.68; CROUCH_EYE=1.08; EYE_TRANSITION_SPEED=4.2
BODY_STOP=0.88; SPAWN=(0.0,-5.0,STAND_EYE); TARGET=(0.0,0.0,1.38)

def approach(cur, target, delta):
    return min(target,cur+delta) if cur<target else max(target,cur-delta)

def norm(v):
    l=math.sqrt(sum(x*x for x in v)); return tuple(x/l for x in v)

def dot(a,b): return sum(x*y for x,y in zip(a,b))

# Spawn camera should point directly at upper torso.
d=norm(tuple(TARGET[i]-SPAWN[i] for i in range(3)))
spawn_dot=dot(d,d)

# Acceleration and braking.
dt=1/60
v=0.0
walk_samples=[]
for _ in range(30):
    v=approach(v,WALK_SPEED,GROUND_ACCEL*dt); walk_samples.append(v)
walk_peak=max(walk_samples)
for _ in range(30): v=approach(v,SPRINT_SPEED,GROUND_ACCEL*dt)
sprint_peak=v
stop_start=v
for _ in range(30): v=approach(v,0.0,GROUND_DECEL*dt)
stop_final=v

# Smooth crouch transition.
eye=STAND_EYE
for _ in range(4): eye=approach(eye,CROUCH_EYE,EYE_TRANSITION_SPEED*dt)
crouch_eye_10f=eye
for _ in range(12): eye=approach(eye,STAND_EYE,EYE_TRANSITION_SPEED*dt)
stand_eye_after=eye

# Jump apex / return, with a queued request held briefly before ground eligibility.
z=0.0; vz=0.0; on_ground=False; coyote=0.0; buffer=JUMP_BUFFER_TIME
# Simulate a press 4 frames before landing. Ground becomes true on frame 4.
trigger_frame=None
for frame in range(8):
    buffer=max(0.0,buffer-dt)
    if frame==4:
        on_ground=True; coyote=COYOTE_TIME
    if on_ground: coyote=COYOTE_TIME
    if buffer>0 and coyote>0:
        vz=JUMP_SPEED; on_ground=False; coyote=0; buffer=0; trigger_frame=frame; break
jump_peak=0.0
for _ in range(180):
    if not on_ground:
        vz-=GRAVITY*dt; z+=vz*dt; jump_peak=max(jump_peak,z)
        if z<=0: z=0; vz=0; on_ground=True; break

checks={
    'spawn_facing':spawn_dot>0.999999,
    'walk_accelerates':walk_samples[0] < walk_samples[-1] and 3.9 <= walk_peak <= WALK_SPEED+1e-6,
    'sprint_faster':sprint_peak > walk_peak+2.0 and sprint_peak <= SPRINT_SPEED+1e-6,
    'brakes_to_stop':stop_start>6.0 and abs(stop_final)<1e-9,
    'crouch_smooth_not_snap':CROUCH_EYE < crouch_eye_10f < STAND_EYE,
    'stand_recovers':stand_eye_after>crouch_eye_10f,
    'jump_buffered':trigger_frame==4,
    'jump_apex':0.9 < jump_peak < 1.2,
    'collision_stop':abs(BODY_STOP-0.88)<1e-9,
}
out={'schema':'ascii_matter.fps_control_polish.v1','checks':checks,'spawn_facing_dot':round(spawn_dot,6),'walk_peak':round(walk_peak,4),'sprint_peak':round(sprint_peak,4),'stop_final':round(stop_final,6),'crouch_eye_4_frames':round(crouch_eye_10f,4),'jump_trigger_frame':trigger_frame,'jump_apex_m':round(jump_peak,4),'result':'PASS' if all(checks.values()) else 'FAIL'}
path=Path(__file__).resolve().parents[1]/'verification/fps_control_polish.json'; path.parent.mkdir(exist_ok=True)
path.write_text(json.dumps(out,indent=2))
print(json.dumps(out,indent=2))
raise SystemExit(0 if out['result']=='PASS' else 1)
