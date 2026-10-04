# Operation StarFall Shell / Saturn Map / Interior UI Standard v0.1

## Purpose

Pass46 places the StarFall shell under the same mastering rules as the moon worlds. The ship interior, pause menu, Saturn operations map, help panel, and shell HUD must behave like one interface family rather than separate screens with different assumptions.

## Contract

`operation_starfall_shell_ui_v0.1`

## Ownership rules

- Shell HUD belongs to the ship shell only.
- Saturn map owns destination selection and launch.
- Pause menu owns resume/map/help/flight/quit.
- Help panel owns controls/reference text.
- Moon worlds own their own runtime HUD while embedded.
- Panel screens suppress the normal shell HUD while open.
- No panel may expose stale pass labels or debug text.

## HUD levels

The shell uses the same H-cycle standard as the moon worlds:

```text
MINIMAL -> COMPACT -> FULL -> HIDDEN
```

Default is `MINIMAL`.

## 16:9 safe canvas

All panel roots must fit inside the established StarFall safe UI canvas:

```text
left -1.34
right 1.34
top 0.965
bottom -0.965
```

The map and menus may use a dimmed ship interior behind them, but their own text/buttons must remain readable at 1280x720, 1600x900, and 1920x1080.

## Saturn map text rules

- Node labels stay short.
- Details live in the right panel.
- Target detail is limited to target/status/loop/resources/tip.
- No long facts wall during normal map use.
- Launch button only launches a READY target.
- Planned targets are visible but must not pretend to be playable.

## Interior rules

- Interior LMB opens the Saturn Ops Map.
- `M` opens the same map.
- `ESC` opens the shell pause menu or closes the current panel.
- `F1` opens shell help.
- `TAB` cycles operation stations only in the shell, not inside embedded moon worlds.

## Reject conditions

Reject a pass if:

- `STARFALL // P##` or other stale pass label appears in normal HUD.
- Map, pause, or help panels show normal HUD text behind them.
- Map detail exceeds the concise panel standard.
- A moon world opens from a random cockpit click without the map owning the launch.
- The shell uses a different screen-size rule than the active moon worlds.
