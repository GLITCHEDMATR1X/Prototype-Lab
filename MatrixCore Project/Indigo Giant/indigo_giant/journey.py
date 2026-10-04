"""Pass 43 — the ongoing journey: making things, planting, the endless trail, the journal.

THE LOOP
    Morning:   set out with Indigo. It senses finds and turns toward far landmarks.
    Midday:    the sun is harsh. Move shade to shade (Indigo's shadow, shells, landmarks),
               eat and drink, dig up food and materials.
    Anywhere:  the Red Giant hunts. Hide in shells, whistle, fight, scare it off.
    Dusk:      find (or carry, or patch) a shell and sleep (Z). That shell becomes camp.
    Between:   make gear from what you found (B), plant blood-branch seeds around camp.
    Always:    study landmarks. Each one points Indigo to the next; when every marker
               is found, a wider ring of new ones opens. The journal (J) keeps it all.

MAKING (B)  - pooled from your bag and Indigo's when it is beside you
    sun cloak        4 fibre, 1 resin              the sun heats you 25% slower
    sand wraps       3 fibre, 2 scraps             jogging and sprinting tire you 30% less
    water skin       3 shards, 1 resin             3 sips of dew, refilled each night you sleep;
                                                   G drinks when you are hot and have no gourd
    shoulder canopy  5 fibre, 2 shards, 2 resin    riding Indigo is shaded (cools instead of heats)
SEEDS
    Smashing a blood branch sometimes leaves a seed (35%).  Hold E on open level ground to
    plant it; it grows into a full branch in 2 minutes.  Grow an oasis around your camp.
"""
from __future__ import annotations

import math
import random
from collections import Counter

from panda3d.core import Point3

from . import desert
from . import desert_world
from . import places as places_mod
from .survival import K, _flat_dist

RECIPES = (
    ('cloak', 'sun cloak', {'fibre': 4, 'resin': 1}, 'the sun heats you 25% slower'),
    ('wraps', 'sand wraps', {'fibre': 3, 'scraps': 2}, 'jogging and sprinting tire you 30% less'),
    ('waterskin', 'water skin', {'shard': 3, 'resin': 1}, '3 sips of dew, refilled each night you sleep'),
    ('canopy', 'shoulder canopy', {'fibre': 5, 'shard': 2, 'resin': 2}, 'riding on Nyx is shaded'),
)
SEED_CHANCE = 0.35
PLANT_MAX_SLOPE = 12.0
PLANT_SPACING = 3.5
desert.HOLD_TIMES.setdefault('plant', 1.2)


class JourneyMixin:
    def _init_journey(self, seed: int):
        self.upgrades: set[str] = set()
        self.stats = Counter()
        self.lore_log: list[str] = []
        self.paused = False
        self._journey_rng = random.Random(seed * 7 + 3)

    # ------------------------------------------------------------ making
    def has_upgrade(self, name: str) -> bool:
        return name in self.upgrades

    def recipe(self, rid: str):
        return next((r for r in RECIPES if r[0] == rid), None)

    def can_craft(self, rid: str):
        r = self.recipe(rid)
        if r is None or rid in self.upgrades:
            return False
        return all(self.pooled_count(item) >= n for item, n in r[2].items())

    def craft(self, rid: str) -> bool:
        r = self.recipe(rid)
        if r is None or rid in self.upgrades or not self.human_alive:
            return False
        if not self.spend_pooled(r[2]):
            missing = ', '.join(f'{n - self.pooled_count(i)} {i}' for i, n in r[2].items() if self.pooled_count(i) < n)
            self.say(f'{r[1]}: still need {missing}', 2.5)
            return False
        self.upgrades.add(rid)
        self.stats['crafted'] += 1
        if rid == 'waterskin':
            self.water_sips = 3
        self.sfx('patch', self.human.getPos(self.render))
        self.say(f'you made the {r[1]} — {r[3]}', 3.0)
        return True

    # ------------------------------------------------------------ seeds
    def on_branch_smashed(self, branch, by: str):
        self.stats['branches_smashed'] += 1
        if self._journey_rng.random() >= SEED_CHANCE:
            return False
        near = self.human_alive and _flat_dist(self.human.getPos(self.render), branch.pos) <= 15.0
        if near and self.bag_space('human') > 0:
            self.bag('human')['seed'] += 1
        elif self.bag_space('giant') > 0:
            self.bag('giant')['seed'] += 1
        else:
            return False
        self.say('a blood-branch seed', 2.0)
        return True

    def _plant_spot(self):
        h = self.human.getPos(self.render)
        f = K['heading_forward'](self.human.getH())
        p = Point3(h.x + f.x * 0.9, h.y + f.y * 0.9, 0.0)
        if desert_world.slope_deg(self.field, p.x, p.y) > PLANT_MAX_SLOPE:
            return None
        for b in self.flora.active.values():
            if math.hypot(b.pos.x - p.x, b.pos.y - p.y) < PLANT_SPACING:
                return None
        p.z = self.field.height(p.x, p.y)
        return p

    def _e_target(self):
        kind, target = super()._e_target()
        if kind is None and self.controlled_name == 'human' and self.human_alive and not self.carried \
                and self.hidden_shell is None and self.bag('human')['seed'] > 0 and self._plant_spot() is not None:
            return 'plant', None
        return kind, target

    def _complete_e(self, kind, target):
        if kind == 'plant':
            spot = self._plant_spot()
            if spot is not None and self.bag('human')['seed'] > 0:
                self.bag('human')['seed'] -= 1
                self.flora.plant(spot, self.human.getH())
                self.stats['planted'] += 1
                self.sfx('dig', spot)
                self.say('you press the seed into the sand', 2.0)
            return
        if kind == 'dig':
            self.stats['finds_dug'] += 1
        if kind == 'smash':
            self.on_branch_smashed(target, 'human')
        super()._complete_e(kind, target)
        if kind == 'study' and target.visited:
            self.stats['landmarks'] += 1
            self.lore_log.append(target.lore)
            if self.landmarks.all_visited():
                self.open_next_chapter()

    # ------------------------------------------------------------ the endless trail
    def open_next_chapter(self):
        lf = self.landmarks
        sites = lf.chapter_sites(lf.chapter + 1)
        zones = desert_world.landmark_flat_zones(sites)
        for z in zones:
            self.field.add_flat_zone(*z)
        self.invalidate_terrain_near([(z[0], z[1], z[3]) for z in zones])
        new = lf.add_chapter(self.human.getPos(self.render))
        first = min(new, key=lambda lm: _flat_dist(lm.pos, self.human.getPos(self.render)))
        self.notice = {'pos': Point3(first.pos), 't': desert.NOTICE_TIME}
        self.say(f'the trail goes on.  Nyx gazes {self.bearing_words(first.pos)}, far away.', 5.0)
        return new

    # ------------------------------------------------------------ journal text
    def journal_lines(self):
        visited = self.landmarks.visited_count()
        lines = [
            f'day {self.day}  ·  {self.time_words()}',
            f'markers found  {visited} / {len(self.landmarks.items)}   (trail ring {self.landmarks.chapter})',
            f'finds dug  {self.stats["finds_dug"]}     seeds planted  {self.stats["planted"]}     nights slept  {self.nights_slept}',
            f'places found  {self.places.found_count() if getattr(self, "places", None) else 0}'
            + (f'     kinds known  {len(self.found_kinds & set(places_mod.catalogue_kinds()))} / '
               f'{len(places_mod.catalogue_kinds())}' if hasattr(self, 'found_kinds') else '')
            + ('     the Sky Well\'s water is in you' if 'wellwater' in self.upgrades else ''),
            self.bloom_words() if hasattr(self, 'bloom_words') else '',
            'made:  ' + (', '.join(r[1] for r in RECIPES if r[0] in self.upgrades) or 'nothing yet'),
        ]
        return lines, self.lore_log[-8:]

    def respawn_point(self):
        """Where you wake after collapsing: your camp shell, else the start."""
        s = getattr(self, 'camp_shell', None)
        if s is not None and not s.held:
            p = s.entrance_point()
            return Point3(p.x, p.y, self.field.height(p.x, p.y)), s.heading
        return None, None

    def flora_seedlings(self):
        return [b for b in self.flora.planted if b.grow < 1.0]

