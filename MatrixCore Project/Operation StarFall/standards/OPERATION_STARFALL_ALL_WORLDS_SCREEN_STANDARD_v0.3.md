# Operation StarFall All-World Screen Standard v0.4

## Active worlds covered
Mimas, Enceladus, Iapetus, Titan, Mars, Pluto, Europa, and Triton.

## Core rule
All active worlds use one responsive display authority and one aspect-safe HUD layout. No world may force its own window size, decoration mode, or independent HUD scale.

## Window rules
- Default: decorated desktop-fit window with normal Windows title bar and resize/maximize controls.
- `--large-window`: 1920x1080 starting size, decorated and resizable.
- `--bordered-window`: 1600x900 starting size, decorated and resizable.
- `--safe-window`: 1440x810 starting size, decorated and resizable.
- `--windowed`: 1280x720 starting size, decorated and resizable.
- `--windowed-fullscreen`: borderless at the native desktop pixel dimensions.
- `--fullscreen`: native-resolution exclusive fullscreen, opt-in only.
- DPI-aware resizing stays enabled.

## HUD ownership
`Worlds/main.py` owns the moon-operation HUD for every world. Minimal HUD is default; H cycles MINIMAL -> COMPACT -> FULL -> HIDDEN. Window resize events must re-run the shared layout pass.

## Reject future passes if
- a world adds a separate window authority
- normal launch is fixed-size or undecorated
- a 4K desktop opens a fixed 1920x1080 borderless window by default
- resizing causes HUD overlap or off-screen controls
