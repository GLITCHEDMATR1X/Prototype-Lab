from __future__ import annotations

import ast
import json
import os
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
TEST_ROOT = Path(tempfile.mkdtemp(prefix='entropy_pass30_verify_'))
os.environ['ENTROPY_USER_DATA'] = str(TEST_ROOT / 'userdata')

checks = []

def require(cond, label, detail=''):
    ok = bool(cond)
    checks.append({'pass': ok, 'label': label, 'detail': str(detail)})
    print(('PASS' if ok else 'FAIL') + ': ' + label + (f' — {detail}' if detail else ''))
    if not ok:
        raise AssertionError(label)

try:
    import runtime_paths as rp
    import crash_reporter as cr

    # Parse every active Python module before exercising persistence.
    manifest = json.loads((ROOT / 'build_manifest.json').read_text(encoding='utf-8'))
    for name in manifest.get('active_modules', []):
        ast.parse((ROOT / name).read_text(encoding='utf-8'), filename=name)
    require(True, 'all active runtime modules parse')

    payload1 = {'schema_version': 5, 'cargo': {'salvage': 4}, 'secret_test_marker': 'DO_NOT_BUNDLE_SAVE_CONTENTS'}
    payload2 = {'schema_version': 5, 'cargo': {'salvage': 9}, 'mission': {'campaign_phase': 'expedition'}}
    rp.write_save(payload1)
    require(rp.SAVE_PATH.is_file() and rp.SAVE_PATH.stat().st_size > 0, 'primary save is durable and non-empty')
    require(json.loads(rp.SAVE_PATH.read_text(encoding='utf-8'))['cargo']['salvage'] == 4, 'primary save round-trips')
    require(rp.SAVE_BACKUP_PATH.is_file() and rp.SAVE_BACKUP_PATH.stat().st_size > 0, 'first valid save seeds a recovery generation')

    rp.write_save(payload2)
    require(rp.SAVE_BACKUP_PATH.is_file() and rp.SAVE_BACKUP_PATH.stat().st_size > 0, 'previous-good generation created')
    backup = json.loads(rp.SAVE_BACKUP_PATH.read_text(encoding='utf-8'))
    require(backup['cargo']['salvage'] == 4, 'previous-good keeps prior valid generation')

    rp.SAVE_PATH.write_text('{ truncated json', encoding='utf-8')
    recovered = rp.read_save()
    info = rp.get_last_save_read_info()
    require(recovered.get('cargo', {}).get('salvage') == 4, 'corrupt primary recovers previous-good')
    require(info.get('recovered') and info.get('source') == 'previous_good', 'save recovery reports its source')
    repaired = json.loads(rp.SAVE_PATH.read_text(encoding='utf-8'))
    require(repaired.get('cargo', {}).get('salvage') == 4, 'recovery repairs primary save atomically')

    first = rp.mark_session_started('Pass 30 Test', verification=False)
    require(not first.get('previous_unclean'), 'first lifecycle start is clean')
    rp.mark_session_checkpoint('focus_loss')
    state = json.loads(rp.SESSION_STATE_PATH.read_text(encoding='utf-8'))
    require(state.get('state') == 'active' and state.get('last_checkpoint_reason') == 'focus_loss', 'lifecycle checkpoint records reason')
    second = rp.mark_session_started('Pass 30 Test', verification=False)
    require(second.get('previous_unclean'), 'active prior session is detected as unclean')
    rp.mark_session_clean_exit()
    third = rp.mark_session_started('Pass 30 Test', verification=False)
    require(not third.get('previous_unclean'), 'clean exit does not produce false unclean warning')
    rp.mark_session_crashed('ENT-VERIFY')
    fourth = rp.mark_session_started('Pass 30 Test', verification=False)
    require(fourth.get('previous_unclean'), 'confirmed prior crash is detected on next launch')
    rp.mark_session_clean_exit()

    # Recreate a valid primary containing a marker that must never enter a crash bundle.
    rp.write_save(payload1)
    rp.RUNTIME_LOG.write_text(f'private path: {Path.home()} / {rp.USER_ROOT}\n', encoding='utf-8')
    cr.install('Pass 30 Test')
    cr.set_context_provider(lambda: {
        'campaign_phase': 'expedition', 'system_index': 3, 'data_fragments': 2,
        'collapse_state': 'CRITICAL', 'collapse_remaining': 8.5,
    })
    try:
        raise RuntimeError('synthetic pass30 crash')
    except RuntimeError:
        exc_type, exc, tb = sys.exc_info()
        bundle = cr.report_exception(exc_type, exc, tb, phase='verification')
    require(bundle is not None and bundle.is_file() and bundle.stat().st_size > 0, 'crash ZIP is verified and non-empty')
    require(rp.FAULT_LOG.is_file() and rp.FAULT_LOG.stat().st_size > 0, 'fault-handler log is never zero-byte')
    with zipfile.ZipFile(bundle, 'r') as z:
        require(z.testzip() is None, 'crash ZIP integrity passes')
        names = set(z.namelist())
        require(any(n.endswith('.json') for n in names) and any(n.endswith('.txt') for n in names), 'crash ZIP contains human and machine reports')
        combined = b'\n'.join(z.read(n) for n in names)
    require(b'DO_NOT_BUNDLE_SAVE_CONTENTS' not in combined, 'crash ZIP excludes save-file contents')
    require(str(Path.home()).encode() not in combined, 'crash ZIP redacts home-directory paths')
    require(b'synthetic pass30 crash' in combined, 'crash ZIP contains actionable exception')
    require(b'"automatic_upload": false' in combined, 'crash report records local-only privacy contract')
    cr.shutdown()

    core = (ROOT / 'space_core.py').read_text(encoding='utf-8')
    require('AUTOSAVE_SECONDS = 20.0' in core and 'periodic_20s' in core, '20-second periodic autosave is wired')
    require('lifecycle_frame_count > 0 and dt > 1.0' in core and 'SESSION RESUMED — EXPEDITION PAUSED' in core, 'long resume gap pauses after first gameplay frame')
    require('WINDOW FOCUS LOST — EXPEDITION PAUSED' in core, 'focus loss remains pause-safe')
    require('CONTROLLER DISCONNECTED — KEYBOARD / MOUSE REMAIN AVAILABLE' in core, 'controller disconnect remains pause-safe')
    require('mark_session_clean_exit()' in core, 'clean shutdown lifecycle marker is wired')
    require('"schema_version": 5' in core, 'save schema remains v5')

    report = {
        'pass': 30,
        'title': 'Save/Crash Hardening + Suspend Resilience',
        'checks': len(checks),
        'passed': sum(1 for c in checks if c['pass']),
        'failed': [c for c in checks if not c['pass']],
        'result': 'PASS' if all(c['pass'] for c in checks) else 'FAIL',
    }
    out = ROOT / 'Entropy_Pass30_save_crash_validation.json'
    out.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(f"CHECKS={report['passed']}/{report['checks']}")
    print(f"FINAL_RESULT={report['result']}")
finally:
    shutil.rmtree(TEST_ROOT, ignore_errors=True)
