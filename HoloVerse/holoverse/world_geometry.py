"""Authoritative HoloVerse surface-ring geometry.

Pass 282.25 keeps the already-accepted 310-unit central FLAT/main area, then
halves the radial width of every finite outer biome ring.  This applies the
same traversal rule used for the accepted FLAT/main-area reduction: each region
takes about half as much radial distance to cross.  Metropolis begins immediately
after Urban and keeps a 1,000-unit reference/arrival band, but its procedural city
is intentionally unbounded beyond that reference band.

This module is intentionally pure data/math: it imports no Panda3D runtime.
"""
from __future__ import annotations

from copy import deepcopy

MAIN_AREA_PREVIOUS_RADIUS = 620.0
MAIN_AREA_RADIUS = 310.0
WORLD_INWARD_SHIFT = MAIN_AREA_PREVIOUS_RADIUS - MAIN_AREA_RADIUS
SURFACE_INNER_RADIUS = 30.0
OUTER_RING_WIDTH_SCALE = 0.50

# Pass 282.25 follows the traversal rule requested for the accepted main-area
# reduction: halve each finite 282.24 ring's radial width, while leaving the
# already-accepted 30..310 FLAT/main area unchanged.  The previous boundary list
# was 310, 1610, 2990, 4390, 5790, 7190, 8790, 10790.
_PREVIOUS_BOUNDARY_RADII = {
    1: 310.0,
    2: 1610.0,
    3: 2990.0,
    4: 4390.0,
    5: 5790.0,
    6: 7190.0,
    7: 8790.0,
    8: 10790.0,
}

def _half_previous_width(inner_key: int, outer_key: int) -> float:
    return (_PREVIOUS_BOUNDARY_RADII[outer_key] - _PREVIOUS_BOUNDARY_RADII[inner_key]) * OUTER_RING_WIDTH_SCALE

FOREST_INNER_RADIUS = MAIN_AREA_RADIUS
FOREST_OUTER_RADIUS = FOREST_INNER_RADIUS + _half_previous_width(1, 2)
HILLS_INNER_RADIUS = FOREST_OUTER_RADIUS
HILLS_OUTER_RADIUS = HILLS_INNER_RADIUS + _half_previous_width(2, 3)
MUSHROOM_INNER_RADIUS = HILLS_OUTER_RADIUS
MUSHROOM_OUTER_RADIUS = MUSHROOM_INNER_RADIUS + _half_previous_width(3, 4)
DESERT_INNER_RADIUS = MUSHROOM_OUTER_RADIUS
DESERT_OUTER_RADIUS = DESERT_INNER_RADIUS + _half_previous_width(4, 5)
ICE_INNER_RADIUS = DESERT_OUTER_RADIUS
ICE_OUTER_RADIUS = ICE_INNER_RADIUS + _half_previous_width(5, 6)
URBAN_INNER_RADIUS = ICE_OUTER_RADIUS
URBAN_OUTER_RADIUS = URBAN_INNER_RADIUS + _half_previous_width(6, 7)
METROPOLIS_INNER_RADIUS = URBAN_OUTER_RADIUS
METROPOLIS_REFERENCE_WIDTH = (_PREVIOUS_BOUNDARY_RADII[8] - _PREVIOUS_BOUNDARY_RADII[7]) * OUTER_RING_WIDTH_SCALE
METROPOLIS_REFERENCE_OUTER_RADIUS = METROPOLIS_INNER_RADIUS + METROPOLIS_REFERENCE_WIDTH
METROPOLIS_INFINITE = True

SURFACE_REGION_RINGS = (
    {"key": 1, "name": "FLAT", "label": "FLAT", "r0": 30.0, "r1": MAIN_AREA_RADIUS, "kind": "flat", "height": 0.0, "hue": 0.08, "color": (0.78, 0.82, 0.86, 0.34)},
    {"key": 2, "name": "FORESTS", "label": "FORESTS", "r0": FOREST_INNER_RADIUS, "r1": FOREST_OUTER_RADIUS, "kind": "forest", "height": 4.8, "hue": 0.32, "color": (0.18, 0.95, 0.30, 0.30)},
    {"key": 3, "name": "GREEN HILLS", "label": "GREEN HILLS", "r0": HILLS_INNER_RADIUS, "r1": HILLS_OUTER_RADIUS, "kind": "hills", "height": 13.8, "hue": 0.24, "color": (0.48, 1.00, 0.18, 0.38)},
    {"key": 4, "name": "MUSHROOM", "label": "MUSHROOM", "r0": MUSHROOM_INNER_RADIUS, "r1": MUSHROOM_OUTER_RADIUS, "kind": "mushroom", "height": 12.4, "hue": 0.88, "color": (1.00, 0.22, 0.82, 0.32)},
    {"key": 5, "name": "DESERT", "label": "DESERT", "r0": DESERT_INNER_RADIUS, "r1": DESERT_OUTER_RADIUS, "kind": "desert", "height": 7.4, "hue": 0.12, "color": (1.00, 0.62, 0.22, 0.30)},
    {"key": 6, "name": "ICE", "label": "ICE", "r0": ICE_INNER_RADIUS, "r1": ICE_OUTER_RADIUS, "kind": "ice", "height": 10.8, "hue": 0.60, "color": (0.66, 0.92, 1.00, 0.32)},
    {"key": 7, "name": "URBAN", "label": "URBAN", "r0": URBAN_INNER_RADIUS, "r1": URBAN_OUTER_RADIUS, "kind": "urban", "height": 4.9, "hue": 0.68, "color": (0.115, 0.122, 0.138, 0.58)},
    {"key": 8, "name": "METROPOLIS", "label": "METROPOLIS", "r0": METROPOLIS_INNER_RADIUS, "r1": METROPOLIS_REFERENCE_OUTER_RADIUS, "kind": "metropolis", "height": 2.6, "hue": 0.76, "color": (0.72, 0.44, 1.00, 0.30), "infinite": True, "reference_width": METROPOLIS_REFERENCE_WIDTH},
)
# Presentation/reference radius only.  Metropolis streaming continues beyond it.
SURFACE_OUTER_RADIUS = float(METROPOLIS_REFERENCE_OUTER_RADIUS)
SURFACE_FINITE_OUTER_RADIUS = float(URBAN_OUTER_RADIUS)

# Hub handoff markers remain normalized inside the already-accepted compact FLAT.
_OLD_HANDOFF_RADII = (92.0, 180.0, 320.0, 620.0)

def remap_main_radius(old_radius: float) -> float:
    old_span = MAIN_AREA_PREVIOUS_RADIUS - SURFACE_INNER_RADIUS
    new_span = MAIN_AREA_RADIUS - SURFACE_INNER_RADIUS
    t = (float(old_radius) - SURFACE_INNER_RADIUS) / old_span
    return SURFACE_INNER_RADIUS + max(0.0, min(1.0, t)) * new_span

MAIN_AREA_HANDOFF_RADII = tuple(round(remap_main_radius(value), 6) for value in _OLD_HANDOFF_RADII)

# HoloSpace is a separate mode, not the outer edge of the infinite city.  Keep
# its accepted relative offsets from the former surface-reference edge.
_PREVIOUS_SURFACE_REFERENCE_OUTER = 10790.0
_PREVIOUS_HOLOSPACE_VIEW_RADIUS = 11110.0
_PREVIOUS_HOLOSPACE_FOCUS_RADIUS = 12170.0
_PREVIOUS_HOLOSPACE_BOT_RADIUS = 12010.0
HOLOSPACE_ENTRY_RADIUS = SURFACE_OUTER_RADIUS
HOLOSPACE_VIEW_RADIUS = SURFACE_OUTER_RADIUS + (_PREVIOUS_HOLOSPACE_VIEW_RADIUS - _PREVIOUS_SURFACE_REFERENCE_OUTER)
HOLOSPACE_FOCUS_Y = -(SURFACE_OUTER_RADIUS + (_PREVIOUS_HOLOSPACE_FOCUS_RADIUS - _PREVIOUS_SURFACE_REFERENCE_OUTER))
HOLOSPACE_BOT_Y = -(SURFACE_OUTER_RADIUS + (_PREVIOUS_HOLOSPACE_BOT_RADIUS - _PREVIOUS_SURFACE_REFERENCE_OUTER))


def surface_ring_for_key(key: int):
    try:
        key = int(key)
    except Exception:
        return None
    for ring in SURFACE_REGION_RINGS:
        if int(ring["key"]) == key:
            return deepcopy(ring)
    return None


def surface_rings():
    return [deepcopy(ring) for ring in SURFACE_REGION_RINGS]


def metropolis_radius_is_unbounded(radius: float) -> bool:
    return bool(METROPOLIS_INFINITE and float(radius) >= float(METROPOLIS_INNER_RADIUS))


def shifted_outer_radius(old_radius: float) -> float:
    """Legacy compatibility helper from Pass 282.22."""
    return float(old_radius) - WORLD_INWARD_SHIFT


# Preserve the accepted guide normalized position inside each compressed ring,
# while preserving the old absolute guide-to-landing stand-off so artifacts and
# guide interactions do not suddenly overlap.
def _ring_radius(r0: float, r1: float, t: float) -> float:
    return float(r0) + (float(r1) - float(r0)) * float(t)

_FLAT_SPAN = MAIN_AREA_RADIUS - SURFACE_INNER_RADIUS
_FLAT_GUIDE_RADIUS = min(MAIN_AREA_RADIUS - 48.0, max(132.0, SURFACE_INNER_RADIUS + _FLAT_SPAN * 0.48))
_HUB_APPROACH_CLEARANCE_FROM_IO = 325.0 - (30.0 + (620.0 - 30.0) * 0.48)
HUB_APPROACH_RADIUS = round(_FLAT_GUIDE_RADIUS + _HUB_APPROACH_CLEARANCE_FROM_IO, 6)

REGION_TRAVEL_SPECS = (
    {"number": 0, "ring_key": 1, "name": "Hub Region", "r0": 0.0, "r1": MAIN_AREA_RADIUS, "radius": HUB_APPROACH_RADIUS, "landing_radius": HUB_APPROACH_RADIUS, "landing_angle_deg": -90.0, "height": 0.0, "yaw": 180.0, "arrival_label": "Hub Approach"},
    {"number": 1, "ring_key": 2, "name": "Forests", "r0": FOREST_INNER_RADIUS, "r1": FOREST_OUTER_RADIUS, "radius": _ring_radius(FOREST_INNER_RADIUS, FOREST_OUTER_RADIUS, 0.30), "landing_radius": _ring_radius(FOREST_INNER_RADIUS, FOREST_OUTER_RADIUS, 0.30) - 48.0, "landing_angle_deg": -90.0, "height": 4.8, "yaw": 180.0, "guide": "Vanta", "arrival_label": "Vanta Grove Approach"},
    {"number": 2, "ring_key": 3, "name": "Green Hills", "r0": HILLS_INNER_RADIUS, "r1": HILLS_OUTER_RADIUS, "radius": _ring_radius(HILLS_INNER_RADIUS, HILLS_OUTER_RADIUS, 0.38), "landing_radius": _ring_radius(HILLS_INNER_RADIUS, HILLS_OUTER_RADIUS, 0.38) - 54.4, "landing_angle_deg": -90.0, "height": 13.8, "yaw": 180.0, "guide": "Nyx", "arrival_label": "Nyx Hillside Approach"},
    {"number": 3, "ring_key": 4, "name": "Mushroom", "r0": MUSHROOM_INNER_RADIUS, "r1": MUSHROOM_OUTER_RADIUS, "radius": _ring_radius(MUSHROOM_INNER_RADIUS, MUSHROOM_OUTER_RADIUS, 0.46), "landing_radius": _ring_radius(MUSHROOM_INNER_RADIUS, MUSHROOM_OUTER_RADIUS, 0.46) - 54.0, "landing_angle_deg": -90.0, "height": 14.2, "yaw": 180.0, "guide": "Solace", "arrival_label": "Solace Sporefield Approach"},
    {"number": 4, "ring_key": 5, "name": "Desert", "r0": DESERT_INNER_RADIUS, "r1": DESERT_OUTER_RADIUS, "radius": _ring_radius(DESERT_INNER_RADIUS, DESERT_OUTER_RADIUS, 0.54), "landing_radius": _ring_radius(DESERT_INNER_RADIUS, DESERT_OUTER_RADIUS, 0.54) - 56.0, "landing_angle_deg": -90.0, "height": 7.4, "yaw": 180.0, "guide": "Ember", "arrival_label": "Ember Hangar Approach"},
    {"number": 5, "ring_key": 6, "name": "Ice", "r0": ICE_INNER_RADIUS, "r1": ICE_OUTER_RADIUS, "radius": _ring_radius(ICE_INNER_RADIUS, ICE_OUTER_RADIUS, 0.62), "landing_radius": _ring_radius(ICE_INNER_RADIUS, ICE_OUTER_RADIUS, 0.62) - 56.0, "landing_angle_deg": -90.0, "height": 10.8, "yaw": 180.0, "guide": "Mirror", "arrival_label": "Mirror Circuit Approach"},
    {"number": 6, "ring_key": 7, "name": "Urban", "r0": URBAN_INNER_RADIUS, "r1": URBAN_OUTER_RADIUS, "radius": _ring_radius(URBAN_INNER_RADIUS, URBAN_OUTER_RADIUS, 0.70), "landing_radius": _ring_radius(URBAN_INNER_RADIUS, URBAN_OUTER_RADIUS, 0.70) - 65.0, "landing_angle_deg": -90.0, "height": 4.9, "yaw": 180.0, "guide": "Sable", "arrival_label": "Sable Warzone Perimeter"},
    {"number": 7, "ring_key": 8, "name": "Metropolis", "r0": METROPOLIS_INNER_RADIUS, "r1": METROPOLIS_REFERENCE_OUTER_RADIUS, "radius": _ring_radius(METROPOLIS_INNER_RADIUS, METROPOLIS_REFERENCE_OUTER_RADIUS, 0.50), "landing_radius": _ring_radius(METROPOLIS_INNER_RADIUS, METROPOLIS_REFERENCE_OUTER_RADIUS, 0.50) - 300.0, "landing_angle_deg": -90.0, "height": 2.6, "yaw": 180.0, "guide": "Archivist", "arrival_label": "Archivist District Approach", "infinite": True},
    {"number": 8, "ring_key": None, "name": "HoloSpace", "r0": HOLOSPACE_ENTRY_RADIUS, "r1": 999999.0, "radius": HOLOSPACE_VIEW_RADIUS, "height": 1096.0, "yaw": -90.0, "holospace": True, "dyson_focus": [0.0, HOLOSPACE_FOCUS_Y, 1185.0], "guide": "Orbit", "arrival_label": "Dyson Reach"},
    {"number": 9, "ring_key": 1, "name": "Hub Spawn", "r0": 0.0, "r1": 120.0, "radius": 0.0, "landing_radius": 0.0, "landing_angle_deg": 0.0, "height": 0.0, "yaw": 0.0, "hub_spawn": True, "arrival_label": "MatrixCore Home"},
)


def region_travel_specs():
    return [deepcopy(entry) for entry in REGION_TRAVEL_SPECS]


def region_travel_for_number(number: int):
    try:
        number = int(number)
    except Exception:
        return None
    for entry in REGION_TRAVEL_SPECS:
        if int(entry["number"]) == number:
            return deepcopy(entry)
    return None
