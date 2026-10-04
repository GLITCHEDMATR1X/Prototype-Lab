from __future__ import annotations
import ast, json, hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
checks = []
def check(name, ok, detail=''):
    checks.append((name, bool(ok), str(detail)))

def sha(p):
    h=hashlib.sha256(); h.update(Path(p).read_bytes()); return h.hexdigest()

for p in sorted(ROOT.rglob('*.py')):
    try:
        ast.parse(p.read_text(encoding='utf-8'))
    except Exception as e:
        check('python:'+p.relative_to(ROOT).as_posix(), False, e)
    else:
        check('python:'+p.relative_to(ROOT).as_posix(), True)
for p in sorted(ROOT.rglob('*.json')):
    try:
        json.loads(p.read_text(encoding='utf-8'))
    except Exception as e:
        check('json:'+p.relative_to(ROOT).as_posix(), False, e)
    else:
        check('json:'+p.relative_to(ROOT).as_posix(), True)

mode = (ROOT/'archive3d/mode.py').read_text(encoding='utf-8')
main = (ROOT/'main.py').read_text(encoding='utf-8')
readme = (ROOT/'README.md').read_text(encoding='utf-8')
catalog = json.loads((ROOT/'assets/books/catalog.json').read_text(encoding='utf-8'))
auth = json.loads((ROOT/'verification/source_authority_hashes.json').read_text(encoding='utf-8'))
protected = auth.get('protected_files', {}) if isinstance(auth, dict) else {}

check('pass07_title', 'Planetary Story Systems Pass 07' in main)
check('pass07_readme', 'Planetary Story Systems' in readme)
check('major_system_specs', 'def _major_system_specs' in mode and 'MatrixCore' in mode and 'Afterlife of IO' in mode and 'Entropy' in mode)
check('planetary_layout_logic', 'def _planetary_layout' in mode and 'system["stories"]' in mode and 'system["sims"]' in mode)
check('role_types_present', all(t in mode for t in ['role="planet"', 'role="moon"', 'role="satellite"']))
check('orbital_update_present', 'if ex.orbit_parent is not None and ex.role in {"moon", "satellite"}' in mode and 'orbit_radius' in mode and 'orbit_speed' in mode)
check('interaction_role_prompt', 'PRIMARY WORLD' in mode and 'SIDE STORY' in mode and 'SIMULATION SATELLITE' in mode)
check('same_system_constellation_priority', 'if source.system_id and ex.system_id == source.system_id' in mode)
check('deterministic_section_mapping', 'def _system_for_book' in mode and 'III — PERSONHOOD AND REVIEW' in mode and 'IV — CONTINUITY CASES' in mode)
check('story_length_scales_orbs', 'def _story_size' in mode and 'len(book_text(book))' in mode)
check('true_3d_orbit_planes', 'def _rotate_orbit_vector' in mode and '_rotate_orbit_vector(orbit, ex.orbit_tilt)' in mode)
check('system_orbit_tracks', 'def _make_system_orbit_tracks' in mode and 'self.system_tracks' in mode)
check('primary_simulation_gates', 'primary_simulation_gate_track_' in mode and 'self.primary_sim_gates' in mode)
check('catalog_55_records', len(catalog) == 55, len(catalog))
check('soundtrack_mp3_support_preserved', 'def find_soundtrack()' in (ROOT/'archive3d/data.py').read_text(encoding='utf-8'))
check('nested_dimension_preserved', 'enter_simulation(self.host' in mode and 'suspend_for_nested' in mode and 'resume_from_nested' in mode)
check('fog_windows_compat_preserved', 'fog.setColor(0.004, 0.006, 0.012)' in mode)
book_protected=[rel for rel in protected if rel.startswith('assets/books/')]
mismatches=[]
for rel,expected in protected.items():
    p=ROOT/rel
    if p.is_file() and sha(p)!=expected:
        mismatches.append(rel)
    elif not p.is_file():
        mismatches.append(rel)
check('source_book_layer_exact', len(book_protected)==58 and not [x for x in mismatches if x.startswith('assets/books/')], f'{len(book_protected)} protected')
check('simulation_links_exact', 'saves/simulation_links.json' in protected and 'saves/simulation_links.json' not in mismatches)

passed=sum(1 for _,ok,_ in checks if ok)
summary=f'Archivist Pass07 contract {passed}/{len(checks)}'+(' PASS' if passed==len(checks) else '')
print(summary)
lines=[summary]
for name,ok,detail in checks:
    line=(('PASS' if ok else 'FAIL')+' '+name+((' // '+detail) if detail else ''))
    print(line)
    lines.append(line)
(ROOT/'verification'/'validation_pass07.txt').write_text('\n'.join(lines)+'\n', encoding='utf-8')
raise SystemExit(0 if passed==len(checks) else 1)
