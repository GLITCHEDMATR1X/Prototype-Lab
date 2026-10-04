"""Pass 51 check: the deep desert - tiers of places by distance, the four legends, night-only
lantern stones, rumours that point (roughly) toward legends, secrets that need Indigo or the
night, tower lookouts, the Sky Well's gift, the journal's places page, and saves.

    python .dev/checks/pass51.py
"""
from __future__ import annotations

import math
import os
import sys
import tempfile
from pathlib import Path

from panda3d.core import Point3

HERE = Path(__file__).resolve().parents[2]          # Pass 62: the game folder
TMP = Path(tempfile.mkdtemp(prefix='indigo_save51_'))
os.environ['INDIGO_SAVE_DIR'] = str(TMP)
sys.argv = sys.argv[:1]

import sys as _sys                                  # Pass 62: the game folder is two levels up
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))
from indigo_giant import desert         # noqa: E402
from indigo_giant import app as game   # noqa: E402
from indigo_giant import places         # noqa: E402
from indigo_giant import places_geom    # noqa: E402

FAILS = []
GLB = HERE / 'assets/Universal Animation Library[Standard]/Unreal-Godot/UAL1_Standard.glb'
CLOCK = [0.0]


def check(name, ok, detail=''):
    print(('PASS ' if ok else 'FAIL ') + name + (f'  [{detail}]' if detail != '' else ''))
    if not ok:
        FAILS.append(name)


def ground(a, x, y):
    return Point3(x, y, a.field.height(x, y))


def go(a, x, y, giant_near=False):
    """Stand at (x, y); Indigo 60 m away (or right beside you), the red one far off."""
    a.human.setPos(ground(a, x, y))
    gx, gy = (x + 6, y - 5) if giant_near else (x + 60, y - 50)
    a.giant.setPos(ground(a, gx, gy))
    a.red_giant.setPos(ground(a, x + 3000, y))
    a.red_state = 'idle'
    a.cam_target = a._controlled_focus()
    a._refresh_world(force=True)


def tick(a, seconds, dt=1 / 30.0):
    for _ in range(int(seconds / dt)):
        CLOCK[0] += dt
        a.survival_step(dt)


def find_kind(layout, kind, rmin=0.0, rmax=12000.0, step=900.0):
    s = layout.start
    for R in range(int(rmin), int(rmax), int(step)):
        for ang in range(0, 360, 6):
            x, y = s.x + R * math.cos(math.radians(ang)), s.y + R * math.sin(math.radians(ang))
            for pl in layout.places_within(x, y, 800.0):
                if pl.kind == kind:
                    return pl
    return None


def near(a, pl):
    """Lay the region out and stand just outside the place (not yet found)."""
    a.places.update(pl.pos)
    p = a.places.places[pl.pid]
    return p


def e_do(a, pl, giant_near=False):
    """Stand beside a place and hold E until it completes. Returns (kind, target) that ran."""
    go(a, pl.pos.x + pl.radius + 1.0, pl.pos.y, giant_near)
    kind, target = a._e_target()
    if kind is not None:
        a._complete_e(kind, target)
    return kind, target


def main():
    # ------------------------------------------------------------ layout rules (no window)
    lay = places.PlaceLayout(1729, Point3(12.0, -7.0, 0.0))
    lay2 = places.PlaceLayout(1729, Point3(12.0, -7.0, 0.0))
    too_close, counts, samples = [], {}, 0
    for R in range(0, 20001, 500):
        for ang in range(0, 360, 10):
            x = lay.start.x + R * math.cos(math.radians(ang))
            y = lay.start.y + R * math.sin(math.radians(ang))
            for pl in lay.places_within(x, y, 400.0):
                samples += 1
                d = math.hypot(pl.pos.x - lay.start.x, pl.pos.y - lay.start.y)
                tier = places.tier_of(pl.kind)
                counts[tier] = counts.get(tier, 0) + 1
                if tier != 'legend' and d < places.TIERS[tier][1] - places.PLACE_CELL:
                    too_close.append((pl.kind, round(d)))
                if pl.kind == 'bloom' and pl.pid != lay._first_bloom()[2] and d < places.RARE_BLOOM_MIN:
                    too_close.append(('bloom', round(d)))
    check('every tier keeps to its distance (uncommon from 1.6 km, rare from 3.4 km, extra blooms from 9 km)',
          not too_close and counts.get('uncommon') and counts.get('rare'), f'{counts} {too_close[:4]}')
    same = True
    for cx in range(-12, 12):
        for cy in range(-12, 12):
            p, q = lay.region(cx, cy), lay2.region(cx, cy)
            if (p is None) != (q is None) or (p is not None and (p.kind != q.kind or p.pos != q.pos)):
                same = False
    check('the same seed always gives the same desert', same)

    legends = lay.legends()
    dists = {k: round(math.hypot(x - lay.start.x, y - lay.start.y)) for k, (x, y, _c) in legends.items()}
    want = dict(places.LEGENDS)
    in_cells = all(lay.region(*c).kind == k for k, (_x, _y, c) in legends.items())
    apart = min(math.hypot(a[0] - b[0], a[1] - b[1]) for i, a in enumerate(legends.values())
                for b in list(legends.values())[i + 1:])
    check('four legends, one each, at their distances and far apart',
          all(abs(dists[k] - want[k]) < 5 for k in want) and in_cells and apart > 3000, f'{dists}, closest pair {apart:.0f} m')

    near_regions = sorted(((math.hypot((cx + 0.5) * places.PLACE_CELL - lay.start.x,
                                       (cy + 0.5) * places.PLACE_CELL - lay.start.y), cx, cy)
                           for cx in range(-6, 7) for cy in range(-6, 7)))
    first_kinds = [lay.region(cx, cy).kind for _d, cx, cy in near_regions if lay.region(cx, cy) is not None][:8]
    check('the eight places nearest the start are one of each common kind', set(places.TIERS['common'][0]) <= set(first_kinds),
          ', '.join(first_kinds[:10]))

    tx, ty = 9000.0, 3000.0
    guesses = [places.rumour_guess(7, ('src', i), (0.0, 0.0), (tx, ty)) for i in range(40)]
    worst = max(math.hypot(g[0] - tx, g[1] - ty) for g in guesses)
    one = math.hypot(guesses[0][0] - tx, guesses[0][1] - ty)
    est = places.rumour_estimate(guesses)
    check('a story is only roughly right; many stories together point true',
          worst <= places.RUMOUR_VAGUE * math.hypot(tx, ty) + 1 and math.hypot(est[0] - tx, est[1] - ty) < 1200,
          f'one off by {one:.0f} m, worst {worst:.0f} m, forty together {math.hypot(est[0] - tx, est[1] - ty):.0f} m')

    tris = {}
    for kind in ('lanterns', 'geode', 'village', 'titan', 'well', 'city', 'cradle'):
        np_ = places_geom.build_place(kind, 11)
        tris[kind] = sum(np_.node().getGeom(i).getPrimitive(0).getNumPrimitives() for i in range(np_.node().getNumGeoms()))
    check('the seven new shapes build (and stay light)', all(0 < t < 30000 for t in tris.values()), str(tris))

    # ------------------------------------------------------------ in the game
    a = game.StreamingTerrainWithGiant(offscreen=True, giant_glb=GLB, new_game=True, persist=True, save_dir=TMP)
    a.time_frozen = True
    a.heat_factor_override = 0.0
    pf = a.places
    L = pf.layout
    a.hour = 12.0
    pf.set_night(False)

    # secrets that need Indigo: the stone hand
    hand = near(a, find_kind(L, 'hand', 1600))
    kind, _t = e_do(a, hand)
    said = a.hud_message.getText() if hasattr(a, 'hud_message') else ''
    blocked = kind == 'need' and not hand.searched
    kind2, _t = e_do(a, hand, giant_near=True)
    check('the stone hand stays shut until Indigo is beside you, then opens',
          blocked and kind2 == 'search' and hand.searched, f'{kind} -> {kind2}; "{said[:50]}"')

    # the sitting giant's hollow only by moonlight
    statue = near(a, find_kind(L, 'statue', 3400))
    k_day, _t = e_do(a, statue)
    a.hour = 23.0
    pf.set_night(True)
    k_night, _t = e_do(a, statue)
    check('the sitting giant\'s hollow shows only at night', k_day == 'need' and k_night == 'search' and statue.searched,
          f'day {k_day}, night {k_night}')
    rum = a.rumours.get('titan')
    check('the sitting giant tells a story of the Sleeping Titan (a rough direction, in the journal)',
          bool(rum) and any('Titan' in ln for ln in a.atlas_lines()[1]), f'{a.atlas_lines()[1][:1]}')

    # lantern stones: night only, warm
    lant = find_kind(L, 'lanterns', 1600)
    a.hour = 12.0
    pf.set_night(False)
    lp = near(a, lant)
    go(a, lp.pos.x + 2.0, lp.pos.y)
    a._check_places(a.human.getPos(a.render))
    hidden_by_day = (lp.node is None or lp.node.isHidden()) and not lp.found
    a.hour = 23.0
    pf.set_night(True)
    a._refresh_world(force=True)
    a._check_places(a.human.getPos(a.render))
    a.chill = 80.0
    a.giant.setPos(ground(a, lp.pos.x + 200, lp.pos.y))
    tick(a, 2.0)
    check('the lantern stones are hidden by day, found at night, and keep the cold off',
          hidden_by_day and lp.found and lp.node is not None and not lp.node.isHidden() and a.chill < 60.0,
          f'chill {a.chill:.0f}')
    a.hour = 12.0
    pf.set_night(False)

    # a tower lookout
    tower = near(a, find_kind(L, 'tower', 1600))
    k_t, _t = e_do(a, tower)
    check('climbing a tower points out the nearest place you have not found',
          k_t == 'climb' and tower.searched and a.tower_sightings, f'{len(a.tower_sightings)} sighted')
    k_t2, _t = e_do(a, tower)
    check('a tower is climbed once', k_t2 != 'climb')

    # legends: the Titan (needs Indigo), a rumour of the Cradle, the Sky Well's gift
    tx, ty, tcell = L.legends()['titan']
    sense_before = places.LEGEND_SENSE_RUMOURED if a.rumours.get('titan') else places.LEGEND_SENSE_RADIUS
    titan = near(a, L.region(*tcell))
    go(a, titan.pos.x + titan.radius + 10, titan.pos.y)
    a._check_places(a.human.getPos(a.render))
    k_ti, _t = e_do(a, titan)
    k_ti2, _t = e_do(a, titan, giant_near=True)
    check('the Sleeping Titan: found, its hollow needs Indigo, and it tells where the red one began',
          titan.found and k_ti == 'need' and k_ti2 == 'search' and bool(a.rumours.get('cradle'))
          and a.stats['legends'] >= 1, f'sense {sense_before:.0f} m, cradle story {a.rumours.get("cradle")}')
    wx, wy, wcell = L.legends()['well']
    well = near(a, L.region(*wcell))
    go(a, well.pos.x + 4.0, well.pos.y)
    a._check_places(a.human.getPos(a.render))
    a.heat = 60.0
    k_w, _t = e_do(a, well)
    had = 'wellwater' in a.upgrades
    a.heat = 0.0
    a.heat_factor_override = None
    rates = []
    for gift in (False, True):
        if gift:
            a.upgrades.add('wellwater')
        else:
            a.upgrades.discard('wellwater')
        a.heat = 0.0
        a.human.setPos(ground(a, well.pos.x + 400, well.pos.y + 400))
        a._refresh_world(force=True)
        tick(a, 3.0)
        rates.append(a.heat)
    a.heat_factor_override = 0.0
    a.upgrades.add('wellwater')
    check('drinking at the Sky Well: cooled, and the sun heats you 15% slower from then on',
          k_w == 'drinkdeep' and had and rates[0] > 0 and abs(rates[1] / rates[0] - desert.WELL_HEAT_MULT) < 0.03,
          f'heat after 3 s: {rates[0]:.2f} -> {rates[1]:.2f}')

    # journal places page
    a.toggle_panel('journal')
    a.set_journal_page('places')
    rows, _r = a.atlas_lines()
    unknown = sum(w.count('?') for _t, _c, w in rows)
    known = len(a.found_kinds)
    words = [n.node().getText() for n in a.panel.findAllMatches('**/+TextNode')]
    check('the journal\'s places page lists every kind, "?" for the ones not found',
          unknown + known == len(places.catalogue_kinds()) and any('stories heard' in w for w in words),
          f'{known} known, {unknown} unknown')
    a.set_journal_page('journal')
    a.close_panel()

    # save and load
    snap = a.places_snapshot()
    kinds_before, rum_before = set(a.found_kinds), {k: list(v) for k, v in a.rumours.items()}
    a.found_kinds = set()
    a.rumours = {}
    a.apply_places(snap)
    old = dict(snap)
    old.pop('kinds')
    old['rumours'] = {k: list(v[0]) for k, v in snap['rumours'].items()}   # the single-point form
    a.found_kinds = set()
    a.apply_places(old)
    derived = set(a.found_kinds)
    check('kinds known and stories heard are saved (and rebuilt for older saves)',
          derived >= kinds_before - {'lanterns'} and set(a.rumours) == set(rum_before), f'{sorted(derived)}')

    print('RESULT', 'PASS' if not FAILS else 'FAIL', FAILS)
    os._exit(0 if not FAILS else 1)


if __name__ == '__main__':
    main()
