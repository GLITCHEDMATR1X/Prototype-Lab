#!/usr/bin/env python3
"""Pass 33 identity checks plus preserved campaign/resilience regressions."""
from __future__ import annotations
import json, subprocess, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
TOOLS=[
 'verify_pass33_expedition_identity.py',
 'verify_pass30_save_crash_lifecycle.py',
 'verify_pass31_expedition_flow.py',
 'verify_pass31_controller_regression.py',
 'verify_pass28_state_aware_music.py',
 'verify_pass25_complete_expedition.py',
 'verify_pass25_home_cache.py',
 'verify_pass25_ship_tutorial.py',
 'verify_pass26_hazard_personality.py',
 'verify_pass27_surface_landmarks.py',
 'verify_settings_audio.py',
 'verify_pass33_code_audit.py',
]
results=[]
for name in TOOLS:
    proc=subprocess.run([sys.executable,'-B',str(ROOT/'tools'/name)],cwd=str(ROOT),capture_output=True,text=True)
    ok=proc.returncode==0
    results.append({'tool':name,'pass':ok,'returncode':proc.returncode,'stdout_tail':'\n'.join(proc.stdout.splitlines()[-12:]),'stderr_tail':'\n'.join(proc.stderr.splitlines()[-12:])})
    print(('PASS' if ok else 'FAIL')+': '+name)
    if not ok:
        print(proc.stdout); print(proc.stderr,file=sys.stderr); break
status='PASS' if len(results)==len(TOOLS) and all(r['pass'] for r in results) else 'FAIL'
out={'pass':33,'title':'Expedition Identity Full Regression','status':status,'suites':results,'passed':sum(1 for r in results if r['pass']),'total':len(TOOLS)}
report=ROOT/'verification'/'reports'/'pass33_regression.json'
report.write_text(json.dumps(out,indent=2)+'\n',encoding='utf-8')
(ROOT/'Entropy_Pass33_regression.json').write_text(json.dumps(out,indent=2)+'\n',encoding='utf-8')
print(f'FINAL_RESULT={status} ({out["passed"]}/{out["total"]})')
print(f'REPORT={report}')
raise SystemExit(0 if status=='PASS' else 1)
