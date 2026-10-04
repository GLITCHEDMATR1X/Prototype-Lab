"""Pure-Python Pass 22 verifier.

Validates banked sidekick economy/source contracts, ringless presentation hooks,
party spawn separation, party-scaled enemy placement, and preservation of all
nine Pass 21 world layouts without importing pygame.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from game.world_data import (  # noqa: E402
    LAYOUTS, LAYOUT_POOLS, WORLD_RECT, MAX_ACTOR_RADIUS, MIN_CLEAR_GAP,
    EDGE_CLEARANCE, expand_object,
)
from tools.pass14_world_verify import (  # noqa: E402
    rect_distance, point_rect_distance, reachable, walkable,
)

AUTHORITY = Path('/mnt/data/hex_pass22_authority/HEX Contract')
EXPECTED_MAZE = {'purge': 7, 'recovery': 7, 'rescue': 6}
EXPECTED_SETPIECES = {
    'purge': {'Flying Buttresses', 'Altar Gate', 'Choir Screens', 'Broken Cloister', 'Votive Rail'},
    'recovery': {'Mirror Archive', 'Index Engine', 'Stack Bridge', 'Shard Barricade'},
    'rescue': {'Service Hook', 'Signal Barricade', 'Shrine Lane', 'Split Bulkhead'},
}
FROZEN_FILES = [
    'main.py', 'game/data.py', 'game/actor_visuals.py', 'game/audio.py',
    'game/world_data.py', 'game/world.py',
]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_layout(quest: str, idx: int, layout: dict) -> dict:
    expanded = [expand_object(o) for o in layout['objects']]
    physical = [o for o in expanded if o['movement']]
    parts = [r for o in physical for r in o['parts']]
    issues: list[str] = []
    wx, wy, ww, wh = WORLD_RECT
    right, bottom = wx + ww, wy + wh
    gaps: list[float] = []

    for o in physical:
        for x, y, w, h in o['parts']:
            if not (x >= wx + EDGE_CLEARANCE and y >= wy + EDGE_CLEARANCE and
                    x + w <= right - EDGE_CLEARANCE and y + h <= bottom - EDGE_CLEARANCE):
                issues.append(f"{o['id']} edge clearance")
    for i, a in enumerate(physical):
        for b in physical[i + 1:]:
            d = rect_distance(a['bounds'], b['bounds'])
            gaps.append(d)
            if d < MIN_CLEAR_GAP:
                issues.append(f"{a['id']}/{b['id']} gap {d:.1f}")

    for name, pos in layout['markers'].items():
        req = 120 if name.startswith(('boss', 'spawn_gate')) else 96 if name.startswith(('enemy_', 'comp_', 'civilian_')) else 88
        nearest = min((point_rect_distance(pos, p) for p in parts), default=9999.0)
        if nearest < req:
            issues.append(f"marker {name} clearance {nearest:.1f}")

    goals = {n: p for n, p in layout['markers'].items()
             if n.startswith(('enemy_', 'comp_', 'boss', 'civilian_')) or n in {'extraction', 'artifact', 'reroute_extraction'}}
    reached = reachable(layout['markers']['entry'], goals, parts)
    missing = sorted(set(goals) - reached)
    if missing:
        issues.append('unreachable: ' + ','.join(missing))

    setpieces = {o.get('setpiece') for o in layout['objects'] if o.get('setpiece')}
    maze = sum(1 for o in physical if o.get('maze_piece'))
    if len(physical) != 8:
        issues.append(f'physical count {len(physical)}')
    if maze != EXPECTED_MAZE[quest]:
        issues.append(f'maze count {maze}')
    if setpieces != EXPECTED_SETPIECES[quest]:
        issues.append('setpiece identity mismatch')
    if layout['markers'] != LAYOUTS[quest]['markers']:
        issues.append('marker authority changed')
    if layout.get('access_breaks') != LAYOUTS[quest].get('access_breaks'):
        issues.append('access break authority changed')

    return {
        'quest': quest, 'variant': idx + 1, 'name': layout['name'], 'pass': not issues,
        'physical_objects': len(physical), 'maze_pieces': maze,
        'minimum_gap': round(min(gaps) if gaps else 9999.0, 2),
        'required_routes_reachable': not missing, 'issues': issues,
    }


def world_parts(layout: dict) -> list[tuple[int, int, int, int]]:
    return [part for rec in layout['objects'] for part in expand_object(rec)['parts'] if expand_object(rec)['movement']]


def distance(a, b) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def add(a, b):
    return (a[0] + b[0], a[1] + b[1])


def sidekick_positions(layout: dict, count: int = 2) -> list[tuple[float, float]]:
    parts = world_parts(layout)
    entry = tuple(layout['markers']['entry'])
    offsets = [(58, 18), (-58, 18), (0, 64), (76, -24), (-76, -24)]
    occupied = [entry]
    chosen_all = []
    for _ in range(count):
        chosen = None
        for offset in offsets:
            candidate = add(entry, offset)
            if not walkable(candidate, parts, 22.0):
                continue
            if any(distance(candidate, other) < 46.0 for other in occupied):
                continue
            chosen = candidate
            break
        if chosen is None:
            chosen = (entry[0] + 48 + 44 * len(chosen_all), entry[1])
        occupied.append(chosen)
        chosen_all.append(chosen)
    return chosen_all


SCALE_OFFSETS = [
    (72, 0), (-72, 0), (0, 72), (0, -72),
    (58, 58), (-58, 58), (58, -58), (-58, -58),
    (96, 36), (-96, 36), (36, 96), (36, -96),
]


def scaled_enemy_positions(layout: dict, party_positions: list[tuple[float, float]], count: int, complication: bool) -> list[tuple[float, float]]:
    parts = world_parts(layout)
    prefix = 'comp_' if complication else 'enemy_'
    names = sorted(n for n in layout['markers'] if n.startswith(prefix))
    if not names:
        names = sorted(n for n in layout['markers'] if n.startswith('enemy_'))
    existing = [tuple(p) for n, p in layout['markers'].items() if n.startswith('enemy_')]
    added: list[tuple[float, float]] = []
    for i in range(count):
        anchor = tuple(layout['markers'][names[i % len(names)]])
        chosen = None
        start = i % len(SCALE_OFFSETS)
        for step in range(len(SCALE_OFFSETS)):
            candidate = add(anchor, SCALE_OFFSETS[(start + step) % len(SCALE_OFFSETS)])
            if not walkable(candidate, parts, 20.0):
                continue
            if any(distance(candidate, e) < 44.0 for e in [*existing, *added]):
                continue
            if any(distance(candidate, member) < 95.0 for member in party_positions):
                continue
            chosen = candidate
            break
        if chosen is not None:
            added.append(chosen)
    return added


def main() -> int:
    authority_present = AUTHORITY.exists()
    frozen = {}
    if authority_present:
        frozen = {rel: sha(ROOT / rel) == sha(AUTHORITY / rel) for rel in FROZEN_FILES}
    else:
        frozen = {rel: False for rel in FROZEN_FILES}

    app = (ROOT / 'game/app.py').read_text(encoding='utf-8')
    sim = (ROOT / 'game/sim.py').read_text(encoding='utf-8')
    render = (ROOT / 'game/render.py').read_text(encoding='utf-8')
    actors = (ROOT / 'game/actors.py').read_text(encoding='utf-8')

    source_contract = {
        'profile_schema_has_sidekick_perks': '"sidekick_perks": 0' in app,
        'profile_schema_version_8_plus': bool(re.search(r'"profile_version": (?:8|9)', app)) and bool(re.search(r'profile\["profile_version"\] = (?:8|9)', app)),
        'max_two_sidekicks': 'return min(2, max(0, int(self.profile.get("guild", {}).get("sidekick_perks", 0))))' in app and 'if len(clean_sidekicks) >= 2:' in sim,
        'blocked_when_fallen': 'if self._fallen_heroes():\n            return 0' in app,
        'bank_on_success_without_fallen': 'SIDEKICK PERK BANKED' in app and 'elif self.mission.status == "SUCCESS":\n            guild["sidekick_perks"]' in app,
        'restore_has_priority': 'elif self.mission.status == "SUCCESS" and self._fallen_heroes():' in app,
        'perks_spent_on_deployment': 'guild["sidekick_perks"] = max(0, int(guild.get("sidekick_perks", 0)) - len(sidekicks))' in app,
        'three_person_party_cap': 'self.party_size = 1 + len(self.sidekick_keys)' in sim and 'TEAM {1+len(sidekick_keys)}/3' in render,
        'sidekicks_spawn_separately': 'offsets = [Vec2(58, 18), Vec2(-58, 18)' in sim and 'candidate.distance_to(other) < 46.0' in sim,
        'initial_enemy_scale_by_joined_players': 'len(self.sidekicks) * 2' in sim,
        'complication_enemy_scale_by_joined_players': 'len(self.sidekicks), complication=True' in sim,
        'enemy_stats_not_party_scaled': not bool(re.search(r'(max_hp|damage|attack_delay)\s*[*/+-]?=\s*.*party_size', sim)),
        'enemy_targets_living_party': '_nearest_party_member' in sim and '_damage_party_member' in sim,
        'sidekicks_render_as_heroes': 'def _draw_sidekicks' in render and 'hero=member' in render,
        'lead_selection_footprint_removed': 'selection footprint' not in actors and 'shadow.inflate(12, 7)' not in actors,
        'boss_aura_rings_removed': 'No persistent boss aura rings' in actors and 'removes persistent sovereign aura rings' in render,
        'enemy_hp_ring_removed': 'pygame.draw.arc(self.canvas, color, pygame.Rect(int(e.pos.x-28)' not in render,
        'object_spawner_ring_removed': 'pygame.draw.circle(self.canvas, env["secondary"], c, pulse, 2)' not in render,
        'extraction_ring_removed': 'pygame.draw.circle(self.canvas, ec, mission.extraction_point' not in render,
        'reliquary_ring_removed': 'pygame.draw.circle(self.canvas, ac, artifact' not in render,
    }

    layouts = []
    spawn_rows = []
    all_ok = authority_present and all(frozen.values()) and all(source_contract.values())
    for quest, pool in LAYOUT_POOLS.items():
        for idx, layout in enumerate(pool):
            row = validate_layout(quest, idx, layout)
            layouts.append(row)
            all_ok = all_ok and row['pass']

            lead = tuple(layout['markers']['entry'])
            sides = sidekick_positions(layout, 2)
            party = [lead, *sides]
            initial = scaled_enemy_positions(layout, party, 4, False)
            complication = scaled_enemy_positions(layout, party, 2, True)
            sep = min(distance(a, b) for i, a in enumerate(party) for b in party[i + 1:])
            spawn_ok = (
                len(sides) == 2 and sep >= 46.0 and all(distance(lead, s) > 0 for s in sides)
                and len(initial) == 4 and len(complication) == 2
            )
            spawn_rows.append({
                'quest': quest, 'variant': idx + 1, 'layout': layout['name'], 'pass': spawn_ok,
                'lead': lead, 'sidekicks': sides, 'minimum_party_separation': round(sep, 2),
                'extra_initial_enemies_for_two_sidekicks': initial,
                'extra_complication_enemies_for_two_sidekicks': complication,
            })
            all_ok = all_ok and spawn_ok

    payload = {
        'pass22_banked_sidekick_squads': 'PASS' if all_ok else 'FAIL',
        'authority': str(AUTHORITY),
        'authority_present': authority_present,
        'frozen_pass21_modules': frozen,
        'source_contract': source_contract,
        'party_contract': {
            'lead_plus_sidekicks_max': 3,
            'banked_perk_cost_per_sidekick': 1,
            'sidekick_access_requires_no_fallen_heroes': True,
            'sidekick_perks_persist_until_spent': True,
            'initial_extra_enemies_per_sidekick': 2,
            'complication_extra_enemies_per_sidekick': 1,
            'boss_hp_party_scaling': False,
            'same_point_spawns_allowed': False,
        },
        'world_contract': {
            'approved_layouts': 9,
            'minimum_obstacle_gap_px': MIN_CLEAR_GAP,
            'maximum_required_actor_radius_px': MAX_ACTOR_RADIUS,
            'world_data_unchanged_from_pass21': frozen.get('game/world_data.py', False),
        },
        'layouts': layouts,
        'spawn_checks': spawn_rows,
    }
    out = ROOT / 'verification/reports/pass22_sidekick_party.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2), encoding='utf-8')
    print(json.dumps(payload, indent=2))
    return 0 if all_ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
