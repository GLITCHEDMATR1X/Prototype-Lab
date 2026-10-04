"""Pass 46 — the wide world: hidden places.

Beyond the landmark trail, the desert is scattered with unique places: a sunken giant's
skull, a wind-carved arch, a dew oasis, a field of lightning glass, rock hoodoos, a ring of
standing stones, the husk of a strange vessel, a small abandoned camp, a stone giant sitting
in meditation, a stone hand reaching out of the sand.

They are NOT on the trail and nothing points at them. Every region of the world (PLACE_CELL
metres square) either holds one or not, decided by the world seed, so a place is always
there whether or not you ever find it. Walk far enough in any direction and you will keep
finding new ones; the world has no edge.

Finding one (walking up to it) names it and writes it in the journal. Some hold something:
  search  (hold E)  the skull, the wreck, the camp and the glass field each hide a cache, once
  drink   (hold E)  the oasis: cools you completely, heals a little, refills the water skin
  wade              standing in the oasis water cools you quickly
  rest    (hold E)  the stone ring: stamina restored and the heat eased, any time
  shade             the skull, arch, hoodoos, statue, wreck and hand all cast real shade
Indigo notices places before you do: walking together, it may turn its head toward one.

Pass 51 - the deep desert. Discovery is layered so the whole desert takes a long time to know:
  common    near and far        skull, arch, oasis, glass, hoodoos, ring, camp, stone tree
  uncommon  from ~1.6 km out    husk, nest, tower, salt flat, totems, stone hand, lantern stones
  rare      from ~3.4 km out    sitting giant, sea-serpent spine, split geode, sunken village
  legends   one each per world, very far, found by following rumours:
            the Sleeping Titan, the Sky Well, the Small City, the Red Cradle  (and the pale bloom)
  Night     the lantern stones are only seen at night; standing among them keeps the cold off.
  Rumours   certain places carry a drawing or a story that points toward a legend (the journal
            keeps them, with the direction from wherever you stand).
  Effort    some secrets need help: Indigo prises open the stone hand, splits the geode and
            lifts the Titan's fallen rib; the sitting giant's hollow only shows by moonlight;
            climb a tower (hold E) to spot the nearest place you have not found.
  Journal   the "places" page lists every kind of place, the ones you have not found as "?".
"""
from __future__ import annotations

import math
import random

from panda3d.core import Point3, Vec3

from . import controls
from . import desert
from . import desert_world
from . import places_geom
from .flora import _stable_seed
from .survival import K, _flat_dist

PLACE_CELL = 760.0              # Pass 47: one region per 760 m square (was 520) - places lie farther apart
PLACE_CHANCE = 0.70
PREPARE_RADIUS = 950.0          # regions this close are laid out (ground levelled) - beyond any built ground
SHOW_RADIUS = 1150.0            # places this close are instanced (the fog hides them long before)
START_CLEAR = 420.0             # nothing right at the start
TRAIL_CLEAR = 240.0             # never on top of a trail landmark
SENSE_RADIUS = 230.0            # Indigo may notice an unfound place this close
PLACE_GHOST = 0.05              # past the fog a tall place is a faint 5% shape, like the trail
PLACE_EDGE_INK = 0.55           # a lighter pencil line than the characters (flat parts never go black)
VARIANTS = 4                    # shapes per kind, built once at load (no hitch when one comes into view)

# kind: (weight, footprint radius, shade radius, height, what E does, cache)
KINDS = {
    'skull':      (10, 14.0, 12.0, 11.0, 'search', {'resin': 2, 'shard': 2}),
    'arch':       (11, 12.0, 6.0, 17.0, None, None),
    'oasis':      (9, 12.0, 0.0, 2.0, 'drink', None),
    'glassfield': (9, 10.0, 0.0, 4.0, 'search', {'shard': 4}),
    'hoodoos':    (10, 13.0, 7.0, 20.0, None, None),
    'ring':       (8, 13.0, 0.0, 6.0, 'rest', None),
    'wreck':      (6, 15.0, 8.0, 9.0, 'search', {'fibre': 3, 'resin': 2, 'gourd': 1}),
    'camp':       (9, 9.0, 0.0, 3.0, 'search', {'pod': 3, 'gourd': 1, 'fibre': 2}),
    'statue':     (4, 12.0, 10.0, 26.0, None, None),
    'hand':       (6, 9.0, 5.0, 15.0, None, None),
    # Pass 47
    'tree':       (8, 10.0, 5.0, 18.0, None, None),
    'nest':       (6, 11.0, 0.0, 4.0, 'search', {'shard': 2, 'fibre': 3}),
    'tower':      (6, 9.0, 6.0, 20.0, None, None),
    'saltflat':   (6, 16.0, 0.0, 3.0, 'search', {'shard': 2}),
    'totems':     (6, 13.0, 0.0, 5.0, None, None),
    'bones':      (5, 22.0, 0.0, 5.0, None, None),
    'bloom':      (0, 5.0, 0.0, 2.0, 'uproot', None),         # never random: see bloom rules below
    # Pass 51 - the deep desert
    'lanterns':   (7, 9.0, 0.0, 2.5, None, None),             # night only; warmth
    'geode':      (6, 10.0, 5.0, 7.0, 'search', {'shard': 6, 'resin': 1}),
    'village':    (5, 24.0, 4.0, 4.0, 'search', {'fibre': 4, 'pod': 3, 'gourd': 2, 'resin': 1}),
    'titan':      (0, 30.0, 14.0, 20.0, 'search', {'shard': 4, 'resin': 4, 'fibre': 4}),
    'well':       (0, 14.0, 0.0, 9.0, 'drinkdeep', None),
    'city':       (0, 54.0, 6.0, 12.0, 'search', {'fibre': 6, 'resin': 4, 'shard': 4, 'gourd': 2, 'pod': 4}),
    'cradle':     (0, 16.0, 8.0, 10.0, 'search', {'shard': 3, 'resin': 2}),
}
# Pass 51: secrets that ask for more than walking up
KINDS['hand'] = (6, 9.0, 5.0, 15.0, 'search', {'resin': 3, 'shard': 2})
KINDS['statue'] = (4, 12.0, 10.0, 26.0, 'search', {'resin': 2, 'shard': 3, 'pod': 2})
KINDS['tower'] = (6, 9.0, 6.0, 20.0, 'climb', None)
NEEDS = {'hand': 'indigo', 'geode': 'indigo', 'titan': 'indigo', 'statue': 'night'}
NEED_WORDS = {
    'hand': 'The stone fingers are shut tight over something. Nyx could prise them open.',
    'geode': 'The geode is split, but its hollow is sealed with crystal. Nyx could break it open.',
    'titan': 'A hollow under the ribs is blocked by a fallen rib. Only Nyx could lift it.',
    'statue': 'In daylight the plinth is plain stone. A moon is carved on it.',
}
DONE_WORDS = {
    'hand': 'Nyx takes the stone fingers in its hands and slowly opens them.',
    'geode': 'Nyx strikes the crystal once. It rings, and breaks.',
    'titan': 'Nyx lifts the fallen rib, very gently, as if it might still hurt.',
    'statue': 'By moonlight a hollow in the plinth shows itself.',
}
INDIGO_HELP_RANGE = 28.0
HOLD = {'search': 1.6, 'drink': 1.0, 'rest': 2.2, 'uproot': 2.6, 'climb': 2.4, 'need': 0.3, 'drinkdeep': 1.4}

# ---------------------------------------------------------------- tiers (Pass 51)
# tier: (kinds, first distance from the start). A tier fades in over TIER_RAMP metres past it.
TIERS = {
    'common':   (('skull', 'arch', 'oasis', 'glassfield', 'hoodoos', 'ring', 'camp', 'tree'), 0.0),
    'uncommon': (('wreck', 'nest', 'tower', 'saltflat', 'totems', 'hand', 'lanterns'), 1600.0),
    'rare':     (('statue', 'bones', 'geode', 'village'), 3400.0),
    'legend':   (('titan', 'well', 'city', 'cradle', 'bloom'), 0.0),
}
TIER_OF = {k: t for t, (ks, _d) in TIERS.items() for k in ks}
TIER_RAMP = 1400.0
FIRST_DECK_RADIUS = 2600.0       # the places nearest the start deal out every common kind once before repeating
COMMON_FAR_SHARE = 0.55          # far out, the common kinds keep at least this share of their weight
COMMON_FADE = 14000.0
# legends: one each per world, at these distances, each in its own direction
LEGENDS = (('titan', 8000.0), ('well', 11000.0), ('city', 14000.0), ('cradle', 18000.0))
LEGEND_NAMES = {'titan': 'the Sleeping Titan', 'well': 'the Sky Well', 'city': 'the Small City',
                'cradle': 'the Red Cradle'}
LEGEND_SENSE_RADIUS = 380.0
LEGEND_SENSE_RUMOURED = 900.0    # once you have heard its story, Indigo feels a legend from much farther
TOWER_SIGHT = 1900.0
LANTERN_WARMTH = 16.0            # chill removed per second among the lantern stones
LANTERN_REACH = 11.0
NIGHT_ONLY = ('lanterns',)
KIND_WORDS = {
    'skull': 'giant skull', 'arch': 'arch', 'oasis': 'oasis', 'glassfield': 'glass field', 'hoodoos': 'hoodoos',
    'ring': 'stone ring', 'camp': 'camp', 'tree': 'stone tree', 'wreck': 'husk', 'nest': 'great nest',
    'tower': 'tower', 'saltflat': 'salt flat', 'totems': 'painted poles', 'hand': 'stone hand',
    'lanterns': 'lantern stones', 'statue': 'sitting giant', 'bones': 'serpent spine', 'geode': 'split geode',
    'village': 'sunken village', 'titan': 'the Sleeping Titan', 'well': 'the Sky Well', 'city': 'the Small City',
    'cradle': 'the Red Cradle', 'bloom': 'the pale bloom',
}

# ---------------------------------------------------------------- the pale bloom (Pass 47)
# The only thing that can end the Red Giant. One grows FIRST_BLOOM_DIST from the start in a
# direction the seed picks; beyond RARE_BLOOM_MIN a few more grow, very rarely.
FIRST_BLOOM_DIST = 6500.0        # Pass 51: was 3200
RARE_BLOOM_MIN = 9000.0         # Pass 51: was 2600 - a lucky early bloom could end the story in the first hour
RARE_BLOOM_CHANCE = 0.008
BLOOM_SENSE_RADIUS = 420.0
BLOOM_SCRAPS = 3
for _k, _t in HOLD.items():
    desert.HOLD_TIMES.setdefault(_k, _t)
OASIS_WATER = 8.3
WADE_COOLING = 14.0             # heat per second while standing in the oasis
REST_STAMINA = 100.0
REST_COOLING = 35.0

_NAMES = {
    'skull': ('the Skull of the {a}', ('First Walker', 'Long Sleep', 'Salt Eye', 'Old Hunger', 'Quiet Brother')),
    'arch': ('the {a} Arch', ('Two-Note', 'Leaning', 'Red Window', 'Wind\'s', 'Broken Bow')),
    'oasis': ('the {a} Pool', ('Dew', 'Still', 'Moon', 'Hidden', 'Green')),
    'glassfield': ('the {a} Glass', ('Lightning', 'Singing', 'Thunder', 'Frozen Rain', 'Needle')),
    'hoodoos': ('the {a}', ('Stacked Elders', 'Standing Sisters', 'Tall Watchers', 'Stone Chimneys', 'Waiting Ones')),
    'ring': ('the {a} Ring', ('Counting', 'Sleepers\'', 'Nine-Stone', 'Dawn', 'Silent')),
    'wreck': ('the {a} Husk', ('Fallen', 'Split', 'Star', 'Seed', 'Hollow')),
    'camp': ('a {a} camp', ('small, cold', 'forgotten', 'tiny, tidy', 'windswept', 'hurried')),
    'statue': ('the {a}', ('Sitting Giant', 'Dreaming One', 'Blue Elder', 'Patient Stone', 'Meditator')),
    'hand': ('the {a} Hand', ('Reaching', 'Open', 'Buried', 'Asking', 'Last')),
    'tree': ('the {a} Tree', ('Stone', 'Last', 'Twisted', 'Sleeping', 'Old Rain')),
    'nest': ('the {a} Nest', ('Empty', 'Great', 'Bone', 'Abandoned', 'Sky-Bird\'s')),
    'tower': ('the {a} Tower', ('Leaning', 'Hollow', 'Sand-Worn', 'Lookout', 'Unfinished')),
    'saltflat': ('the {a} Salt', ('Mirror', 'White', 'Cracked', 'Blue', 'Singing')),
    'totems': ('the {a} Poles', ('Painted', 'Watching', 'Pointing', 'Little People\'s', 'Seven')),
    'bones': ('the {a} Spine', ('Serpent\'s', 'Sea-Snake', 'Long', 'Drowned', 'Old Sea')),
    'bloom': ('the {a}', ('Pale Bloom', 'Pale Bloom', 'White Bell', 'Pale Bloom', 'Bone Flower')),
    'lanterns': ('the {a} Stones', ('Lantern', 'Ember', 'Night', 'Warm', 'Firefly')),
    'geode': ('the {a} Geode', ('Split', 'Violet', 'Singing', 'Broken', 'Hollow')),
    'village': ('the {a} Village', ('Sunken', 'Drowned', 'Quiet', 'Buried', 'Last')),
    'titan': ('{a}', ('the Sleeping Titan',) * 5),
    'well': ('{a}', ('the Sky Well',) * 5),
    'city': ('{a}', ('the Small City',) * 5),
    'cradle': ('{a}', ('the Red Cradle',) * 5),
}
_LORE = {
    'skull': ("Its eyes look the way the wind goes. Inside, it is dim and cool.",
              "Something the size of Nyx died here, long before the sand came.",
              "Small shelves have been cut into the bone, and left empty."),
    'arch': ("The wind makes two notes through it, one low, one high.",
             "Under the arch the sand is swept clean, as if someone keeps it.",
             "Through it, the horizon looks closer."),
    'oasis': ("Water, still and cold, in the middle of nothing.",
              "The reeds lean toward the water like they are listening.",
              "The pool is deeper than it looks. Stars sleep in it at noon."),
    'glassfield': ("Lightning struck here, again and again, and the sand remembered.",
                   "The glass rings faintly when the wind touches it.",
                   "Branches of glass, like roots grown upward."),
    'hoodoos': ("Stone stacked on stone, and nobody stacked it.",
                "The towers lean toward each other, as if sharing a secret.",
                "From the top one, you could see forever. Nobody could climb it."),
    'ring': ("Nine stones, or there were. Two lie down, tired.",
             "Inside the ring, your heartbeat slows.",
             "The shadows of the stones point at each other at noon."),
    'wreck': ("A husk like a seed pod, split open. Whatever grew inside it left.",
              "Glass ribs, and a smell like rain.",
              "It fell from somewhere. It did not fall gently."),
    'camp': ("Three little huts around a cold fire. Small people slept here.",
             "Dried fibre still hangs on the rack. They meant to come back.",
             "Footprints lead away from the fire, all in the same direction."),
    'statue': ("A giant, carved sitting, eyes closed. It is older than the dunes.",
               "Nyx is very quiet here. It lowers its head.",
               "Blue stone, not from this desert. Someone brought it very far."),
    'hand': ("A stone hand reaching out of the sand, fingers half closed.",
             "Is it reaching up, or holding on?",
             "The palm is smooth, as if many hands have touched it."),
    'tree': ("A tree, turned to stone. Once there was rain here.",
             "The rings of the trunk are glass now.",
             "Its roots still hold the dune together."),
    'nest': ("A nest of reed and bone, wider than Nyx is tall. The eggs hatched long ago.",
             "Whatever flew from here was very big.",
             "The shells are thin as paper and white as the moon."),
    'tower': ("A tower of cut stone, leaning, unfinished. Small steps spiral up inside.",
              "From the doorway you can see the next dune, and nothing else.",
              "Someone built it to watch for something. Crimson, perhaps."),
    'saltflat': ("A floor of salt, cracked into plates. The sky lies in it.",
                 "Walking here sounds like breaking ice.",
                 "The salt is bitter. An old sea dried here."),
    'totems': ("Seven painted poles, all leaning the same way.",
               "Little carved faces, all looking the same way.",
               "The poles point somewhere. The small people wanted you to follow."),
    'bones': ("The spine of something that swam here, when this was a sea.",
              "It dives in and out of the sand, as if still swimming.",
              "Every bone is as big as you are."),
    'lanterns': ("Stones that hold a little of the day and give it back at night. It is warm among them.",
                 "Pale-gold stones, faintly shining. Small people slept here, in the cold.",
                 "The light is soft, like a hand held near a fire."),
    'geode': ("A boulder split in two. Inside, violet crystal, like a mouth full of teeth.",
              "The crystal hums when the wind crosses it.",
              "Something split it from inside, long ago."),
    'village': ("A dozen huts of dried mud, drowned to the doorways in sand.",
                "Pots, still stacked by the doors. The well is dry, but only just.",
                "The small people lived here once, many of them."),
    'titan': ("A giant far larger than Nyx lies curled in the sand, its bones white as salt. "
              "Nyx kneels beside it for a long time. It was one of Nyx's kind.",) * 3,
    'well': ("A round mouth of cut stone, and far below, dark water. You can see stars in it, "
             "though it is noon. The air that rises from it is cold and sweet.",) * 3,
    'city': ("Walls, lanes, a hundred little huts: the city of the small people, half drowned in "
             "sand. Everything here is exactly the size of you.",) * 3,
    'cradle': ("A great egg of red stone, broken open from the inside. Crimson began here. "
               "Scratched round it, over and over: Crimson, small, and alone.",) * 3,
    'bloom': ("A pale flower, alone in a ring of white stones. Crimson will not come near it.",
              "A white bell of petals, bitter-smelling. Nothing grows around it.",
              "The only pale thing in the whole desert. Your hands feel cold near it."),
}
# Pass 47: the recipe, told by the desert (camps, totems and statues point the way)
BLOOM_HINTS = {
    'camp': "Scratched into a hut: Crimson bent over a blood branch, eating. Beside it a pale flower, "
            "and Crimson lying down. The flower is drawn far away, {bearing}.",
    'totems': "At the foot of the poles, pale petals, long dried. The poles lean {bearing}.",
    'statue': "Carved in the plinth: a pale flower, a blood branch, and a red giant asleep forever. "
              "The carving faces {bearing}.",
}


# Pass 51: rumours - what a place tells you about a legend, and which places tell it
RUMOUR_FROM = {
    'titan': ('hand', 'statue', 'bones'),
    'well': ('tower', 'lanterns', 'geode'),
    'city': ('village', 'bones'),
    'cradle': ('titan',),                  # only the Titan knows where the red one began
}
RUMOUR_COMMON_MIN = 2000.0       # a common place only knows the far stories when it is far out itself
RUMOUR_VAGUE = 0.45              # a story is only roughly right: off by up to 45% of the distance it points
                                 # (each place's story is off in its own way - several of them narrow it down)
RUMOUR_TEXT = {
    'titan': "Scratched here: a giant far larger than Nyx, lying curled, asleep or dead. It lies {bearing}.",
    'well': "A worn carving: a round hole in the ground with stars inside it, and small people walking "
            "to it from every side, {bearing}.",
    'city': "Small footprints cut into the stone, hundreds of them, all walking {bearing}, toward a drawing "
            "of many huts inside a wall.",
    'cradle': "A red shape curled inside a broken egg, drawn over and over. The drawings face {bearing}.",
}
RUMOUR_VAGUE_TITAN = 0.12        # the Titan's drag-mark points true
RUMOUR_FROM_TITAN = "Beside the great bones, a long red drag-mark in the old stone leads away {bearing}."


def night_only(kind: str) -> bool:
    return kind in NIGHT_ONLY


def tier_of(kind: str) -> str:
    return TIER_OF.get(kind, 'common')


def catalogue_kinds():
    """Every kind of place a journey can find, in journal order."""
    return [k for t in ('common', 'uncommon', 'rare', 'legend') for k in TIERS[t][0]]


def kind_weight(kind: str, dist: float) -> float:
    """How likely a region this far from the start holds this kind (relative weight)."""
    base = KINDS[kind][0]
    tier = TIER_OF.get(kind)
    if tier is None or tier == 'legend' or base <= 0:
        return 0.0
    first = TIERS[tier][1]
    if dist < first:
        return 0.0
    if tier == 'common':
        return base * max(COMMON_FAR_SHARE, 1.0 - dist / COMMON_FADE)
    return base * min(1.0, 0.25 + (dist - first) / TIER_RAMP)


def rumour_guess(seed: int, source_key, source_xy, target_xy, vague: float = None):
    """Where a story told at source says the target is: roughly right, wrong in its own way."""
    d = math.hypot(target_xy[0] - source_xy[0], target_xy[1] - source_xy[1])
    rng = random.Random(_stable_seed(int(seed), repr(source_key), 'rumour'))
    r = (RUMOUR_VAGUE if vague is None else vague) * d * math.sqrt(rng.random())
    a = rng.uniform(0, 2 * math.pi)
    return target_xy[0] + math.cos(a) * r, target_xy[1] + math.sin(a) * r


def rumour_estimate(guesses):
    """All the stories heard about one place, taken together."""
    n = len(guesses)
    return sum(g[0] for g in guesses) / n, sum(g[1] for g in guesses) / n


def distance_words(d: float) -> str:
    if d < 450.0:
        return 'close by'
    if d < 1000.0:
        return 'a walk away'
    if d < 2500.0:
        return 'far off'
    return 'very far away'


class Place:
    __slots__ = ('pid', 'kind', 'pos', 'heading', 'radius', 'name', 'lore', 'found', 'searched', 'sensed', 'node')

    def __init__(self, pid, kind, pos, heading, name, lore):
        self.pid, self.kind, self.pos, self.heading, self.name, self.lore = pid, kind, pos, heading, name, lore
        self.radius = KINDS[kind][1]
        self.found = False
        self.searched = False
        self.sensed = False
        self.node = None


def _pick_kind(rng: random.Random, dist: float) -> str:
    return desert_world._weighted(rng, [(k, kind_weight(k, dist)) for k in KINDS if kind_weight(k, dist) > 0.0])


def default_start() -> Point3:
    return Point3(0.0, 0.0, 0.0)


class PlaceLayout:
    """Where every place is: pure rules from the world seed (no rendering). Used by the game
    (PlaceField) and by tools_discovery_probe.py, so both see the same world."""

    def __init__(self, seed: int, start: Point3):
        self.seed = int(seed)
        self.start = Point3(start)
        self._trail_cache: dict = {}
        self._regions: dict = {}

    def _trail_sites(self, dist_from_start: float):
        """Trail landmark positions that could be near this distance (first ring + chapters)."""
        sites = list(self._trail_cache.setdefault(1, [(x, y) for _i, x, y, _k, _h in
                                                       desert_world.landmark_sites(self.seed, self.start.x,
                                                                                   self.start.y)]))
        c = 2
        while True:
            base = desert_world.CHAPTER_FIRST_RING + (c - 2) * desert_world.CHAPTER_RING_STEP
            if base - 600.0 > dist_from_start:
                break
            if base + 900.0 >= dist_from_start:
                if c not in self._trail_cache:
                    first = desert_world.LANDMARK_COUNT + (c - 2) * desert_world.CHAPTER_SIZE
                    self._trail_cache[c] = [(x, y) for _i, x, y, _k, _h in desert_world.chapter_sites(
                        self.seed, self.start.x, self.start.y, c, first)]
                sites.extend(self._trail_cache[c])
            c += 1
        return sites

    def _first_bloom(self):
        """Where the first pale bloom grows (always exists; clear of the trail)."""
        fb = getattr(self, '_first_bloom_xy', None)
        if fb is None:
            rng = random.Random(_stable_seed(self.seed, 'first bloom'))
            a = rng.uniform(0, 2 * math.pi)
            for _ in range(24):
                x = self.start.x + math.cos(a) * FIRST_BLOOM_DIST
                y = self.start.y + math.sin(a) * FIRST_BLOOM_DIST
                if all(math.hypot(x - tx, y - ty) >= TRAIL_CLEAR for tx, ty in self._trail_sites(FIRST_BLOOM_DIST)):
                    break
                a += 0.27
            fb = self._first_bloom_xy = (x, y, (math.floor(x / PLACE_CELL), math.floor(y / PLACE_CELL)))
        return fb

    def legends(self):
        """{kind: (x, y, cell)} - where each legend lies (one each, far out, each its own way)."""
        lg = getattr(self, '_legends', None)
        if lg is None:
            lg = {}
            rng = random.Random(_stable_seed(self.seed, 'legends'))
            a0 = rng.uniform(0, 2 * math.pi)
            fbx, fby, _fc = self._first_bloom()
            taken = [(fbx, fby)]
            for i, (kind, dist) in enumerate(LEGENDS):
                a = a0 + i * 2.4 + rng.uniform(-0.3, 0.3)           # ~137 deg apart: never bunched
                for _ in range(40):
                    x = self.start.x + math.cos(a) * dist
                    y = self.start.y + math.sin(a) * dist
                    clear_trail = all(math.hypot(x - tx, y - ty) >= TRAIL_CLEAR + 60.0
                                      for tx, ty in self._trail_sites(dist))
                    clear_other = all(math.hypot(x - ox, y - oy) >= 2.5 * PLACE_CELL for ox, oy in taken)
                    if clear_trail and clear_other:
                        break
                    a += 0.09
                taken.append((x, y))
                lg[kind] = (x, y, (math.floor(x / PLACE_CELL), math.floor(y / PLACE_CELL)))
            self._legends = lg
        return lg

    def _first_deck(self) -> dict:
        """{cell: kind} for the regions nearest the start: every common kind once, then again, in a
        shuffled order - so the first few hours always show the whole common set."""
        deck = getattr(self, '_deck', None)
        if deck is None:
            deck = self._deck = {}
            rng = random.Random(_stable_seed(self.seed, 'first deck'))
            commons = list(TIERS['common'][0])
            order = []
            r = int(math.ceil(FIRST_DECK_RADIUS / PLACE_CELL)) + 1
            sx, sy = math.floor(self.start.x / PLACE_CELL), math.floor(self.start.y / PLACE_CELL)
            for cx in range(sx - r, sx + r + 1):
                for cy in range(sy - r, sy + r + 1):
                    d = math.hypot((cx + 0.5) * PLACE_CELL - self.start.x, (cy + 0.5) * PLACE_CELL - self.start.y)
                    if d <= FIRST_DECK_RADIUS:
                        order.append((d, cx, cy))
            order.sort()
            hand = []
            for _d, cx, cy in order:
                if self._spot(cx, cy) is None:
                    continue                                  # only regions that hold a place draw a card
                if not hand:
                    hand = commons[:]
                    rng.shuffle(hand)
                deck[(cx, cy)] = hand.pop()
        return deck

    def region(self, cx: int, cy: int):
        """The place in region (cx, cy), or None. A fresh Place each call (the game keeps its own)."""
        if (cx, cy) not in self._regions:
            self._regions[(cx, cy)] = self._region_rule(cx, cy)
        spec = self._regions[(cx, cy)]
        return None if spec is None else Place(*spec)

    def _region_rule(self, cx: int, cy: int):
        for kind, (lx, ly, lcell) in self.legends().items():
            if (cx, cy) == lcell:
                rng = random.Random(_stable_seed(self.seed, cx, cy, 'legend'))
                return ((cx, cy), kind, Point3(lx, ly, 0.0), rng.uniform(0, 360), LEGEND_NAMES[kind], _LORE[kind][0])
        fx, fy, fcell = self._first_bloom()
        if (cx, cy) == fcell:
            rng = random.Random(_stable_seed(self.seed, cx, cy, 'bloom'))
            return ((cx, cy), 'bloom', Point3(fx, fy, 0.0), rng.uniform(0, 360), 'the Pale Bloom',
                    rng.choice(_LORE['bloom']))
        spot = self._spot(cx, cy)
        if spot is None:
            return None
        x, y = spot
        krng = random.Random(_stable_seed(self.seed, cx, cy, 'kind'))
        ccx, ccy = (cx + 0.5) * PLACE_CELL, (cy + 0.5) * PLACE_CELL
        kind = _pick_kind(krng, math.hypot(ccx - self.start.x, ccy - self.start.y))
        kind = self._first_deck().get((cx, cy), kind)
        if krng.random() < RARE_BLOOM_CHANCE and math.hypot(x - self.start.x, y - self.start.y) >= RARE_BLOOM_MIN:
            kind = 'bloom'
        heading = krng.uniform(0, 360)
        name_t, words = _NAMES[kind]
        name = name_t.format(a=krng.choice(words))
        lore = krng.choice(_LORE[kind])
        return ((cx, cy), kind, Point3(x, y, 0.0), heading, name, lore)

    def _spot(self, cx: int, cy: int):
        """(x, y) if region (cx, cy) holds an ordinary place (whatever its kind), else None."""
        rng = random.Random(_stable_seed(self.seed, cx, cy, 'place'))
        if rng.random() >= PLACE_CHANCE:
            return None
        x = (cx + rng.uniform(0.2, 0.8)) * PLACE_CELL
        y = (cy + rng.uniform(0.2, 0.8)) * PLACE_CELL
        d0 = math.hypot(x - self.start.x, y - self.start.y)
        if d0 < START_CLEAR:
            return None
        for tx, ty in self._trail_sites(d0):
            if math.hypot(x - tx, y - ty) < TRAIL_CLEAR:
                return None
        return x, y

    def places_within(self, x: float, y: float, radius: float):
        r = int(math.ceil(radius / PLACE_CELL))
        ox, oy = math.floor(x / PLACE_CELL), math.floor(y / PLACE_CELL)
        for cx in range(ox - r, ox + r + 1):
            for cy in range(oy - r, oy + r + 1):
                pl = self.region(cx, cy)
                if pl is not None and math.hypot(pl.pos.x - x, pl.pos.y - y) <= radius:
                    yield pl


class PlaceField:
    def __init__(self, render, field, seed: int, start: Point3, shadow_mask):
        self.render, self.field, self.seed = render, field, int(seed)
        self.start = Point3(start)
        self.layout = PlaceLayout(seed, start)
        self.root = render.attachNewNode('places')
        self.root.setShaderInput('fog_floor', PLACE_GHOST)
        self.root.setShaderInput('edge_ink', PLACE_EDGE_INK)
        self.shadow_mask = shadow_mask
        self.places: dict = {}
        self.regions: set = set()
        self.shown: dict = {}
        # every shape is built up front (~0.35 s); instancing one later is free
        self.protos = {(kind, v): places_geom.build_place(kind, _stable_seed(self.seed, kind, v, 'shape'))
                       for kind in list(KINDS) + ['bloom_gone'] if kind not in LEGEND_NAMES for v in range(VARIANTS)}
        for kind in LEGEND_NAMES:                  # one of each in the world: built once, shared by all variants
            proto = places_geom.build_place(kind, _stable_seed(self.seed, kind, 'shape'))
            for v in range(VARIANTS):
                self.protos[(kind, v)] = proto
        self.pending_found: set = set()          # from a save, applied when the region is laid out
        self.pending_searched: set = set()
        self.pending_sensed: set = set()         # Pass 54: Indigo does not announce the same place twice

    def _first_bloom(self):
        return self.layout._first_bloom()

    def _region(self, cx: int, cy: int):
        return self.layout.region(cx, cy)

    def update(self, focus: Point3):
        """Lay out every region within PREPARE_RADIUS (levels the ground, keeps it clear of
        other content). Returns (x, y, radius) circles of ground that changed."""
        changed = []
        r = int(math.ceil(PREPARE_RADIUS / PLACE_CELL))
        fx, fy = math.floor(focus.x / PLACE_CELL), math.floor(focus.y / PLACE_CELL)
        for cx in range(fx - r, fx + r + 1):
            for cy in range(fy - r, fy + r + 1):
                if (cx, cy) in self.regions:
                    continue
                # only regions whose nearest point is inside the radius
                nx = min(max(focus.x, cx * PLACE_CELL), (cx + 1) * PLACE_CELL)
                ny = min(max(focus.y, cy * PLACE_CELL), (cy + 1) * PLACE_CELL)
                if math.hypot(nx - focus.x, ny - focus.y) > PREPARE_RADIUS:
                    continue
                self.regions.add((cx, cy))
                p = self._region(cx, cy)
                if p is None:
                    continue
                inner, outer = p.radius + 6.0, p.radius + 34.0
                self.field.add_flat_zone(p.pos.x, p.pos.y, inner, outer)
                self.field.add_clear_zone(p.pos.x, p.pos.y, p.radius + 8.0)
                p.pos.z = self.field.height(p.pos.x, p.pos.y)
                key = repr(p.pid)
                p.found = key in self.pending_found
                p.searched = key in self.pending_searched
                p.sensed = p.found or key in self.pending_sensed
                self.places[p.pid] = p
                changed.append((p.pos.x, p.pos.y, outer))
        # instance what is near, drop what is far
        for p in self.places.values():
            d = _flat_dist(p.pos, focus)
            if d <= SHOW_RADIUS and p.node is None:
                variant = _stable_seed(self.seed, p.pid[0], p.pid[1], 'variant') % VARIANTS
                p.node = self.root.attachNewNode(f'place_{p.kind}_{p.pid[0]}_{p.pid[1]}')
                shape = 'bloom_gone' if p.kind == 'bloom' and p.searched else p.kind
                self.protos[(shape, variant)].instanceTo(p.node)
                p.node.setPos(p.pos.x, p.pos.y, p.pos.z - 0.15)
                p.node.setH(p.heading)
                if p.kind == 'oasis':
                    p.node.setShaderInput('edge_ink', 0.0)   # still water: no ink at a glancing view
                if night_only(p.kind):
                    p.node.setShaderInput('fog_floor', 0.45)  # a soft glow through the night haze
                    p.node.setShaderInput('edge_ink', 0.25)
                    self._apply_night(p)
                if KINDS[p.kind][2] <= 0.0:
                    p.node.hide(self.shadow_mask)            # flat places cast no shadow
                self.shown[p.pid] = p
            elif d > SHOW_RADIUS + 120.0 and p.node is not None:
                p.node.removeNode()
                p.node = None
                self.shown.pop(p.pid, None)
        return changed

    night = False

    def set_night(self, night: bool):
        """Night-only places appear at dusk and vanish at dawn (and glow while they are out)."""
        if night == self.night:
            return
        self.night = night
        for p in self.shown.values():
            if night_only(p.kind):
                self._apply_night(p)

    def _apply_night(self, p: Place):
        if p.node is None:
            return
        if self.night:
            p.node.show()
            p.node.setColorScale(2.3, 2.1, 1.5, 1.0)          # lifts the stones out of the blue night tint
        else:
            p.node.hide()

    def is_found(self, pid) -> bool:
        pl = self.places.get(pid)
        return pl.found if pl is not None else repr(pid) in self.pending_found

    def unfound_near(self, origin: Point3, radius: float, night: bool):
        """The nearest place within radius you have not found (from the layout: it need not be
        laid out yet). Night-only places count only at night."""
        best = None
        for pl in self.layout.places_within(origin.x, origin.y, radius):
            if self.is_found(pl.pid) or (night_only(pl.kind) and not night):
                continue
            d = math.hypot(pl.pos.x - origin.x, pl.pos.y - origin.y)
            if best is None or d < best[0]:
                best = (d, pl)
        return None if best is None else best[1]

    def reshow(self, p: Place):
        """Rebuild one place's node (after the bloom is uprooted)."""
        if p.node is not None:
            p.node.removeNode()
            p.node = None
            self.shown.pop(p.pid, None)

    def bloom_near(self, origin: Point3, radius: float = 7000.0):
        """The nearest pale bloom still growing, from the layout rules (it need not be laid out
        yet).  Returns (x, y) or None."""
        fx, fy, fcell = self._first_bloom()
        best = None
        cands = []
        if repr(fcell) not in self.pending_searched and not (fcell in self.places and self.places[fcell].searched):
            cands.append((fx, fy))
        r = int(math.ceil(radius / PLACE_CELL))
        ox, oy = math.floor(origin.x / PLACE_CELL), math.floor(origin.y / PLACE_CELL)
        for cx in range(ox - r, ox + r + 1):
            for cy in range(oy - r, oy + r + 1):
                if (cx, cy) == fcell:
                    continue
                pl = self.places.get((cx, cy)) or self._region(cx, cy)
                if pl is None or pl.kind != 'bloom':
                    continue
                if pl.searched or repr(pl.pid) in self.pending_searched:
                    continue
                cands.append((pl.pos.x, pl.pos.y))
        for x, y in cands:
            d = math.hypot(x - origin.x, y - origin.y)
            if best is None or d < best[0]:
                best = (d, x, y)
        return None if best is None else (best[1], best[2])

    # ------------------------------------------------------------ queries
    def nearest(self, p: Point3, pad: float = 0.0):
        best, best_d = None, None
        for pl in self.shown.values():
            d = _flat_dist(pl.pos, p) - pl.radius - pad
            if d <= 0.0 and (best_d is None or d < best_d):
                best, best_d = pl, d
        return best

    def action_at(self, p: Point3, helpers=None):
        """(kind, place) the human can do here with E, or (None, None).
        helpers: {'indigo': bool, 'night': bool} - for secrets that need them."""
        pl = self.nearest(p, 3.0)
        if pl is None:
            return None, None
        if night_only(pl.kind) and not self.night:
            return None, None
        what = KINDS[pl.kind][4]
        if what in ('search', 'uproot', 'climb') and pl.searched:
            return None, None
        need = NEEDS.get(pl.kind)
        if what == 'search' and need is not None and not (helpers or {}).get(need, False):
            return 'need', pl
        if what == 'drink' and _flat_dist(pl.pos, p) > OASIS_WATER + 3.0:
            return None, None
        if what == 'rest' and _flat_dist(pl.pos, p) > 9.0:
            return None, None
        return what, pl

    def among_lanterns(self, p: Point3) -> bool:
        if not self.night:
            return False
        for pl in self.shown.values():
            if pl.kind in NIGHT_ONLY and _flat_dist(pl.pos, p) <= LANTERN_REACH:
                return True
        return False

    def in_water(self, p: Point3) -> bool:
        for pl in self.shown.values():
            if pl.kind == 'oasis' and _flat_dist(pl.pos, p) <= OASIS_WATER:
                return True
        return False

    def shade_circles(self, offset: Vec3):
        out = []
        for pl in self.shown.values():
            if night_only(pl.kind) and not self.night:
                continue
            r, h = KINDS[pl.kind][2], KINDS[pl.kind][3]
            if r > 0.0:
                out.append((pl.pos.x + offset.x * h * 0.45, pl.pos.y + offset.y * h * 0.45, r))
        return out

    def found_count(self) -> int:
        return sum(1 for p in self.places.values() if p.found) + len(
            {k for k in self.pending_found} - {repr(p.pid) for p in self.places.values()})

    def found_names(self):
        return [p.name for p in self.places.values() if p.found]


class PlacesMixin:
    """Hooks the places into the desert: discovery, E actions, shade, water, the journal, saves."""

    @property
    def found_kinds(self) -> set:
        v = self.__dict__.get('_found_kinds')
        if v is None:
            v = self.__dict__['_found_kinds'] = set()
        return v

    @found_kinds.setter
    def found_kinds(self, value):
        self.__dict__['_found_kinds'] = set(value)

    @property
    def rumours(self) -> dict:
        v = self.__dict__.get('_rumours')
        if v is None:
            v = self.__dict__['_rumours'] = {}
        return v

    @rumours.setter
    def rumours(self, value):
        self.__dict__['_rumours'] = dict(value)

    @property
    def tower_sightings(self) -> dict:
        v = self.__dict__.get('_tower_sightings')
        if v is None:
            v = self.__dict__['_tower_sightings'] = {}
        return v

    def _places_field(self) -> PlaceField:
        pf = getattr(self, 'places', None)
        if pf is None:
            pf = self.places = PlaceField(self.render, self.field, self.seed, self.landmarks.start,
                                          K['SHADOW_CAMERA_MASK'])
            self._place_sense_t = 0.0
        return pf

    def _refresh_world(self, force: bool = False):
        pf = self._places_field()
        pf.set_night(self.is_night() if hasattr(self, 'hour') else False)
        focus = self.giant.getPos(self.render) if self.controlled_name == 'giant' else self.human.getPos(self.render)
        changed = pf.update(focus)
        if changed and hasattr(self, 'invalidate_terrain_near'):
            self.invalidate_terrain_near(changed)       # only rebuilds chunks that are loaded (normally none)
        super()._refresh_world(force)
        hp = self.human.getPos(self.render)
        self._static_shade += [c for c in pf.shade_circles(self._sun_offset())
                               if math.hypot(c[0] - hp.x, c[1] - hp.y) < 80.0]
        self._check_places(focus)

    # ------------------------------------------------------------ discovery
    def _check_places(self, focus: Point3):
        if not hasattr(self, 'stats') or not hasattr(self, '_snd'):
            return                                       # still starting up
        pf = self.places
        hp = self.human.getPos(self.render)
        for pl in pf.shown.values():
            if pl.found or (night_only(pl.kind) and not pf.night):
                continue
            near_me = self.human_alive and _flat_dist(pl.pos, hp) <= pl.radius + 16.0
            near_ride = self.controlled_name == 'giant' and _flat_dist(pl.pos, focus) <= pl.radius + 24.0
            if near_me or near_ride:
                self.discover_place(pl)
                return
        # Indigo notices places before you do (only when you walk together)
        gp = self.giant.getPos(self.render)
        if not (self.giant_alive and self.human_alive and _flat_dist(gp, hp) <= 45.0):
            return
        for pl in pf.shown.values():
            if night_only(pl.kind) and not pf.night:
                continue
            reach = (BLOOM_SENSE_RADIUS if pl.kind == 'bloom' else
                     (LEGEND_SENSE_RUMOURED if self.rumours.get(pl.kind) else LEGEND_SENSE_RADIUS)
                     if pl.kind in LEGEND_NAMES else SENSE_RADIUS)
            if not pl.found and not pl.sensed and _flat_dist(pl.pos, hp) <= reach:
                pl.sensed = True
                self.sfx('hum_indigo_sense', gp)
                if pl.kind in LEGEND_NAMES:
                    self.notice = {'pos': Point3(pl.pos), 't': desert.NOTICE_TIME * 2}
                    self.say(f'Nyx stops dead and stares {self.bearing_words(pl.pos)}. '
                             'Something enormous lies out there.', 5.0)
                elif pl.kind == 'bloom':
                    self.say(f'Nyx stops and turns its head {self.bearing_words(pl.pos)}, uneasy. '
                             'Something pale grows out there.', 4.5)
                else:
                    self.say(f'Nyx turns its head {self.bearing_words(pl.pos)}. Something stands out there.', 3.5)
                return

    def discover_place(self, pl: Place):
        pl.found = True
        pl.sensed = True
        self.stats['places'] += 1
        new_kind = pl.kind not in self.found_kinds
        self.found_kinds.add(pl.kind)
        if pl.kind in LEGEND_NAMES:
            self.stats['legends'] += 1
            self.rumours.pop(pl.kind, None)
        self.lore_log.append(f'{pl.name[0].upper() + pl.name[1:]}.  {pl.lore}')
        self.sfx('legend_found' if pl.kind in LEGEND_NAMES else 'landmark_study', pl.pos)
        what = KINDS[pl.kind][4]
        hint = {'search': '  Something may be hidden here.', 'drink': '  The water is cold.',
                'rest': '  A good place to rest.', 'uproot': '  You could tear it out of the ground.',
                'climb': '  You could climb it and look out.', 'drinkdeep': '  You could climb down and drink.'
                }.get(what, '')
        if pl.kind in NIGHT_ONLY:
            hint = '  It is warm among the stones.'
        text = f'{pl.name[0].upper() + pl.name[1:]}.\n{pl.lore}{hint}'
        clues = []
        if pl.kind in BLOOM_HINTS:
            clue = self.give_bloom_hint(pl)
            if clue:
                clues.append(clue)
        clues += self.give_rumours(pl)
        if clues:
            text += '\n' + '\n'.join(clues)
        if new_kind and pl.kind not in LEGEND_NAMES:
            text += f'\n(a new kind of place: {len(self.found_kinds & set(catalogue_kinds()))} of {len(catalogue_kinds())} known)'
        seconds = 10.0 if pl.kind in LEGEND_NAMES else 8.0 if clues else 6.0
        self.say(text, seconds)

    def give_rumours(self, pl: Place) -> list:
        """Pass 51: places that know a story about a legend tell you which way it lies."""
        out = []
        layout = self.places.layout
        d0 = _flat_dist(pl.pos, layout.start)
        for legend, sources in RUMOUR_FROM.items():
            if pl.kind not in sources or self.places.is_found(layout.legends()[legend][2]):
                continue
            if tier_of(pl.kind) == 'common' and d0 < RUMOUR_COMMON_MIN:
                continue
            x, y, _cell = layout.legends()[legend]
            gx, gy = rumour_guess(self.seed, pl.pid, (pl.pos.x, pl.pos.y), (x, y),
                                  RUMOUR_VAGUE_TITAN if pl.kind == 'titan' else None)
            self.rumours.setdefault(legend, []).append((gx, gy))
            ex, ey = rumour_estimate(self.rumours[legend])
            template = RUMOUR_FROM_TITAN if pl.kind == 'titan' else RUMOUR_TEXT[legend]
            clue = template.format(bearing=self.bearing_words(Point3(ex, ey, 0.0)))
            self.lore_log.append(clue)
            out.append(clue)
        return out

    def rumour_words(self, legend: str) -> str:
        guesses = self.rumours.get(legend) or []
        if not guesses:
            return ''
        ex, ey = rumour_estimate(guesses)
        where = Point3(ex, ey, 0.0)
        sure = ('one story says', 'two stories say', 'several stories say')[min(2, len(guesses) - 1)]
        return (f'{KIND_WORDS[legend]}:  {sure} {distance_words(_flat_dist(where, self.human.getPos(self.render)))}, '
                f'{self.bearing_words(where)}')

    def atlas_lines(self):
        """Pass 51: the journal's places page - every kind, '?' for the ones not found yet."""
        kinds = set(self.found_kinds)
        rows = []
        for tier, (ks, _d) in TIERS.items():
            got = [k for k in ks if k in kinds]
            words = [KIND_WORDS[k] if k in kinds else '?' for k in ks]
            rows.append((tier, f'{len(got)}/{len(ks)}', words))
        rumours = [self.rumour_words(legend) for legend in sorted(self.rumours) if self.rumours[legend]]
        return rows, rumours

    def give_bloom_hint(self, pl: Place) -> str:
        """Pass 47: camps, totems and statues point toward the nearest pale bloom still growing.
        Pass 51: a camp near the start does not know (only the far ones do), and the drawing is rough."""
        if tier_of(pl.kind) == 'common' and _flat_dist(pl.pos, self.places.layout.start) < RUMOUR_COMMON_MIN:
            return ''
        spot = self.places.bloom_near(pl.pos)
        if spot is None or self.red_dead:
            return ''
        x, y = rumour_guess(self.seed, ('bloom', pl.pid), (pl.pos.x, pl.pos.y), spot)   # Pass 51: roughly right
        target = Point3(x, y, self.field.height(x, y))
        self.bloom_hint = (x, y)
        self.notice = {'pos': Point3(target), 't': desert.NOTICE_TIME}      # Indigo gazes that way too
        clue = BLOOM_HINTS[pl.kind].format(bearing=self.bearing_words(target))
        self.lore_log.append(clue)
        return clue

    def bloom_words(self) -> str:
        """Journal line about the pale bloom (no map: a direction from where you stand)."""
        if self.red_dead:
            if getattr(self, 'gleebs_state', None) in ('arriving', 'waiting'):
                return 'Crimson sleeps and will not wake. Gleebs waits in its light for you and Nyx.'
            return 'Crimson sleeps and will not wake.'
        if self.pooled_count('bane') > 0:
            return 'you carry pale scraps: work one into a blood branch, and wait.'
        if any(b.poisoned for b in self.flora.branches.values()):
            return 'a poisoned blood branch waits for Crimson.'
        hint = getattr(self, 'bloom_hint', None)
        if hint is None:
            return 'the small people drew a pale flower. you do not know where.'
        return f'the pale bloom: far away, {self.bearing_words(Point3(hint[0], hint[1], 0))}.'

    # ------------------------------------------------------------ E actions
    def _e_target(self):
        kind, target = super()._e_target()
        if kind is None and self.controlled_name == 'human' and self.human_alive and not self.carried \
                and self.hidden_shell is None and getattr(self, 'places', None) is not None:
            what, pl = self.places.action_at(self.human.getPos(self.render), self.place_helpers())
            if what is not None:
                return what, pl
        return kind, target

    def place_helpers(self) -> dict:
        hp = self.human.getPos(self.render)
        indigo = bool(self.giant_alive and _flat_dist(self.giant.getPos(self.render), hp) <= INDIGO_HELP_RANGE)
        return {'indigo': indigo, 'night': self.is_night() if hasattr(self, 'hour') else False}

    def place_prompt(self, kind, target) -> str:
        if kind == 'search':
            if isinstance(target, Place) and target.kind in NEEDS:
                return {'hand': 'Nyx: open the hand', 'geode': 'Nyx: break the crystal',
                        'titan': 'Nyx: lift the fallen rib', 'statue': 'search the moonlit hollow'}[target.kind]
            return f'search {target.name}' if isinstance(target, Place) else 'search'
        if kind == 'need':
            return 'look closer'
        if kind == 'uproot':
            return 'tear out the pale bloom'
        return {'drink': 'drink and cool off', 'rest': 'rest inside the ring', 'climb': 'climb the tower',
                'drinkdeep': 'climb down and drink'}.get(kind, '')

    def _complete_e(self, kind, target):
        if kind == 'need':
            self.say(NEED_WORDS[target.kind], 4.5)
            return
        if kind == 'climb':
            if not target.searched:
                target.searched = True
                self.climb_tower(target)
            return
        if kind == 'drinkdeep':
            self.heat = 0.0
            if hasattr(self, 'chill'):
                self.chill = 0.0
            self.human_health = K['HUMAN_MAX_HEALTH']
            self.stamina = 100.0
            if self.has_upgrade('waterskin'):
                self.water_sips = 3
            self.sfx('well_drink', self.human.getPos(self.render))
            if 'wellwater' not in self.upgrades:
                self.upgrades.add('wellwater')
                self.lore_log.append('You drank from the Sky Well. The sun sits lighter on you ever since.')
                self.say('The water is so cold it hurts, and then it does not.\n'
                         'From now on the sun heats you more slowly.', 6.0)
            else:
                self.say('cold, sweet water from very far down.', 3.0)
            return
        if kind == 'search':
            if not target.searched:
                target.searched = True
                cache = dict(KINDS[target.kind][5] or {})
                lost = self.give_items(cache)
                self.sfx('dig', target.pos)
                got = ', '.join(f'{n} {desert.ITEM_LABEL.get(i, i)}' for i, n in cache.items())
                first = DONE_WORDS.get(target.kind)
                text = (first + '\n' if first else '') + f'hidden here: {got}'
                if target.kind == 'cradle':
                    text += ('\nAt the bottom, tiny scratches: a small red giant, and a blood branch, drawn with care.'
                             if not self.red_dead else '\nIt is quiet here now.')
                if first and target.kind in ('hand', 'geode', 'titan'):
                    self.notice = {'pos': Point3(target.pos), 't': desert.NOTICE_TIME}
                self.say(text + ('\n(you could not carry everything)' if lost else ''), 5.0 if first else 3.5)
                self.stats['caches'] += 1
            return
        if kind == 'uproot':
            if not target.searched:
                target.searched = True
                self.places.reshow(target)
                lost = self.give_items({'bane': BLOOM_SCRAPS})
                self.stats['blooms'] += 1
                self.sfx('branch_smash', target.pos)
                self.bloom_hint = None                      # Pass 51: hints are rough; any bloom answers them
                self.lore_log.append('You tore up a pale bloom. Its scraps are bitter and cold.')
                key = controls.label(getattr(self, 'bindings', {}), 'poison')
                self.say('You tear up the pale bloom. Its scraps are bitter and cold in your hands.\n'
                         f'Crimson loves blood branches. Work a scrap into one ({key}), '
                         'and let it find it.' + ('\n(you could not carry them all)' if lost else ''), 9.0)
            return
        if kind == 'drink':
            self.heat = 0.0
            self.human_health = min(K['HUMAN_MAX_HEALTH'], self.human_health + 20.0)
            self.stamina = min(100.0, self.stamina + 30.0)
            if self.has_upgrade('waterskin'):
                self.water_sips = 3
            self.sfx('eat', self.human.getPos(self.render))
            self.say('cold water.' + ('  the water skin is full.' if self.has_upgrade('waterskin') else ''), 2.5)
            return
        if kind == 'rest':
            self.stamina = REST_STAMINA
            self.winded = False
            self.heat = max(0.0, self.heat - REST_COOLING)
            self.say('you sit a while in the ring. your breath comes back.', 3.0)
            return
        super()._complete_e(kind, target)

    def climb_tower(self, tower: Place):
        """Pass 51: from the top of a tower you can see what the fog hides below."""
        pf = self.places
        night = pf.night
        spot = pf.unfound_near(tower.pos, TOWER_SIGHT, night)
        self.sfx('landmark_study', tower.pos)
        self.sfx('tower_climb', tower.pos)
        lines = ['You climb the little steps inside the tower. At the top the wind is cold and the fog lies below you.']
        if spot is not None:
            d = _flat_dist(spot.pos, tower.pos)
            what = 'something enormous' if spot.kind in LEGEND_NAMES else 'something standing' if \
                KINDS[spot.kind][3] >= 8.0 else 'something low, catching the light'
            lines.append(f'{what[0].upper() + what[1:]}, {distance_words(d)}, {self.bearing_words(spot.pos)}.')
            pl = pf.places.get(spot.pid)
            if pl is not None:
                pl.sensed = True
            self.notice = {'pos': Point3(spot.pos.x, spot.pos.y, self.field.height(spot.pos.x, spot.pos.y)),
                           't': desert.NOTICE_TIME}
            self.tower_sightings[repr(spot.pid)] = (spot.pos.x, spot.pos.y)
        else:
            lines.append('Only dunes, all the way round.')
        for legend, (x, y, cell) in pf.layout.legends().items():
            if not pf.is_found(cell) and math.hypot(x - tower.pos.x, y - tower.pos.y) <= TOWER_SIGHT * 2.4 \
                    and legend not in self.rumours:
                gx, gy = rumour_guess(self.seed, ('tower', tower.pid), (tower.pos.x, tower.pos.y), (x, y))
                self.rumours[legend] = [(gx, gy)]
                clue = (f'And very far off, {self.bearing_words(Point3(gx, gy, 0))}, a shape too big to be a dune: '
                        f'{KIND_WORDS[legend]}, perhaps.')
                lines.append(clue)
                self.lore_log.append(clue)
                break
        self.say('\n'.join(lines), 7.0)

    # ------------------------------------------------------------ water
    def survival_step(self, dt: float):
        super().survival_step(dt)
        pf = getattr(self, 'places', None)
        if pf is None or self.world_frozen() or not self.human_alive:
            return
        hp = self.human.getPos(self.render)
        if pf.among_lanterns(hp) and hasattr(self, 'chill'):        # Pass 51: warm among the lantern stones
            self.chill = max(0.0, self.chill - LANTERN_WARMTH * dt)
        if self.carried:
            return
        if pf.in_water(hp):
            self.heat = max(0.0, self.heat - WADE_COOLING * dt)

    # ------------------------------------------------------------ save
    def places_snapshot(self) -> dict:
        pf = self._places_field()
        found = {repr(p.pid) for p in pf.places.values() if p.found} | pf.pending_found
        searched = {repr(p.pid) for p in pf.places.values() if p.searched} | pf.pending_searched
        hint = getattr(self, 'bloom_hint', None)
        return {'found': sorted(found), 'searched': sorted(searched),
                'bloom_hint': [round(hint[0], 2), round(hint[1], 2)] if hint else None,
                'kinds': sorted(self.found_kinds),                                              # Pass 51
                'sensed': sorted(pf.pending_sensed | {repr(p.pid) for p in pf.places.values() if p.sensed and not p.found}),
                'sightings': {k: [round(x, 1), round(y, 1)] for k, (x, y) in self.tower_sightings.items()},
                'rumours': {k: [[round(x, 1), round(y, 1)] for x, y in g] for k, g in self.rumours.items()}}

    def apply_places(self, data: dict):
        pf = self._places_field()
        pf.pending_found = set(data.get('found', []))
        pf.pending_searched = set(data.get('searched', []))
        pf.pending_sensed = set(data.get('sensed', []))
        self.tower_sightings.clear()
        for k, v in (data.get('sightings') or {}).items():
            if isinstance(v, (list, tuple)) and len(v) == 2:
                self.tower_sightings[k] = (float(v[0]), float(v[1]))
        hint = data.get('bloom_hint')
        self.bloom_hint = (float(hint[0]), float(hint[1])) if hint else None
        # Pass 51: kinds known and rumours (older saves: rebuilt from the places found)
        kinds = data.get('kinds')
        if kinds is None:
            kinds = set()
            for key in pf.pending_found:
                try:
                    cx, cy = (int(v) for v in key.strip('()').split(','))
                except ValueError:
                    continue
                pl = pf.layout.region(cx, cy)
                if pl is not None:
                    kinds.add(pl.kind)
        self.found_kinds = {k for k in kinds if k in KINDS}
        rumours = {}
        for k, v in (data.get('rumours') or {}).items():
            if k not in LEGEND_NAMES or not isinstance(v, (list, tuple)):
                continue
            pts = v if v and isinstance(v[0], (list, tuple)) else [v]
            guesses = [(float(p[0]), float(p[1])) for p in pts if isinstance(p, (list, tuple)) and len(p) == 2]
            if guesses:
                rumours[k] = guesses
        self.rumours = rumours
        for p in pf.places.values():
            p.found = repr(p.pid) in pf.pending_found
            p.searched = repr(p.pid) in pf.pending_searched
            p.sensed = p.found or repr(p.pid) in pf.pending_sensed
