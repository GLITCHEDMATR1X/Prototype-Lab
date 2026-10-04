# Operation StarFall — Mission Signal / Rescue Standard v0.1

## Purpose

Pass48 converts the remote rover/drone restriction from a loose overlay into a real field-operations rule.

The player does not hit invisible walls. The mission zone is enforced through signal quality, static, audio crackle, control degradation, disabled drone states, rescue beacons, and line-of-sight recovery pulls.

## Active control bodies

- Rover: existing `support_refinery_rover` body only. Do not spawn a replacement rover.
- Drone A: existing drill/survey drone.
- Drone B: rescue/tow relay drone.

## Signal-zone rules

- Mission-zone center is created from the rover deployment position.
- Warning radius: `MISSION_ZONE_WARNING_RADIUS`.
- Hard disable radius: `MISSION_ZONE_HARD_RADIUS`.
- A visible warning ring and hard ring should exist in-world.
- Signal degradation begins before the hard edge.
- Rover and drone movement should degrade with signal quality.
- A transparent static overlay and occasional crackle cue should warn the player.

## Disabled-drone rules

- Drones can be disabled by mission-zone signal loss.
- A disabled drone must not be controllable.
- If the active drone disables, control falls back to the other active drone or rover.
- A disabled drone must show a visible rescue beacon.

## Rescue rules

- LMB can lock a rescue cable when the crosshair is on a disabled drone.
- Rescue uses screen-space/camera picking to avoid blind distance guessing.
- Rescue pull strength depends on distance and signal quality.
- Rescue requires a simple terrain line-of-sight check.
- If the cable is blocked, the player must move the rover or active drone.
- When the disabled drone gets close enough, it reactivates and Alt POV becomes available again.

## Audio/FX rules

Required cues:

- `signal_static.wav`
- `drone_disabled.wav`
- `rescue_pull.wav`
- `rescue_complete.wav`

These must respect `--no-audio` and headless/test silence rules.

## Validation

Required checks:

- `--mission-signal-rescue-contract-test`
- `--remote-rover-drone-contract-test`
- `--world-action-contract-test`
- all mastering contracts already established through Pass47
- at least one fresh mission signal/rescue screenshot

## Rejection conditions

Reject a future pass if:

- it adds a separate player body instead of the rover;
- it creates a hard invisible wall around the mission zone;
- rescue ignores line of sight entirely;
- disabled drones have no visible beacon;
- signal static is UI-only and does not affect control feel;
- Alt controls regress.
