# Operation StarFall Remote Rover / Drone Control Standard v0.1

## Phase
Mastering / immersion restriction foundation.

## Rule
Moon operations are no longer controlled by a loose invisible walking entity.
The surface control body is the existing support refinery rover already present in the world.
Do not add a replacement rover or duplicate player body.

## Active control bodies

| Mode | Binding | Rule |
|---|---|---|
| ROVER | default / Ctrl+Alt fallback | WASD drives existing land rover body; camera follows from the rover. |
| DRONE_A | Left Alt / Alt | Switches to existing drill drone POV/control; pressing again returns to rover. |
| DRONE_B | Right Alt | Switches to rescue relay drone POV/control; pressing again returns to rover. |

## Mission-zone restriction
- Each moon operation owns a mission-zone center and radius.
- Leaving the core zone increases transparent signal-static overlay.
- Drones that travel beyond the hard disable radius lose signal and become disabled.
- Rover does not disable; it is the recovery body.

## Drone disable / rescue rule
- If the active drone is disabled, control automatically switches to the other active drone or the rover.
- Disabled drones remain visible in the world.
- Aim at a disabled drone and press LMB to attach a rescue cable.
- The disabled drone is pulled toward the active control body until it is rescued.

## Visual/UI rule
- HUD must show active view/control mode.
- Static overlay must remain translucent and not hide gameplay.
- No new full-screen UI layer may override the standard HUD cycle.

## Anti-regression
- TAB still returns to StarFall shell.
- ESC/F1/H behavior remains from Pass46.
- Pass39 screen canvas, Pass41 audio authority, Pass42 progress, Pass43 action contract, Pass44 generation, and Pass45 Windows settings remain valid.
