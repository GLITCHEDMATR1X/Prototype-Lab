# Operation StarFall Reference Display Standard v0.3

## Purpose
Operation StarFall uses **1920x1080 as the primary render and UI reference surface**. The game no longer treats 1600x900 or a near-desktop arbitrary window as the normal startup authority.

## Normal startup
- Default mode: `reference_1080p_window`.
- On desktops whose work area can hold a decorated 1920x1080 client, open a centered decorated/resizable 1920x1080 window.
- On a 1920x1080-class desktop where the taskbar/window decorations would force the client below 1080p, use an exact borderless 1920x1080 client instead.
- When the physical desktop is smaller than 1920x1080, scale the same 16:9 reference surface down.
- A 1280x720 desktop remains exactly 1280x720; do not shrink below the documented minimum merely to preserve decorations.

## Explicit alternate modes
- `--reference-window` / `--1080p`: normal reference authority.
- `--desktop-window`: legacy desktop-fit decorated/resizable behavior.
- `--large-window`: bordered 1920x1080 best fit.
- `--bordered-window`: bordered 1600x900.
- `--safe-window`: bordered 1440x810.
- `--windowed`: 1280x720.
- `--windowed-fullscreen`: borderless native desktop.
- `--fullscreen`: native-resolution exclusive fullscreen, opt-in only.

## HUD and DPI
HUD remains aspect-safe and reflows after window events. DPI awareness stays enabled. Normal QA captures use 1920x1080 first; 1280x720 is the minimum-resolution regression.

## Reject future display work if
- Normal startup silently falls back to 1600x900 on a 1080p-capable desktop.
- A 1920x1080 desktop produces a smaller client solely because of taskbar/decorations.
- A 1280x720 desktop is forced below 1280x720.
- Existing explicit display presets stop working.
- UI overlaps or clips after either 1080p or 720p rendering.
