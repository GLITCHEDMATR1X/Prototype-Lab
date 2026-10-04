# Operation StarFall Pass97 — Responsive Display Window Authority

Base: Pass96 Full Function Sweep / Runtime Repair.

## Repair
The shipped Pass96 settings selected a fixed 1920x1080 display surface and the shared display authority locked preset windows with `win-fixed-size #t`. On a 4K desktop this produced a half-width/half-height game window with no usable resize/maximize behavior.

Pass97 changes normal startup to `desktop_resizable_window`: decorated, movable, resizable, DPI-aware, and sized from the current desktop/work area. The legacy `borderless_1920x1080` saved default migrates to the new desktop-resizable mode. Borderless remains optional and now uses native desktop dimensions.

All decorated presets are resizable. `window-event` continues to reflow the world HUD layout.

## Runtime proof
4K simulated desktop:
- initial window: 3792x2072, decorated, fixed_size=false, fullscreen=false
- requested resize: 1600x900 accepted
- borderless: 3840x2160 at origin 0,0

## Regression
Display, Windows optimization, screen layout, all-world screen, transport, planet vision, atmospheric FX, Jupiter full-wrap, and Jupiter spatial authority contracts pass.

Embedded Europa was also launched after a runtime resize to 1600x900. The same window stayed 1600x900, decorated, and resizable inside the world and after TAB-style return to the shell.
