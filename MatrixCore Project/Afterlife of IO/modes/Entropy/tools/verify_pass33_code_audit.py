#!/usr/bin/env python3
"""Active-module and resilience audit for Entropy Pass 33."""
from __future__ import annotations
import ast, json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
manifest=json.loads((ROOT/'build_manifest.json').read_text(encoding='utf-8'))
modules=list(manifest.get('active_modules',()))
missing=[]; parse_errors=[]; duplicates=[]
for rel in modules:
    path=ROOT/rel
    if not path.is_file():
        missing.append(rel); continue
    src=path.read_text(encoding='utf-8')
    try:
        tree=ast.parse(src,filename=rel); compile(src,rel,'exec')
    except Exception as exc:
        parse_errors.append({'file':rel,'error':str(exc)}); continue
    for node in ast.walk(tree):
        if isinstance(node,ast.ClassDef):
            seen=set()
            for item in node.body:
                if isinstance(item,(ast.FunctionDef,ast.AsyncFunctionDef)):
                    if item.name in seen: duplicates.append({'file':rel,'class':node.name,'method':item.name})
                    seen.add(item.name)
core=(ROOT/'space_core.py').read_text(encoding='utf-8')
runtime=(ROOT/'runtime_paths.py').read_text(encoding='utf-8')
crash=(ROOT/'crash_reporter.py').read_text(encoding='utf-8')
identity=(ROOT/'expedition_identity.py').read_text(encoding='utf-8')
checks={
 'manifest_pass_33':manifest.get('pass')==33,
 'active_module_count_19':len(modules)==19,  # Pass 34 adds ruin_dive.py
 'identity_module_active':'expedition_identity.py' in modules,
 'save_schema_v5':'"schema_version": 5' in core,
 'atomic_save':'os.replace(tmp_name, path)' in runtime and 'os.fsync(handle.fileno())' in runtime,
 'previous_good':'SAVE_BACKUP_PATH' in runtime and 'previous_good' in runtime,
 'crash_zip_integrity':'archive.testzip()' in crash,
 'no_auto_upload':'"automatic_upload": False' in crash,
 'bounded_motion_delta':'dt = min(max(0.0, wall_dt), 0.050)' in core,
 'suspend_uses_wall_delta':'lifecycle_frame_count > 0 and wall_dt > 1.0' in core,
 'planet_loading_excluded':'planet_entry_pending or planet_entry_surface_ready' in core,
 'new_system_variety':'def _generate_varied_system' in core and 'style_variety_score' in core,
 'identity_profiles':'WORLD_ARCHIVE_PROFILES' in identity and 'ARCHIVE_SITE_SEQUENCE' in identity,
}
status='PASS' if not (missing or parse_errors or duplicates) and all(checks.values()) else 'FAIL'
out={'pass':'Entropy Pass 33 — Expedition Identity','status':status,'active_modules':len(modules),'missing_modules':missing,'parse_errors':parse_errors,'duplicate_class_methods':duplicates,'contract_checks':checks}
(ROOT/'Entropy_Pass33_code_audit.json').write_text(json.dumps(out,indent=2)+'\n',encoding='utf-8')
(ROOT/'verification'/'reports'/'pass33_code_audit.json').write_text(json.dumps(out,indent=2)+'\n',encoding='utf-8')
print(json.dumps(out,indent=2))
raise SystemExit(0 if status=='PASS' else 1)
