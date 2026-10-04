#!/usr/bin/env python3
"""Pass 32 smoothness checks plus complete preserved Pass 31 regression."""
from __future__ import annotations
import json, subprocess, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
TOOLS=['verify_pass32_smooth_expedition.py','verify_pass31_full_regression.py']
results=[]
for name in TOOLS:
    proc=subprocess.run([sys.executable,'-B',str(ROOT/'tools'/name)],cwd=str(ROOT),capture_output=True,text=True)
    ok=proc.returncode==0
    results.append({'tool':name,'pass':ok,'returncode':proc.returncode,'stdout_tail':'\n'.join(proc.stdout.splitlines()[-14:]),'stderr_tail':'\n'.join(proc.stderr.splitlines()[-14:])})
    print(('PASS' if ok else 'FAIL')+': '+name)
    if not ok:
        print(proc.stdout); print(proc.stderr,file=sys.stderr); break
status='PASS' if len(results)==len(TOOLS) and all(r['pass'] for r in results) else 'FAIL'
out={'pass':32,'title':'Smooth Expedition Feedback Full Regression','status':status,'suites':results,'passed':sum(1 for r in results if r['pass']),'total':len(TOOLS)}
report=ROOT/'verification'/'reports'/'pass32_regression.json'
report.write_text(json.dumps(out,indent=2)+'\n',encoding='utf-8')
print(f'FINAL_RESULT={status} ({out["passed"]}/{out["total"]})')
print(f'REPORT={report}')
raise SystemExit(0 if status=='PASS' else 1)
