"""Focused active-module source audit for Entropy Pass 31."""
from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
manifest = json.loads((ROOT / 'build_manifest.json').read_text(encoding='utf-8'))
modules = list(manifest.get('active_modules', ()))
parse_errors = []
duplicates = []
missing = []
compile_errors = []

for rel in modules:
    path = ROOT / rel
    if not path.is_file():
        missing.append(rel)
        continue
    source = path.read_text(encoding='utf-8')
    try:
        tree = ast.parse(source, filename=rel)
        compile(source, rel, 'exec')
    except Exception as exc:
        parse_errors.append({'file': rel, 'error': str(exc)})
        continue
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            seen = set()
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if item.name in seen:
                        duplicates.append({'file': rel, 'class': node.name, 'method': item.name})
                    seen.add(item.name)

runtime = (ROOT / 'runtime_paths.py').read_text(encoding='utf-8')
core = (ROOT / 'space_core.py').read_text(encoding='utf-8')
crash = (ROOT / 'crash_reporter.py').read_text(encoding='utf-8')
contract_checks = {
    'manifest_pass_31_or_newer': int(manifest.get('pass', 0)) >= 31,
    'crash_reporter_active': 'crash_reporter.py' in modules,
    'save_schema_v5_preserved': '"schema_version": 5' in core,
    'atomic_replace_present': 'os.replace(tmp_name, path)' in runtime,
    'save_fsync_present': 'os.fsync(handle.fileno())' in runtime,
    'previous_good_present': 'SAVE_BACKUP_PATH' in runtime and 'previous_good' in runtime,
    'readback_verification_present': 'save verification failed' in runtime,
    'session_marker_present': 'SESSION_STATE_PATH' in runtime and 'mark_session_clean_exit' in core,
    'crash_zip_integrity_present': 'archive.testzip()' in crash and 'zip_tmp.stat().st_size <= 0' in crash,
    'no_auto_upload_contract': '"automatic_upload": False' in crash,
    'no_save_contents_contract': '"save_contents_included": False' in crash,
    'suspend_gap_pause_present': 'lifecycle_frame_count > 0 and dt > 1.0' in core and 'SESSION RESUMED — EXPEDITION PAUSED' in core,
    'planet_loading_excluded_from_suspend': 'planet_entry_pending or planet_entry_surface_ready' in core and 'transition_gap_grace_frames > 0' in core,
    'warp_goal_gate_present': 'warp_unlocked' in core and 'resolve current system goal before warp' in core,
    'dead_target_recycle_present': 'resolve_target_loss("system_collapse")' in core and 'resolve_target_loss("planet_destroyed")' in core,
    'periodic_checkpoint_present': 'AUTOSAVE_SECONDS = 20.0' in core and 'periodic_20s' in core,
}
status = 'PASS' if not (parse_errors or duplicates or missing or compile_errors) and all(contract_checks.values()) else 'FAIL'
out = {
    'pass': 'Entropy Pass 31 — Expedition Flow Integrity',
    'status': status,
    'active_modules': len(modules),
    'missing_modules': missing,
    'parse_errors': parse_errors,
    'compile_errors': compile_errors,
    'duplicate_class_methods': duplicates,
    'contract_checks': contract_checks,
}
(ROOT / 'Entropy_Pass31_code_audit.json').write_text(json.dumps(out, indent=2) + '\n', encoding='utf-8')
print(json.dumps(out, indent=2))
if status != 'PASS':
    raise SystemExit(1)
