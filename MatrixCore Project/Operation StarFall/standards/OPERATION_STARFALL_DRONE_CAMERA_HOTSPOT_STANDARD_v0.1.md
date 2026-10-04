# Operation StarFall Drone Camera / Hotspot Authority v0.1

Pass51 standardizes camera ownership for the remote surface units.

## Unit camera rules

- The **hover drone** is the existing Drone A / drill drone body.
- The hover camera is a belly-mounted view below the drone body, not a third-person chase view.
- The hover camera may tilt directly down to inspect ground/hotspots without rendering the drone shell in front of the operator.
- The **land rover** remains the existing support rover / land drone body.
- The land rover camera is mounted on top of the rover, uses slow terrain traversal, and stays in the mission zone.
- No replacement drone/rover entities are created by this camera pass.

## Action rules

- LMB from hover-drone view on a locked hotspot routes the existing Drone A to that hotspot.
- Drone A autopilot owns movement while drilling dispatch is active; manual flight does not fight the drill route.
- LMB on held cargo still collects cargo when the cargo is in view.
- Disabled drone rescue remains LMB target/cable based.

## Overlay rules

- Hover-drone static uses cyan/blue signal noise.
- Land-rover signal overlay uses warmer amber/orange filtering.
- Bottom-left unit telemetry must report the active camera mount, rover speed/link, drone power, altitude, dock state, and task state.

## Test rules

Required tests:

```bash
python -B Worlds/main.py --drone-camera-hotspot-test --no-audio
python -B Worlds/main.py --remote-rover-drone-contract-test --no-audio
python -B Worlds/main.py --flight-drone-power-contract-test --no-audio
python -B Worlds/main.py --mission-signal-rescue-contract-test --no-audio
```

Required screenshot proofs:

```bash
python Worlds/main.py --moon=mimas --test-shot verification/screenshots/opstar51_hover_drone_belly_cam_mimas.png --hover-drone-camera-shot --no-audio
python Worlds/main.py --moon=mimas --test-shot verification/screenshots/opstar51_land_rover_top_cam_mimas.png --land-rover-camera-shot --no-audio
```
