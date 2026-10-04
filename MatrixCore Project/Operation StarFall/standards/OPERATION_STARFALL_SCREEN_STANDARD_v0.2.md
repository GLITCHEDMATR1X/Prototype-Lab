# Operation StarFall Responsive Screen Standard v0.3

## Purpose
Operation StarFall uses one responsive window authority. The normal Windows launch is a decorated, movable, resizable desktop-fit window. HUD layout stays aspect-safe while the OS window is restored, resized, moved, or maximized.

## Window modes
- Default: `desktop_resizable_window`; near-desktop fit with normal Windows title bar and resize/maximize controls.
- `--large-window`: 1920x1080 starting client size, decorated and resizable.
- `--bordered-window`: 1600x900 starting client size, decorated and resizable.
- `--safe-window`: 1440x810 starting client size, decorated and resizable.
- `--windowed`: 1280x720 starting client size, decorated and resizable.
- `--windowed-fullscreen`: borderless window using the native desktop pixel size, not fixed 1920x1080.
- `--fullscreen`: native-resolution exclusive fullscreen, opt-in only.

## DPI rule
Windows launch is DPI-aware and allows DPI-driven window resize updates. Desktop sizing must use the actual monitor/work-area dimensions rather than assuming 1920x1080.

## HUD ownership
- Minimal HUD is default.
- H cycles HUD: minimal -> compact -> full -> hidden.
- F1 opens help.
- ESC/P opens options/menu.
- The universal top access strip appears only in Full HUD.
- Normal play should show only objective, sonar, crosshair, and a short resource/movement line.

## Reflow rule
`window-event` must re-run the screen layout pass. No UI element should rely on stale positions after a resize or display-mode change.

## Reject future screen work if
- Normal launch is undecorated or fixed-size.
- A 4K desktop opens a fixed 1920x1080 borderless window by default.
- Decorated modes disable resize/maximize controls.
- Borderless mode ignores native desktop dimensions.
- UI overlaps after a resize.
