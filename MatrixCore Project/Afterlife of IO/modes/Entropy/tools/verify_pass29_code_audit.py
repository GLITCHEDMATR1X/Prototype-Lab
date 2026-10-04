"""Focused active-module source audit for Entropy Pass 29."""
from __future__ import annotations
import ast, json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
manifest=json.loads((ROOT/'build_manifest.json').read_text(encoding='utf-8'))
modules=list(manifest.get('active_modules',()))
parse_errors=[]; duplicates=[]; missing=[]
for rel in modules:
    path=ROOT/rel
    if not path.is_file():
        missing.append(rel); continue
    try:
        tree=ast.parse(path.read_text(encoding='utf-8'), filename=rel)
    except Exception as exc:
        parse_errors.append({'file':rel,'error':str(exc)}); continue
    for node in ast.walk(tree):
        if isinstance(node,ast.ClassDef):
            seen=set()
            for item in node.body:
                if isinstance(item,(ast.FunctionDef,ast.AsyncFunctionDef)):
                    if item.name in seen:
                        duplicates.append({'file':rel,'class':node.name,'method':item.name})
                    seen.add(item.name)
status='PASS' if not (parse_errors or duplicates or missing) else 'FAIL'
out={'pass':'Entropy Pass 29 — Controller-First Expedition','status':status,'active_modules':len(modules),'missing_modules':missing,'parse_errors':parse_errors,'duplicate_class_methods':duplicates}
(ROOT/'Entropy_Pass29_code_audit.json').write_text(json.dumps(out,indent=2)+'\n',encoding='utf-8')
print(json.dumps(out,indent=2))
if status!='PASS': raise SystemExit(1)
