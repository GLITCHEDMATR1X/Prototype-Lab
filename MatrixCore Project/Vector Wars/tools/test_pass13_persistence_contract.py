#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
main_text = (ROOT / 'main.py').read_text(encoding='utf-8')
save_text = (ROOT / 'campaign_save.py').read_text(encoding='utf-8')

checks = {
    'campaign save path is user data': 'CAMPAIGN_SAVE_PATH = USER_DATA_DIR / "campaign_save.json"' in main_text,
    'startup restore': 'restore_campaign_save(' in main_text and 'load_campaign_save(CAMPAIGN_SAVE_PATH)' in main_text,
    'campaign-owned mode restored': '_apply_combat_mode(phase_progression.active_mode)' in main_text,
    'kill progress persisted': '_persist_campaign()' in main_text,
    'replay clears campaign save': 'clear_campaign_save(CAMPAIGN_SAVE_PATH)' in main_text,
    'atomic replace': 'os.replace(tmp, path)' in save_text,
    'schema versioned': 'SCHEMA_VERSION = 1' in save_text,
}
failed = [name for name, ok in checks.items() if not ok]
for name, ok in checks.items():
    print(('PASS ' if ok else 'FAIL ') + name)
if failed:
    raise SystemExit(1)
print('pass13_persistence_contract: PASS')
