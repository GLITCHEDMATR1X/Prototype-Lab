# Operation StarFall Flight Drone Power / Docking Standard v0.1

Pass49 rule: flight drones are not unlimited free cameras.

## Required behavior

- Surface operations still use the existing support rover / land drone as the controlled anchor.
- Drone A and Drone B are flight drones.
- Flight drones have finite power.
- Flight drones have per-drone altitude limits measured above local terrain.
- Flight drones drain power while remote-piloted or performing tasks.
- Idle flight drones automatically return to the existing rover and attach to recharge.
- The rover is the charging anchor; do not spawn a new charge vehicle.
- If a drone reaches critical power, it disables and must be rescued through the existing click/pull rescue system.
- Drone stats belong in the bottom-left HUD area.

## Default limits

- Drone A maximum altitude: 230 m above terrain.
- Drone B maximum altitude: 205 m above terrain.
- Power maximum: 100%.
- Low power warning: 34%.
- Critical disable: 4%.

## HUD requirement

Bottom-left HUD must show:

```text
FLIGHT DRONES
F-A PWR ###% ALT ###/###m AIR/DOCK STATE
F-B PWR ###% ALT ###/###m AIR/DOCK STATE
ROVER DOCK ####/####
```

## Acceptance

Reject future passes if:

- Drone altitude is unlimited.
- Drone power is UI-only and does not drain/recharge.
- Idle drones hover forever instead of auto-docking.
- A new fake land drone or charge vehicle is spawned instead of using the existing rover.
- Drone stats are hidden in a debug panel only.
