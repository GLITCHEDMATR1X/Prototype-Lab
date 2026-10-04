"""HoloCore line kit (Pass HC-1).

Small helpers for HoloCore's line-drawn strata assets
(``assets/strata/<band>/*.py``), in the same neon line style as the seabed
flora.  Line widths follow the window height so lines keep the same apparent
weight at 1080p and 4K (1.0x at 1080 rows, 2.0x at 2160 rows).
"""
from __future__ import annotations

import math

from panda3d.core import ColorBlendAttrib, LineSegs, NodePath, TransparencyAttrib

REFERENCE_ROWS = 1080.0
MAX_LINE_SCALE = 2.2

_line_scale_cache: float | None = None


def line_scale() -> float:
    """Line width multiplier for the current window (1.0 at 1080p, 2.0 at 4K)."""
    global _line_scale_cache
    if _line_scale_cache is not None:
        return _line_scale_cache
    scale = 1.0
    try:
        import builtins

        app = getattr(builtins, "base", None)
        win = getattr(app, "win", None)
        if win is not None:
            rows = float(win.getYSize() or 0)
            if rows <= 0 and hasattr(win, "getProperties"):
                rows = float(win.getProperties().getYSize() or 0)
            if rows > 0:
                scale = max(1.0, min(MAX_LINE_SCALE, rows / REFERENCE_ROWS))
                _line_scale_cache = scale
    except Exception:
        scale = 1.0
    return scale


def new_lines(name: str, thickness: float = 1.2) -> LineSegs:
    ls = LineSegs(name)
    ls.setThickness(float(thickness) * line_scale())
    return ls


def polyline(ls: LineSegs, pts, color) -> None:
    ls.setColor(*color)
    for i, p in enumerate(pts):
        (ls.moveTo if i == 0 else ls.drawTo)(*p)


def ring(ls: LineSegs, cx, cy, cz, rx, ry, color, segs=24, plane="xy") -> None:
    pts = []
    for k in range(segs + 1):
        a = math.tau * k / segs
        if plane == "xy":
            pts.append((cx + math.cos(a) * rx, cy + math.sin(a) * ry, cz))
        elif plane == "xz":
            pts.append((cx + math.cos(a) * rx, cy, cz + math.sin(a) * ry))
        else:
            pts.append((cx, cy + math.cos(a) * rx, cz + math.sin(a) * ry))
    polyline(ls, pts, color)


def wire_sphere(ls: LineSegs, cx, cy, cz, r, color, lat=5, lon=8, segs=18) -> None:
    for i in range(1, lat):
        phi = math.pi * i / lat
        ring(ls, cx, cy, cz + math.cos(phi) * r, math.sin(phi) * r, math.sin(phi) * r, color, segs)
    for j in range(lon):
        th = math.tau * j / lon
        pts = [(cx + math.sin(math.pi * k / segs) * r * math.cos(th),
                cy + math.sin(math.pi * k / segs) * r * math.sin(th),
                cz + math.cos(math.pi * k / segs) * r) for k in range(segs + 1)]
        polyline(ls, pts, color)


def finish(parent: NodePath, name: str, layers, x, y, z, additive=True) -> NodePath:
    """Attach finished LineSegs under one node, flatten them into few draws, place it."""
    root = parent.attachNewNode(name)
    for ls in layers:
        root.attachNewNode(ls.create())
    root.flattenStrong()
    root.setPos(x, y, z)
    root.setLightOff()
    root.setTransparency(TransparencyAttrib.MAlpha)
    root.setDepthWrite(False)
    root.setBin("transparent", 11)
    if additive:
        root.setAttrib(ColorBlendAttrib.make(ColorBlendAttrib.MAdd, ColorBlendAttrib.OIncomingAlpha, ColorBlendAttrib.OOne))
    return root


__all__ = ["finish", "line_scale", "new_lines", "polyline", "ring", "wire_sphere"]
