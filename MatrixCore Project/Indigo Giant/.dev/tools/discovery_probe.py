"""Pass 51 — how long does the desert take to discover?

A headless explorer walks the world the way a curious player does and records WHEN each thing
is first found, in real play time (hours at the keyboard, days and nights included).

Nothing is rendered: it reads the same deterministic layout rules the game uses
(places.PlaceLayout), so the numbers match the world a player gets with that seed.

PLAYER PROFILES   (speeds from main.py, time from daycycle.py)
    walker   on foot with Indigo: walk/jog mix, stops for shade, food and shells
    mixed    half on foot, half riding Indigo (the usual player)
    rider    rides Indigo nearly everywhere (with the shoulder canopy)
A day is 12 real minutes, the night 4 (sleeping skips most of it). Each profile moves for a
share of the daylight; the rest is shade, digging, eating, fights, looking around.

SEEING THINGS   (the fog is exp2: 0.013/m on foot, 0.0048/m riding high on Indigo)
    on foot   ~80 m + 5 m per metre of height (max 220 m) - tall shapes are a 5% ghost past that
    riding    ~180 m + 9 m per metre of height (max 420 m)
    Indigo    walking together, it senses a place within 230 m (legends 520 m) and turns its head
    night     the lantern stones only show at night; the explorer is out after dark every 3rd night
    towers    climbing one points out the nearest unfound place within 1.9 km
    rumours   places that tell of a legend (or the pale bloom) give its direction; on each new
              leg the explorer follows a rumour half the time
The explorer turns aside to every place it notices, then carries on. Between places it picks
the heading that leads farthest from where it has already been (plus a little whim).

    python .dev/tools/discovery_probe.py                 3 seeds x 3 profiles, 60 play hours each
    python .dev/tools/discovery_probe.py --hours 30 --seeds 5
    python .dev/tools/discovery_probe.py --json out.json
"""
from __future__ import annotations

import argparse
import json
import math
import random
import sys
from collections import defaultdict

import sys as _sys                                  # Pass 62: the game folder is two levels up
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))
from indigo_giant import daycycle
from indigo_giant import places

STEP = 20.0                       # metres per simulation step
ON_FOOT = 3.3                     # m/s on foot, walking and jogging (Pass 58)
DAY_REAL_S = (daycycle.DAY_END - daycycle.DAY_START) * daycycle.SECONDS_PER_DAY_HOUR   # 720 s of daylight
NIGHT_WALK_S = 120.0              # every third night: two minutes walking in the dark
NIGHT_REAL_S = 45.0               # sleeping through the night: fade, waking, a little night walking
PROFILES = {
    #          speed m/s, share of daylight spent moving, riding?
    'walker': (ON_FOOT, 0.60, False),   # Pass 58: walk 1.45 / jog 5.6 m/s (Pass 52: 1.2 / 4.4 -> 2.6)
    'mixed':  (3.8, 0.58, None),  # None: alternates on foot / riding each day
    'rider':  (6.0, 0.55, True),
}
INDIGO_SENSE = places.SENSE_RADIUS
LEG_MIN, LEG_MAX = 400.0, 1400.0


def sight(kind_height: float, riding: bool) -> float:
    if riding:
        return min(420.0, 180.0 + 9.0 * kind_height)
    return min(220.0, 80.0 + 5.0 * kind_height)


FOLLOW_RUMOUR = 0.5
SEARCH_TRIES = 5


class Explorer:
    def __init__(self, seed: int, profile: str, hours: float):
        self.layout = places.PlaceLayout(seed, places.default_start())
        self.rng = random.Random(seed * 31 + len(profile))
        self.speed, self.move_share, self.ride_mode = PROFILES[profile]
        self.limit_s = hours * 3600.0
        self.x, self.y = self.layout.start.x, self.layout.start.y
        self.t = 0.0                       # real play seconds
        self.day_moving_left = DAY_REAL_S * self.move_share
        self.day = 1
        self.found: dict = {}              # pid -> (t, place)
        self.first_kind: dict = {}         # kind -> t
        self.visited_ends = [(self.x, self.y)]
        self.checked: set = set()
        self.target = None
        self.leg_left = 0.0
        self.heading = self.rng.uniform(0, 2 * math.pi)
        self.walked = 0.0
        self.rumours: dict = {}            # legend -> (x, y) best estimate
        self.guesses = defaultdict(list)
        self.searches = defaultdict(int)
        self.night_left = 0.0
        self.pending_sighting = None

    # ---------------------------------------------------------------- time
    def riding(self) -> bool:
        if self.ride_mode is None:
            return self.day % 2 == 0
        return self.ride_mode

    def speed_now(self) -> float:
        return self.speed if self.ride_mode is not None else (6.0 if self.riding() else ON_FOOT)

    def is_night_window(self) -> bool:
        """The explorer is out for a short walk after dark every third night (night-only places)."""
        return self.night_left > 0.0

    def spend(self, metres: float):
        dt = metres / self.speed_now()
        self.walked += metres
        if self.night_left > 0.0:                      # a night walk, slower and closer
            self.night_left -= dt
            self.t += dt
            if self.night_left <= 0.0:
                self._new_day()
            return
        self.day_moving_left -= dt
        self.t += dt / self.move_share                 # the stops happen alongside the walking
        if self.day_moving_left <= 0.0:
            if self.day % 3 == 0:
                self.night_left = NIGHT_WALK_S
            else:
                self._new_day()

    def _new_day(self):
        self.day += 1
        self.t += NIGHT_REAL_S
        self.day_moving_left = DAY_REAL_S * self.move_share

    # ---------------------------------------------------------------- seeing
    def notice(self):
        riding = self.riding()
        reach = max(420.0 if riding else 220.0, places.LEGEND_SENSE_RUMOURED, places.BLOOM_SENSE_RADIUS)
        best = None
        for pl in self.layout.places_within(self.x, self.y, reach):
            if pl.pid in self.found:
                continue
            d = math.hypot(pl.pos.x - self.x, pl.pos.y - self.y)
            if places.night_only(pl.kind):
                see = 260.0 if self.night_walk else 0.0      # their glow shows through the night haze
            else:
                see = max(sight(places.KINDS[pl.kind][3], riding), INDIGO_SENSE)
                if pl.kind == 'bloom':
                    see = max(see, places.BLOOM_SENSE_RADIUS)
                if pl.kind in places.LEGEND_NAMES:
                    see = max(see, places.LEGEND_SENSE_RUMOURED if self.guesses.get(pl.kind)
                              else places.LEGEND_SENSE_RADIUS)
            if d <= see and (best is None or d < best[0]):
                best = (d, pl)
        return None if best is None else best[1]

    def record(self, pl):
        self.found[pl.pid] = (self.t, pl)
        self.first_kind.setdefault(pl.kind, self.t)
        lay = self.layout
        self.rumours.pop(pl.kind, None)
        d0 = math.hypot(pl.pos.x - lay.start.x, pl.pos.y - lay.start.y)
        for legend, sources in places.RUMOUR_FROM.items():          # the same rules as the game
            x, y, cell = lay.legends()[legend]
            if pl.kind in sources and cell not in self.found and not (
                    places.tier_of(pl.kind) == 'common' and d0 < places.RUMOUR_COMMON_MIN):
                self.guesses[legend].append(places.rumour_guess(
                    lay.seed, pl.pid, (pl.pos.x, pl.pos.y), (x, y),
                    places.RUMOUR_VAGUE_TITAN if pl.kind == 'titan' else None))
                self.rumours[legend] = places.rumour_estimate(self.guesses[legend])
        if pl.kind in places.BLOOM_HINTS and 'bloom' not in self.first_kind and not (
                places.tier_of(pl.kind) == 'common' and d0 < places.RUMOUR_COMMON_MIN):
            fx, fy, _c = lay._first_bloom()
            self.rumours['bloom'] = places.rumour_guess(lay.seed, ('bloom', pl.pid), (pl.pos.x, pl.pos.y), (fx, fy))
        if pl.kind == 'tower':                                       # climb it and look out
            best = None
            for other in lay.places_within(pl.pos.x, pl.pos.y, places.TOWER_SIGHT):
                if other.pid in self.found or places.night_only(other.kind):
                    continue
                d = math.hypot(other.pos.x - pl.pos.x, other.pos.y - pl.pos.y)
                if best is None or d < best[0]:
                    best = (d, other)
            if best is not None:
                self.pending_sighting = best[1]
            for legend, (x, y, cell) in lay.legends().items():
                if cell not in self.found and math.hypot(x - pl.pos.x, y - pl.pos.y) <= places.TOWER_SIGHT * 2.4 \
                        and legend not in self.rumours:
                    g = places.rumour_guess(lay.seed, ('tower', pl.pid), (pl.pos.x, pl.pos.y), (x, y))
                    self.guesses[legend].append(g)
                    self.rumours[legend] = g
                    break

    # ---------------------------------------------------------------- moving
    def new_leg(self):
        for k, (tx, ty) in list(self.rumours.items()):          # reached a story's spot: search round it
            if math.hypot(tx - self.x, ty - self.y) < 300.0:     # a few times, then let it go until a new story
                self.searches[k] += 1
                if self.searches[k] > SEARCH_TRIES:
                    del self.rumours[k]
                else:
                    a = self.rng.uniform(0, 2 * math.pi)
                    r = self.rng.uniform(700.0, 1600.0)
                    self.rumours[k] = (tx + math.cos(a) * r, ty + math.sin(a) * r)
        if self.rumours and self.rng.random() < FOLLOW_RUMOUR:
            tx, ty = min(self.rumours.values(), key=lambda p: math.hypot(p[0] - self.x, p[1] - self.y))
            d = math.hypot(tx - self.x, ty - self.y)
            if d > 60.0:
                self.heading = math.atan2(ty - self.y, tx - self.x)
                self.leg_left = min(d, LEG_MAX)
                return
        best = None
        for _ in range(10):
            a = self.rng.uniform(0, 2 * math.pi)
            L = self.rng.uniform(LEG_MIN, LEG_MAX)
            ex, ey = self.x + math.cos(a) * L, self.y + math.sin(a) * L
            novelty = min(math.hypot(ex - vx, ey - vy) for vx, vy in self.visited_ends[-400:])
            score = novelty * self.rng.uniform(0.8, 1.2)
            if best is None or score > best[0]:
                best = (score, a, L)
        _s, self.heading, self.leg_left = best

    def run(self):
        self.night_walk = False
        while self.t < self.limit_s:
            self.night_walk = self.is_night_window()
            if self.target is None and self.pending_sighting is not None:
                self.target, self.pending_sighting = self.pending_sighting, None
                if self.target.pid in self.found:
                    self.target = None
            if self.target is None:
                pl = self.notice()
                if pl is not None:
                    self.target = pl
            if self.target is not None:
                dx, dy = self.target.pos.x - self.x, self.target.pos.y - self.y
                d = math.hypot(dx, dy)
                if d <= self.target.radius + 16.0:
                    self.record(self.target)
                    self.target = None
                    continue
                step = min(STEP, d)
                self.x += dx / d * step
                self.y += dy / d * step
                self.spend(step)
                continue
            if self.leg_left <= 0.0:
                self.visited_ends.append((self.x, self.y))
                self.new_leg()
            self.x += math.cos(self.heading) * STEP
            self.y += math.sin(self.heading) * STEP
            self.leg_left -= STEP
            self.spend(STEP)
        return self


def summarise(ex: Explorer) -> dict:
    h = lambda s: round(s / 3600.0, 2)                  # noqa: E731
    kinds_all = places.catalogue_kinds()
    tiers = defaultdict(list)
    for k in kinds_all:
        tiers[places.tier_of(k)].append(k)
    got = sorted(ex.first_kind.items(), key=lambda kv: kv[1])
    out = {
        'play_hours': h(ex.t), 'days': ex.day, 'km_walked': round(ex.walked / 1000.0, 1),
        'places_found': len(ex.found),
        'places_per_hour': round(len(ex.found) / max(1e-6, ex.t / 3600.0), 2),
        'kinds_found': f'{len(ex.first_kind)}/{len(kinds_all)}',
        'first_of_kind_h': {k: h(t) for k, t in got},
        'tiers': {},
    }
    for tier, ks in tiers.items():
        times = [ex.first_kind[k] for k in ks if k in ex.first_kind]
        out['tiers'][tier] = {'found': f'{len(times)}/{len(ks)}',
                              'all_by_h': h(max(times)) if len(times) == len(ks) else None,
                              'first_h': h(min(times)) if times else None}
    n = len(kinds_all)
    order = sorted(ex.first_kind.values())
    for pct in (25, 50, 75, 90, 100):
        need = math.ceil(n * pct / 100)
        out[f'kinds_{pct}pct_h'] = h(order[need - 1]) if len(order) >= need else None
    blooms = [t for t, pl in ex.found.values() if pl.kind == 'bloom']
    out['first_bloom_h'] = h(min(blooms)) if blooms else None
    out['legends_h'] = {k: h(ex.first_kind[k]) if k in ex.first_kind else None for k in places.LEGEND_NAMES}
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--hours', type=float, default=60.0)
    ap.add_argument('--seeds', type=int, default=3)
    ap.add_argument('--profiles', default='walker,mixed,rider')
    ap.add_argument('--json', default=None)
    args = ap.parse_args(argv)
    results = {}
    for profile in args.profiles.split(','):
        for s in range(args.seeds):
            seed = 1729 + s * 101
            r = summarise(Explorer(seed, profile, args.hours).run())
            results[f'{profile}/{seed}'] = r
            tiers = '  '.join(f"{t} {v['found']}@{v['all_by_h']}h" for t, v in sorted(r['tiers'].items()))
            print(f"{profile:6s} seed {seed}: {r['places_found']:4d} places ({r['places_per_hour']}/h), "
                  f"kinds {r['kinds_found']}  50%@{r['kinds_50pct_h']}h 90%@{r['kinds_90pct_h']}h "
                  f"100%@{r['kinds_100pct_h']}h  bloom@{r['first_bloom_h']}h  | {tiers}")
            print('         legends:', r['legends_h'])
            sys.stdout.flush()
    if args.json:
        with open(args.json, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=1)
    return results


if __name__ == '__main__':
    main()
