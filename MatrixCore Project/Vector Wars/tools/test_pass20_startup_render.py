from pathlib import Path
src = Path(__file__).resolve().parents[1] / 'main.py'
s = src.read_text(encoding='utf-8')
checks = {
    'startup repair behavior remains present': 'def _present_startup_frame' in s and 'Preparing city and combat systems...' in s,
    'startup frame helper exists': 'def _present_startup_frame' in s,
    'startup frame flips display': 'pygame.display.flip()' in s[s.index('def _present_startup_frame'):s.index('# Internal canvas')],
    'startup pumps event queue': 'pygame.event.pump()' in s[s.index('def _present_startup_frame'):s.index('# Internal canvas')],
    'startup frame before world construction': s.index('_present_startup_frame()') < s.index('city = City(seed=1337)'),
    'second startup status during construction': 'Preparing city and combat systems...' in s,
}
for name, ok in checks.items():
    print(('PASS' if ok else 'FAIL'), name)
if not all(checks.values()): raise SystemExit(1)
print('pass20_startup_render: PASS')
