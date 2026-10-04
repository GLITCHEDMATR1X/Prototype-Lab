from pathlib import Path
s = Path('main.py').read_text()
checks = {
    'phase progression imported': 'from phase_progression import PhaseProgression' in s,
    'phase progression instantiated': 'phase_progression = PhaseProgression()' in s,
    'ground completion advances campaign': 'phase_progression.advance_ground_to_air()' in s,
    'campaign mode applied': '_apply_combat_mode(phase_progression.active_mode)' in s,
    'air attempt activated': 'combat_outcomes.begin_attempt("AIR")' in s,
    'transition notice': 'GROUND SECURED // AIR PHASE ACTIVE' in s,
    'developer exit restores campaign': 'Leaving developer mode restores the campaign-owned front.' in s,
    'developer tab remains gated': 'if dev_mode and not (ground_assault and ground_recovery.redeploy_required):' in s,
}
for name, ok in checks.items():
    print(('PASS' if ok else 'FAIL'), name)
assert all(checks.values())
print('pass06_contract: PASS')
