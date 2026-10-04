#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

TESTS = [
    ROOT / 'tools' / 'test_combat_outcomes.py',
    ROOT / 'tools' / 'test_ground_operation.py',
    ROOT / 'tools' / 'test_ground_recovery.py',
    ROOT / 'tools' / 'test_air_operation.py',
    ROOT / 'tools' / 'test_ocean_operation.py',
    ROOT / 'tools' / 'test_pass04_contract.py',
    ROOT / 'tools' / 'test_pass05_contract.py',
    ROOT / 'tools' / 'test_pass06_contract.py',
    ROOT / 'tools' / 'test_pass07_ground_kill_attribution.py',
    ROOT / 'tools' / 'test_pass09_air_loop.py',
    ROOT / 'tools' / 'test_pass10_air_to_ocean.py',
    ROOT / 'tools' / 'test_pass11_ocean_loop.py',
    ROOT / 'tools' / 'test_pass12_campaign_complete.py',
    ROOT / 'tools' / 'test_campaign_save.py',
    ROOT / 'tools' / 'test_pass13_persistence_contract.py',
    ROOT / 'tools' / 'test_pass14_hud_hierarchy.py',
    ROOT / 'tools' / 'test_music_library.py',
    ROOT / 'tools' / 'test_pass15_phase_music.py',
    ROOT / 'tools' / 'test_gameplay_balance.py',
    ROOT / 'tools' / 'test_pass16_difficulty_authority.py',
    ROOT / 'tools' / 'test_pacing_balance.py',
    ROOT / 'tools' / 'test_pass17_phase_pacing.py',
    ROOT / 'tools' / 'test_weapon_pacing.py',
    ROOT / 'tools' / 'test_pass18_secondary_weapon_authority.py',
    ROOT / 'tools' / 'test_pass19_holoverse_legacy_contract.py',
    ROOT / 'tools' / 'test_pass20_startup_render.py',
    ROOT / 'tools' / 'test_pass21_startup_phase_order.py',
    ROOT / 'tools' / 'test_pass22_display_surface_authority.py',
    ROOT / 'test_phase_progression.py',
]


def main() -> int:
    failures: list[tuple[Path, int]] = []
    for test in TESTS:
        rel = test.relative_to(ROOT)
        print(f'\n=== {rel} ===', flush=True)
        proc = subprocess.run([sys.executable, str(test)], cwd=ROOT)
        if proc.returncode != 0:
            failures.append((rel, proc.returncode))

    print('\n=== REGRESSION SUMMARY ===')
    print(f'run={len(TESTS)} pass={len(TESTS)-len(failures)} fail={len(failures)}')
    if failures:
        for rel, code in failures:
            print(f'FAIL {rel} exit={code}')
        return 1
    print('VECTOR_WARS_REGRESSIONS: PASS')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
