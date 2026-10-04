import json,math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];BC=.017;OC=.015;SP=.060
paths={'spinal_trunk':[(0,.040,1.645),(0,.055,1.560),(0,.060,1.460),(0,.065,1.360),(0,.065,1.250),(0,.060,1.150),(0,.055,1.040),(0,.050,.920)],'left_shoulder':[(-.005,.055,1.480),(-.080,.060,1.470),(-.150,.055,1.430),(-.210,.062,1.370)],'right_shoulder':[(.005,.055,1.480),(.080,.060,1.470),(.150,.055,1.430),(.210,.056,1.370)],'left_arm':[(-.210,.062,1.370),(-.250,.056,1.290),(-.290,.059,1.190),(-.320,.045,1.090),(-.350,.003,.990),(-.380,-.042,.890)],'right_arm':[(.210,.056,1.370),(.250,.064,1.290),(.290,.058,1.190),(.320,.033,1.090),(.350,-.005,.990),(.380,-.038,.890)],'left_leg':[(-.010,.050,.920),(-.060,.055,.840),(-.090,.055,.740),(-.100,.055,.640),(-.105,.055,.530),(-.105,.060,.420),(-.105,.060,.300),(-.105,.065,.180)],'right_leg':[(.010,.050,.920),(.060,.055,.840),(.090,.055,.740),(.100,.055,.640),(.105,.055,.530),(.105,.060,.420),(.105,.060,.300),(.105,.065,.180)]}
rec=[((0,.012,1.690),(.050,.042,.040),24),((-.073,0,1.350),(.036,.023,.095),22),((.073,0,1.350),(.036,.023,.095),22),((0,-.030,1.310),(.023,.014,.030),12),((-.055,.012,1.105),(.032,.020,.042),12),((.055,.007,1.115),(.040,.020,.030),14),((-.065,-.012,1.005),(.018,.014,.026),6),((.065,-.012,1.005),(.018,.014,.026),6)]
def d(a,b):return sum((a[i]-b[i])**2 for i in range(3))**.5
def fib(c,r,n):
 cx,cy,cz=c;rx,ry,rz=r;phi=(1+5**.5)/2;out=[]
 for i in range(n):z=1-2*(i+.5)/n;t=2*math.pi*i/phi;rr=max(0,1-z*z)**.5;out.append((cx+rx*rr*math.cos(t),cy+ry*rr*math.sin(t),cz+rz*z))
 return out
def poly(q):
 out=[]
 for a,b in zip(q[:-1],q[1:]):
  L=d(a,b);n=max(1,math.ceil(L/SP))
  for i in range(n):t=i/n;out.append(tuple(a[k]+(b[k]-a[k])*t for k in range(3)))
 out.append(q[-1]);return out
surf=[tuple(x['p']) for x in json.loads((ROOT/'assets/cache/generic_male_ascii.json').read_text())['points']];org=sum((fib(*x) for x in rec),[]);acc=[];counts={};shell=[];oclear=[];rb=ro=rx=0
for name,path in paths.items():
 kept=0
 for p in poly(path):
  bc=min(d(p,s) for s in surf)
  if bc<BC:rb+=1;continue
  oc=min(d(p,o) for o in org);stem=name=='spinal_trunk' and p[2]>1.60
  if oc<OC and not stem:ro+=1;continue
  if acc and min(d(p,q) for q in acc)<.024:rx+=1;continue
  acc.append(p);kept+=1;shell.append(bc);oclear.append(oc)
 counts[name]=kept
checks={'bounded':35<=len(acc)<=90,'spine':counts['spinal_trunk']>=10,'shoulders':counts['left_shoulder']>=3 and counts['right_shoulder']>=3,'arms':counts['left_arm']>=5 and counts['right_arm']>=5,'legs':counts['left_leg']>=9 and counts['right_leg']>=9,'body_clear':min(shell)>=BC}
out={'result':'PASS' if all(checks.values()) else 'FAIL','checks':checks,'neural_glyph_count':len(acc),'per_path_counts':counts,'minimum_body_shell_clearance_m':round(min(shell),6),'minimum_organ_clearance_m_including_brainstem':round(min(oclear),6),'rejected_for_body_clearance':rb,'rejected_for_organ_clearance':ro,'rejected_for_neural_overlap':rx};(ROOT/'verification/internal_neural.json').write_text(json.dumps(out,indent=2));print(json.dumps(out,indent=2));raise SystemExit(out['result']!='PASS')