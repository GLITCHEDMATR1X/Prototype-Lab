from __future__ import annotations

from collections.abc import Iterable

import pygame


def glow_line(
    glow_surface: pygame.Surface,
    final_surface: pygame.Surface,
    color: pygame.Color | tuple[int, int, int],
    points: Iterable[tuple[int, int]],
    width: int = 2,
    closed: bool = False,
) -> None:
    pts = list(points)
    if len(pts) < 2:
        return
    rgb = pygame.Color(color)
    for extra, alpha in ((12, 18), (7, 28), (3, 44)):
        pygame.draw.lines(glow_surface, (*rgb[:3], alpha), closed, pts, width + extra)
    pygame.draw.lines(final_surface, rgb, closed, pts, width)


def glow_circle(
    glow_surface: pygame.Surface,
    final_surface: pygame.Surface,
    color: pygame.Color | tuple[int, int, int],
    center: tuple[int, int],
    radius: int,
    width: int = 2,
) -> None:
    rgb = pygame.Color(color)
    pygame.draw.circle(glow_surface, (*rgb[:3], 22), center, radius + 13, width + 10)
    pygame.draw.circle(glow_surface, (*rgb[:3], 42), center, radius + 6, width + 5)
    pygame.draw.circle(final_surface, rgb, center, radius, width)
