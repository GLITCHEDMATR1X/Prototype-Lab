from pathlib import Path
import json, math

ROOT = Path(__file__).resolve().parents[1]
BODY = ROOT / 'assets/cache/generic_male_ascii.json'
OUT = ROOT / 'assets/cache/internal_skeleton.json'

ORGAN_RECIPES = {
    'brain':        {'center': (0.000, 0.012, 1.690), 'radii': (0.050, 0.042, 0.040), 'count': 24},
    'left_lung':    {'center': (-0.073, 0.000, 1.350), 'radii': (0.036, 0.023, 0.095), 'count': 22},
    'right_lung':   {'center': (0.073, 0.000, 1.350), 'radii': (0.036, 0.023, 0.095), 'count': 22},
    'heart':        {'center': (0.000, -0.030, 1.310), 'radii': (0.023, 0.014, 0.030), 'count': 12},
    'stomach':      {'center': (-0.055, 0.012, 1.105), 'radii': (0.032, 0.020, 0.042), 'count': 12},
    'liver':        {'center': (0.055, 0.007, 1.115), 'radii': (0.040, 0.020, 0.030), 'count': 14},
    'left_kidney':  {'center': (-0.065, -0.012, 1.005), 'radii': (0.018, 0.014, 0.026), 'count': 6},
    'right_kidney': {'center': (0.065, -0.012, 1.005), 'radii': (0.018, 0.014, 0.026), 'count': 6},
}

JOINTS = {
    'pelvis': (0.000, 0.050, 0.900),
    'spine_low': (0.000, 0.060, 1.020),
    'spine_mid': (0.000, 0.070, 1.165),
    'spine_high': (0.000, 0.070, 1.380),
    'neck': (0.000, 0.055, 1.555),
    'head_base': (0.000, 0.050, 1.615),
    'left_shoulder': (-0.180, 0.060, 1.455),
    'right_shoulder': (0.180, 0.060, 1.455),
    # Pass 18: lower the elbow pivots to the actual upper/lower-arm break.
    # Pass 16/17 placed them too high, making the forearms look short and causing
    # the visible bend to occur above the model's anatomical elbow.
    'left_elbow': (-0.255, 0.060, 1.225),
    'right_elbow': (0.255, 0.060, 1.225),
    'left_wrist': (-0.342, 0.020, 1.020),
    'right_wrist': (0.340, 0.018, 1.020),
    'left_hand': (-0.382, -0.004, 0.910),
    'right_hand': (0.382, -0.004, 0.910),
    'left_hip': (-0.100, 0.025, 0.880),
    'right_hip': (0.100, 0.025, 0.880),
    'left_knee': (-0.098, 0.030, 0.515),
    'right_knee': (0.098, 0.030, 0.515),
    'left_ankle': (-0.125, 0.070, 0.150),
    'right_ankle': (0.125, 0.070, 0.150),
    'left_foot': (-0.140, 0.025, 0.070),
    'right_foot': (0.140, 0.025, 0.070),
}

# Pass 16: five small articulated finger chains per hand.  The authored pose has
# the hands hanging at the sides, so the phalanges descend inside the sampled
# ASCII hand volume.  Each chain uses root/mid/tip joints and remains a child of
# the existing hand joint; elbow motion therefore carries forearm, palm and fingers
# without disturbing the upper arm or torso.
FINGER_NAMES = ('thumb','index','middle','ring','pinky')
FINGER_Y_OFFSETS = (-0.022,-0.011,0.000,0.011,0.022)
FINGER_LENGTHS = (0.061,0.069,0.073,0.067,0.054)
FINGER_JOINT_RADIUS = 0.0019
FINGER_BONE_RADII = (0.0020,0.0016,0.0014)
# Pass 29: add believable skeletal mass without breaching the dense ASCII shell.
BONE_RADIUS_MULTIPLIER = 1.15
CURVE_RADIUS_MULTIPLIER = 1.15
JOINT_RADIUS_MULTIPLIER = 1.08
for side, sign in (('left',-1.0),('right',1.0)):
    hx,hy,hz = JOINTS[f'{side}_hand']
    for i,(finger,yoff,length) in enumerate(zip(FINGER_NAMES,FINGER_Y_OFFSETS,FINGER_LENGTHS)):
        root=(hx + sign*(i-2)*0.003, hy+yoff, hz-0.006)
        mid=(root[0]+sign*0.002, root[1]-0.003, root[2]-length*0.48)
        tip=(root[0]+sign*0.004, root[1]-0.006, root[2]-length)
        JOINTS[f'{side}_{finger}_root']=root
        JOINTS[f'{side}_{finger}_mid']=mid
        JOINTS[f'{side}_{finger}_tip']=tip

RIG_PARENT = {
    'pelvis': None,
    'spine_low': 'pelvis',
    'spine_mid': 'spine_low',
    'spine_high': 'spine_mid',
    'neck': 'spine_high',
    'head_base': 'neck',
    'left_shoulder': 'spine_high',
    'left_elbow': 'left_shoulder',
    'left_wrist': 'left_elbow',
    'left_hand': 'left_wrist',
    'right_shoulder': 'spine_high',
    'right_elbow': 'right_shoulder',
    'right_wrist': 'right_elbow',
    'right_hand': 'right_wrist',
    'left_hip': 'pelvis',
    'left_knee': 'left_hip',
    'left_ankle': 'left_knee',
    'left_foot': 'left_ankle',
    'right_hip': 'pelvis',
    'right_knee': 'right_hip',
    'right_ankle': 'right_knee',
    'right_foot': 'right_ankle',
}
for side in ('left','right'):
    for finger in FINGER_NAMES:
        RIG_PARENT[f'{side}_{finger}_root']=f'{side}_hand'
        RIG_PARENT[f'{side}_{finger}_mid']=f'{side}_{finger}_root'
        RIG_PARENT[f'{side}_{finger}_tip']=f'{side}_{finger}_mid'

BONES = [
    ('spine_pelvis','pelvis','spine_low',0.0092),
    ('spine_low_mid','spine_low','spine_mid',0.0083),
    ('spine_mid_high','spine_mid','spine_high',0.0083),
    ('spine_neck','spine_high','neck',0.0070),
    ('neck_head','neck','head_base',0.0070),
    ('left_clavicle','spine_high','left_shoulder',0.0068),
    ('right_clavicle','spine_high','right_shoulder',0.0068),
    ('left_humerus','left_shoulder','left_elbow',0.0072),
    ('right_humerus','right_shoulder','right_elbow',0.0072),
    ('left_radius','left_elbow','left_wrist',0.0052),
    ('right_radius','right_elbow','right_wrist',0.0052),
    ('left_palm','left_wrist','left_hand',0.0046),
    ('right_palm','right_wrist','right_hand',0.0046),
    ('left_hip_link','pelvis','left_hip',0.0070),
    ('right_hip_link','pelvis','right_hip',0.0070),
    ('left_femur','left_hip','left_knee',0.0092),
    ('right_femur','right_hip','right_knee',0.0092),
    ('left_tibia','left_knee','left_ankle',0.0061),
    ('right_tibia','right_knee','right_ankle',0.0061),
    ('left_foot_arch','left_ankle','left_foot',0.0048),
    ('right_foot_arch','right_ankle','right_foot',0.0048),
]
for side in ('left','right'):
    for finger in FINGER_NAMES:
        BONES.extend([
            (f'{side}_{finger}_metacarpal',f'{side}_hand',f'{side}_{finger}_root',FINGER_BONE_RADII[0]),
            (f'{side}_{finger}_proximal',f'{side}_{finger}_root',f'{side}_{finger}_mid',FINGER_BONE_RADII[1]),
            (f'{side}_{finger}_distal',f'{side}_{finger}_mid',f'{side}_{finger}_tip',FINGER_BONE_RADII[2]),
        ])

# Curved ribs sit outside the ASCII lung/heart clusters while remaining well inside
# the sampled outer shell.  Each polyline is rendered as short solid bone segments.
RIB_LEVELS = (1.440, 1.380, 1.320, 1.260)
RIB_RADIUS = 0.0040

def rib_points(side, z):
    s = float(side)
    return [
        (0.000, 0.072, z),
        (s*0.060, 0.072, z),
        (s*0.112, 0.045, z),
        (s*0.122, 0.000, z),
        (s*0.095, -0.052, z),
        (s*0.035, -0.064, z),
    ]

CURVES = []
for level, z in enumerate(RIB_LEVELS, 1):
    CURVES.append({'name': f'left_rib_{level}', 'radius': RIB_RADIUS, 'points': rib_points(-1, z)})
    CURVES.append({'name': f'right_rib_{level}', 'radius': RIB_RADIUS, 'points': rib_points(1, z)})

# A thin sternum closes the front of the rib cage without touching the heart.
CURVES.append({'name':'sternum','radius':0.0038,'points':[(0.0,-0.055,1.255),(0.0,-0.055,1.455)]})

# Pass 14 anatomical reinforcement: paired lower-arm/lower-leg bones, shoulder blades,
# and a pelvic bowl. These remain lightweight solid curves but read much more like
# a skeleton than one cylinder per limb.
CURVES.extend([
    {'name':'left_ulna','radius':0.0033,'points':[(-0.255,0.074,1.225),(-0.298,0.052,1.120),(-0.342,0.034,1.020)]},
    {'name':'right_ulna','radius':0.0033,'points':[(0.255,0.074,1.225),(0.298,0.050,1.120),(0.340,0.032,1.020)]},
    {'name':'left_fibula','radius':0.0035,'points':[(-0.112,0.044,0.515),(-0.116,0.055,0.330),(-0.139,0.078,0.150)]},
    {'name':'right_fibula','radius':0.0035,'points':[(0.112,0.044,0.515),(0.116,0.055,0.330),(0.139,0.078,0.150)]},
    {'name':'left_scapula','radius':0.0036,'points':[(-0.030,0.088,1.425),(-0.105,0.096,1.455),(-0.166,0.080,1.430),(-0.112,0.090,1.350),(-0.030,0.088,1.425)]},
    {'name':'right_scapula','radius':0.0036,'points':[(0.030,0.088,1.425),(0.105,0.096,1.455),(0.166,0.080,1.430),(0.112,0.090,1.350),(0.030,0.088,1.425)]},
    {'name':'left_pelvis_wing','radius':0.0041,'points':[(0.000,0.052,0.925),(-0.065,0.073,0.952),(-0.118,0.052,0.935),(-0.132,0.030,0.900),(-0.100,0.025,0.880)]},
    {'name':'right_pelvis_wing','radius':0.0041,'points':[(0.000,0.052,0.925),(0.065,0.073,0.952),(0.118,0.052,0.935),(0.132,0.030,0.900),(0.100,0.025,0.880)]},
])

# Pass 13 formed skull: a faceted solid cranium cap plus recognizable facial bones.
# The cranium itself is emitted as a thick low-poly shell in main.py; these curves
# form the brow, orbital rims, cheek bones, nasal bridge, maxilla, and mandible.

def ellipse_ring(cx, cy, cz, rx, rz, segments=8):
    pts=[]
    for i in range(segments+1):
        a=2.0*math.pi*i/segments
        pts.append((cx+rx*math.cos(a),cy,cz+rz*math.sin(a)))
    return pts

CURVES.extend([
    {'name':'skull_brow','radius':0.0040,'points':[(-0.050,-0.040,1.710),(-0.025,-0.050,1.720),(0.000,-0.052,1.722),(0.025,-0.050,1.720),(0.050,-0.040,1.710)]},
    {'name':'left_orbit','radius':0.0034,'points':ellipse_ring(-0.026,-0.043,1.692,0.016,0.016,8)},
    {'name':'right_orbit','radius':0.0034,'points':ellipse_ring(0.026,-0.043,1.692,0.016,0.016,8)},
    {'name':'left_cheek','radius':0.0036,'points':[(-0.042,-0.030,1.695),(-0.049,-0.024,1.675),(-0.046,-0.018,1.650)]},
    {'name':'right_cheek','radius':0.0036,'points':[(0.042,-0.030,1.695),(0.049,-0.024,1.675),(0.046,-0.018,1.650)]},
    {'name':'nasal_bridge','radius':0.0034,'points':[(0.000,-0.053,1.705),(0.000,-0.057,1.675),(0.000,-0.053,1.660)]},
    {'name':'maxilla','radius':0.0034,'points':[(-0.043,-0.046,1.665),(-0.022,-0.052,1.660),(0.000,-0.054,1.658),(0.022,-0.052,1.660),(0.043,-0.046,1.665)]},
    {'name':'mandible','radius':0.0038,'points':[(-0.046,-0.016,1.650),(-0.044,-0.027,1.635),(-0.027,-0.036,1.620),(0.000,-0.040,1.615),(0.027,-0.036,1.620),(0.044,-0.027,1.635),(0.046,-0.016,1.650)]},
])

SKULL = {
    'center': (0.000, 0.018, 1.692),
    'outer_radii': (0.058, 0.060, 0.064),
    'thickness': 0.0042,
    # Angular patch: back/top/sides are closed solid bone; the face/front is open.
    'theta_min_deg': -10.0,
    'theta_max_deg': 190.0,
    'phi_min_deg': 12.0,
    'phi_max_deg': 150.0,
    'slices': 18,
    'stacks': 12,
}

JOINT_RADIUS = 0.0070
def joint_radius_for(name):
    base = FINGER_JOINT_RADIUS if any(tok in name for tok in FINGER_NAMES) else JOINT_RADIUS
    return base * JOINT_RADIUS_MULTIPLIER
BODY_KEEP_OUT = 0.0030
ORGAN_KEEP_OUT = 0.0040


def ellipsoid_points(center, radii, count):
    cx,cy,cz=center; rx,ry,rz=radii
    phi=(1.0+math.sqrt(5.0))*0.5
    out=[]
    for i in range(count):
        z=1.0-2.0*(i+0.5)/count
        theta=2.0*math.pi*i/phi
        rr=math.sqrt(max(0.0,1.0-z*z))
        out.append((cx+rx*rr*math.cos(theta), cy+ry*rr*math.sin(theta), cz+rz*z))
    return out


def dist(a,b):
    return math.sqrt(sum((float(a[i])-float(b[i]))**2 for i in range(3)))


def segment_samples(a,b,spacing=0.004):
    length=dist(a,b)
    steps=max(2,int(math.ceil(length/spacing))+1)
    return [tuple(a[k]+(b[k]-a[k])*i/(steps-1) for k in range(3)) for i in range(steps)]


def clearance(points, targets):
    return min(dist(p,q) for p in points for q in targets)

body_data=json.loads(BODY.read_text())
surface=[tuple(p['p']) for p in body_data['points']]
organ_points=[]
for name,recipe in ORGAN_RECIPES.items():
    for p in ellipsoid_points(recipe['center'],recipe['radii'],recipe['count']):
        organ_points.append((name,p))
organ_xyz=[p for _,p in organ_points]

records=[]
all_segments=[]
for name,a_name,b_name,radius in BONES:
    all_segments.append((name,JOINTS[a_name],JOINTS[b_name],radius*BONE_RADIUS_MULTIPLIER,'bone'))
for curve in CURVES:
    pts=curve['points']
    for i,(a,b) in enumerate(zip(pts[:-1],pts[1:])):
        all_segments.append((f"{curve['name']}_{i+1}",a,b,curve['radius']*CURVE_RADIUS_MULTIPLIER,'curve'))

minimum_shell=999.0
minimum_organ=999.0
violations=[]
for name,a,b,radius,kind in all_segments:
    samples=segment_samples(a,b)
    shell_net=clearance(samples,surface)-radius
    organ_net=clearance(samples,organ_xyz)-radius
    minimum_shell=min(minimum_shell,shell_net)
    minimum_organ=min(minimum_organ,organ_net)
    if shell_net <= BODY_KEEP_OUT or organ_net <= ORGAN_KEEP_OUT:
        violations.append({'name':name,'shell_net':shell_net,'organ_net':organ_net})
    records.append({'name':name,'a':list(a),'b':list(b),'radius':radius,'kind':kind,'shell_clearance_m':shell_net,'organ_clearance_m':organ_net})

joint_min_shell=999.0
joint_min_organ=999.0
joint_records=[]
for name,p in JOINTS.items():
    jr=joint_radius_for(name)
    shell_net=min(dist(p,q) for q in surface)-jr
    organ_net=min(dist(p,q) for q in organ_xyz)-jr
    joint_min_shell=min(joint_min_shell,shell_net)
    joint_min_organ=min(joint_min_organ,organ_net)
    if shell_net <= BODY_KEEP_OUT or organ_net <= ORGAN_KEEP_OUT:
        violations.append({'name':'joint:'+name,'shell_net':shell_net,'organ_net':organ_net})
    joint_records.append({'name':name,'pos':list(p),'radius':jr,'shell_clearance_m':shell_net,'organ_clearance_m':organ_net})



def skull_surface_points(spec, resolution_scale=2):
    cx,cy,cz=spec['center']; rx,ry,rz=spec['outer_radii']; t=spec['thickness']
    theta0=math.radians(spec['theta_min_deg']); theta1=math.radians(spec['theta_max_deg'])
    phi0=math.radians(spec['phi_min_deg']); phi1=math.radians(spec['phi_max_deg'])
    slices=max(8,int(spec['slices']*resolution_scale)); stacks=max(6,int(spec['stacks']*resolution_scale))
    out_outer=[]; out_inner=[]
    ir=(rx-t,ry-t,rz-t)
    for si in range(stacks+1):
        phi=phi0+(phi1-phi0)*si/stacks
        sp=math.sin(phi); cp=math.cos(phi)
        for ti in range(slices+1):
            theta=theta0+(theta1-theta0)*ti/slices
            ct=math.cos(theta); st=math.sin(theta)
            out_outer.append((cx+rx*sp*ct,cy+ry*sp*st,cz+rz*cp))
            out_inner.append((cx+ir[0]*sp*ct,cy+ir[1]*sp*st,cz+ir[2]*cp))
    return out_outer,out_inner

skull_outer,skull_inner=skull_surface_points(SKULL)
skull_shell_clearance=min(dist(p,q) for p in skull_outer for q in surface)
skull_organ_clearance=min(dist(p,q) for p in (skull_outer+skull_inner) for q in organ_xyz)
if skull_shell_clearance <= BODY_KEEP_OUT:
    violations.append({'name':'formed_skull:outer_shell','shell_net':skull_shell_clearance,'organ_net':skull_organ_clearance})
if skull_organ_clearance <= ORGAN_KEEP_OUT:
    violations.append({'name':'formed_skull:inner_shell','shell_net':skull_shell_clearance,'organ_net':skull_organ_clearance})

# Rig metadata and deterministic body binding map. The skeleton is the parent authority:
# every surface glyph is bound to one joint branch instead of sitting independently under render.

def nearest_joint_name(point, names):
    return min(names, key=lambda name: dist(point, JOINTS[name]))


def point_segment_distance(point, a, b):
    """Return (distance, t) from point to the finite segment a->b.

    Pass 18 uses actual limb envelopes instead of the old z>=0.79 rectangle.
    The old cutoff split the sampled hands horizontally: hand glyphs below 0.79 m
    were classified as pelvis/leg matter and visibly stayed behind when elbows bent.
    """
    p=tuple(map(float,point)); a=tuple(map(float,a)); b=tuple(map(float,b))
    ab=tuple(b[i]-a[i] for i in range(3)); ap=tuple(p[i]-a[i] for i in range(3))
    den=sum(v*v for v in ab) or 1.0
    t=max(0.0,min(1.0,sum(ap[i]*ab[i] for i in range(3))/den))
    q=tuple(a[i]+ab[i]*t for i in range(3))
    return dist(p,q),t


def arm_binding(point, side):
    """Classify a surface sample against the authored arm centerline.

    Each envelope has its own lateral/vertical gate so torso/hip samples are not
    stolen merely because the hanging arm passes nearby.  The hand envelope is
    extended through the real sampled fingertips (~0.744 m), eliminating the
    detached hand patch seen in Pass 17.
    """
    x,y,z=map(float,point); ax=abs(x)
    shoulder=JOINTS[f'{side}_shoulder']; elbow=JOINTS[f'{side}_elbow']
    wrist=JOINTS[f'{side}_wrist']; hand=JOINTS[f'{side}_hand']
    sign=-1.0 if side=='left' else 1.0
    hand_tip=(sign*0.402,-0.055,0.745)
    candidates=[]
    d,t=point_segment_distance(point,shoulder,elbow)
    if ax>=0.140 and 1.17<=z<=1.52 and d<=0.092:
        # Upper-arm skin remains under shoulder until the distal elbow cap.
        candidates.append((d/0.092, f'{side}_shoulder' if t<0.82 else f'{side}_elbow'))
    d,t=point_segment_distance(point,elbow,wrist)
    if ax>=0.195 and 0.96<=z<=1.29 and d<=0.088:
        # Forearm is an elbow descendant; only the distal cuff follows wrist.
        candidates.append((d/0.088, f'{side}_elbow' if t<0.82 else f'{side}_wrist'))
    d,t=point_segment_distance(point,wrist,hand)
    if ax>=0.275 and 0.82<=z<=1.07 and d<=0.100:
        candidates.append((d/0.100, f'{side}_wrist' if t<0.55 else f'{side}_hand'))
    d,t=point_segment_distance(point,hand,hand_tip)
    if ax>=0.285 and 0.70<=z<=0.96 and d<=0.110:
        candidates.append((d/0.110, f'{side}_hand'))
    if not candidates:
        return None
    return min(candidates,key=lambda item:item[0])[1]


def body_binding(point):
    x,y,z = map(float, point)
    side = 'left' if x < 0 else 'right'
    if z >= 1.575:
        return 'head_base'
    arm=arm_binding(point,side)
    if arm is not None:
        return arm
    if z <= 0.12:
        return f'{side}_foot'
    if z < 0.90:
        return nearest_joint_name(point, [f'{side}_hip',f'{side}_knee',f'{side}_ankle',f'{side}_foot'])
    if z < 1.055:
        return 'pelvis'
    if z < 1.22:
        return 'spine_mid'
    if z < 1.49:
        return 'spine_high'
    return 'neck'

body_bindings=[body_binding(p) for p in surface]
organ_bindings={
    'brain':'head_base',
    'left_lung':'spine_high','right_lung':'spine_high','heart':'spine_high',
    'stomach':'spine_mid','liver':'spine_mid','left_kidney':'spine_low','right_kidney':'spine_low',
}
curve_bindings={}
for c in CURVES:
    n=c['name']
    if n.startswith('skull_') or n in ('left_orbit','right_orbit','left_cheek','right_cheek','nasal_bridge','maxilla','mandible'):
        curve_bindings[n]='head_base'
    elif n.startswith('left_ulna'):
        curve_bindings[n]='left_elbow'
    elif n.startswith('right_ulna'):
        curve_bindings[n]='right_elbow'
    elif n.startswith('left_fibula'):
        curve_bindings[n]='left_knee'
    elif n.startswith('right_fibula'):
        curve_bindings[n]='right_knee'
    elif 'pelvis' in n:
        curve_bindings[n]='pelvis'
    else:
        curve_bindings[n]='spine_high'

payload={
    'version':6,
    'role':'solid internal structural skeleton; Pass 29 mass/occlusion polish with thicker bones, larger joints, thicker cranium, corrected elbow pivots, and independent articulation with fingered hands',
    'color':[0.52,0.57,0.50,1.0],
    'bone_radius_multiplier':BONE_RADIUS_MULTIPLIER,
    'curve_radius_multiplier':CURVE_RADIUS_MULTIPLIER,
    'joint_radius_multiplier':JOINT_RADIUS_MULTIPLIER,
    'rig_parent':RIG_PARENT,
    'body_bindings':body_bindings,
    'organ_bindings':organ_bindings,
    'curve_bindings':curve_bindings,
    'skull_joint':'head_base',
    'joints':{k:list(v) for k,v in JOINTS.items()},
    'joint_radius':JOINT_RADIUS,
    'joint_radii':{name:joint_radius_for(name) for name in JOINTS},
    'finger_names':list(FINGER_NAMES),
    'bones':[{'name':n,'a':a,'b':b,'radius':r*BONE_RADIUS_MULTIPLIER} for n,a,b,r in BONES],
    'curves':[dict(c, radius=float(c['radius'])*CURVE_RADIUS_MULTIPLIER) for c in CURVES],
    'skull':SKULL,
    'metrics':{
        'body_glyph_count':len(surface),
        'organ_glyph_count':len(organ_xyz),
        'joint_count':len(JOINTS),
        'primary_bone_count':len(BONES),
        'curve_count':len(CURVES),
        'render_segment_count':len(all_segments),
        'formed_skull_mesh_count':1,
        'formed_skull_outer_shell_clearance_m':skull_shell_clearance,
        'formed_skull_organ_clearance_m':skull_organ_clearance,
        'minimum_segment_shell_clearance_m':minimum_shell,
        'minimum_segment_organ_clearance_m':minimum_organ,
        'minimum_joint_shell_clearance_m':joint_min_shell,
        'minimum_joint_organ_clearance_m':joint_min_organ,
        'required_shell_clearance_m':BODY_KEEP_OUT,
        'required_organ_clearance_m':ORGAN_KEEP_OUT,
        'violations':violations,
    },
    'segment_audit':records,
    'joint_audit':joint_records,
}
OUT.write_text(json.dumps(payload,indent=2)+'\n')
print(json.dumps(payload['metrics'],indent=2))
if violations:
    raise SystemExit(1)
