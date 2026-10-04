# Operation StarFall — Windows Settings / Optimization Standard v0.2

## Window rules
- Default launch uses a decorated, movable, resizable desktop-fit window.
- The default client frame is calculated from the actual Windows monitor/work area.
- Windows DPI awareness and DPI-driven window resize handling stay enabled.
- Decorated presets are resizable and keep normal minimize/maximize/restore controls.
- Borderless mode uses the native desktop pixel dimensions instead of fixed 1920x1080.
- Exclusive fullscreen is opt-in only.
- `window-event` reflows the shared HUD layout after size changes.

## Settings authority
Portable settings live at `settings/starfall_user_settings.json`. Shell and worlds read the same display preset. The legacy fixed `borderless_1920x1080` default migrates to `desktop_resizable`.

## Performance profiles
PERFORMANCE, BALANCED, and PRESENTATION remain shared by all worlds.

## Rejection conditions
- Default launch is fixed-size or undecorated.
- A 4K display is limited to a 1920x1080 default window.
- Decorated windows disable resize/maximize behavior.
- Borderless ignores native desktop size.
- A resize breaks HUD layout or mouse centering.
