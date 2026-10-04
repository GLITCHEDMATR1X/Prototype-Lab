from __future__ import annotations

from dataclasses import dataclass

DEFAULT_WINDOW_SIZE = (1280, 720)


@dataclass(frozen=True)
class PresentationRect:
    width: int
    height: int
    x: int
    y: int
    scale: float
    integer_scale: bool


def choose_desktop_size(desktop_sizes, display_index: int, fallback=(1920, 1080)) -> tuple[int, int]:
    """Return a sane current-desktop size without requesting a monitor mode change."""
    cleaned = []
    for size in desktop_sizes or ():
        try:
            w, h = int(size[0]), int(size[1])
        except (TypeError, ValueError, IndexError):
            continue
        if w >= 640 and h >= 360:
            cleaned.append((w, h))
    if not cleaned:
        fw, fh = int(fallback[0]), int(fallback[1])
        return (max(640, fw), max(360, fh))
    index = max(0, min(int(display_index), len(cleaned) - 1))
    return cleaned[index]


def fit_virtual_canvas(window_size, virtual_size) -> PresentationRect:
    """Aspect-fit the native canvas inside any desktop without stretching it."""
    ww, wh = max(1, int(window_size[0])), max(1, int(window_size[1]))
    vw, vh = max(1, int(virtual_size[0])), max(1, int(virtual_size[1]))
    scale = min(ww / vw, wh / vh)
    width = max(1, min(ww, int(round(vw * scale))))
    height = max(1, min(wh, int(round(vh * scale))))
    x = (ww - width) // 2
    y = (wh - height) // 2
    nearest = round(scale)
    integer_scale = nearest >= 1 and abs(scale - nearest) < 1e-9
    return PresentationRect(width, height, x, y, scale, integer_scale)
