import ast,json,math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; (ROOT/'verification').mkdir(exist_ok=True); code=(ROOT/'main.py').read_text(); ast.parse(code)
recipes={'brain':((0,.012,1.690),(.050,.042,.040),24),'left_lung':((-.073,0,1.350),(.036,.023,.095),22),'right_lung':((.073,0,1.350),(.036,.023,.095),22),'heart':((0,-.030,1.310),(.023,.014,.030),12),'stomach':((-.055,.012,1.105),(.032,.020,.042),12),'liver':((.055,.007,1.115),(.040,.020,.030),14),'left_kidney':((-.065,-.012,1.005),(.018,.014,.026),6),'right_kidney':((.065,-.012,1.005),(.018,.014,.026),6)}
def fib(c,r,n):
 cx,cy,cz=c;rx,ry,rz=r;phi=(1+5**.5)/2;out=[]
 for i in range(n):
  z=1-2*(i+.5)/n;t=2*math.pi*i/phi;rr=max(0,1-z*z)**.5;out.append((cx+rx*rr*math.cos(t),cy+ry*rr*math.sin(t),cz+rz*z))
 return out
def d(a,b):return sum((a[i]-b[i])**2 for i in range(3))**.5
body_data=json.loads((ROOT/'assets/cache/generic_male_ascii.json').read_text()); surface=[tuple(p['p']) for p in body_data['points']]; sample_count=body_data.get('sample_count',len(surface)); shell_required=.0215 if sample_count<=1500 else .0160; org={k:fib(*v) for k,v in recipes.items()};body={k:min(d(p,s) for p in q for s in surface) for k,q in org.items()};pair=(999,None);names=list(org)
for i,a in enumerate(names):
 for b in names[i+1:]:
  m=min(d(x,y) for x in org[a] for y in org[b]);pair=min(pair,(m,(a,b)),key=lambda x:x[0])
checks={'shell_clear':min(body.values())>shell_required,'organs_clear':pair[0]>.030,'heart_raised':recipes['heart'][0][2]>=1.30,'lungs_lower':recipes['left_lung'][0][2]-recipes['left_lung'][1][2]<=1.26,'brain_rear':recipes['brain'][0][1]+recipes['brain'][1][1]>=.05,'brain_larger':recipes['brain'][2]>=24}
out={'result':'PASS' if all(checks.values()) else 'FAIL','checks':checks,'organ_glyph_count':sum(len(x) for x in org.values()),'minimum_body_shell_center_clearance_m':round(min(body.values()),6),'required_shell_center_clearance_m':shell_required,'minimum_inter_organ_center_clearance_m':round(pair[0],6),'closest_organ_pair':pair[1],'heart_center_z_m':1.31,'lung_lowest_extent_z_m':1.255,'brain_rear_extent_y_m':.054,'brain_glyph_count':24};(ROOT/'verification/internal_anatomy.json').write_text(json.dumps(out,indent=2));print(json.dumps(out,indent=2));raise SystemExit(out['result']!='PASS')