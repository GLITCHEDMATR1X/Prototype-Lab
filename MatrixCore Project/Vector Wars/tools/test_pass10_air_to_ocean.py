from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
s = (ROOT / 'main.py').read_text()
p = (ROOT / 'phase_progression.py').read_text()
checks = {
    'air completion advances campaign': 'phase_progression.advance_air_to_ocean()' in s,
    'campaign mode applied after air': '_apply_combat_mode(phase_progression.active_mode)' in s,
    'ocean attempt activated': 'combat_outcomes.begin_attempt("OCEAN")' in s,
    'maritime transition notice': 'AIR SECURED // MARITIME PHASE ACTIVE' in s,
    'phase authority defines air to ocean': 'def advance_air_to_ocean' in p,
    'developer exit still restores campaign': 'Leaving developer mode restores the campaign-owned front.' in s,
}
for name, ok in checks.items():
    print(('PASS' if ok else 'FAIL'), name)
assert all(checks.values())
print('pass10_air_to_ocean: PASS')
