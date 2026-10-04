"""Run the preserved campaign/hazard/landmark/audio checks for Entropy Pass 28."""
from __future__ import annotations
import json, subprocess, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
commands=[
 ('state_aware_music',['tools/verify_pass28_state_aware_music.py']),
 ('complete_expedition',['tools/verify_pass25_complete_expedition.py']),
 ('home_cache',['tools/verify_pass25_home_cache.py']),
 ('ship_tutorial_gleebs',['tools/verify_pass25_ship_tutorial.py']),
 ('hazard_personality',['tools/verify_pass26_hazard_personality.py']),
 ('surface_landmarks',['tools/verify_pass27_surface_landmarks.py']),
 ('settings_audio',['tools/verify_settings_audio.py']),
 ('code_audit',['tools/verify_pass28_code_audit.py']),
]
results=[]
for name,args in commands:
    proc=subprocess.run([sys.executable,'-B',*args],cwd=ROOT,text=True,capture_output=True)
    results.append({'name':name,'returncode':proc.returncode,'stdout_tail':'\n'.join(proc.stdout.strip().splitlines()[-8:]),'stderr_tail':'\n'.join(proc.stderr.strip().splitlines()[-8:])})
status='PASS' if all(r['returncode']==0 for r in results) else 'FAIL'
out={'pass':28,'status':status,'checks':results}
(ROOT/'Entropy_Pass28_regression.json').write_text(json.dumps(out,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'pass':28,'status':status,'checks':len(results)},indent=2))
if status!='PASS': raise SystemExit(1)
