# Operation StarFall — World Action Standard v0.1

Pass43 locks one shared action language across every active moon operation.

## Rule

Every active world must describe and execute the moon loop using the same player-facing sequence:

```text
SURVEY -> DRILL_DEPLOY -> ANCHOR -> LOWER_LINE -> MATCH_TOOL -> REEL_ATTACH -> COLLECT -> RETURN_RESULT
```

The world may change terrain, target resources, ambience, hazards, and visual identity, but it must not invent a separate control vocabulary for the same operation loop.

## Standard actions

| State | Player-facing binding | Meaning |
|---|---|---|
| SURVEY | Mouse look + sonar HUD | Sweep terrain until the sonar return is readable. |
| DRILL_DEPLOY | 1 on hotspot lock | Send the drill drone to the locked site. |
| ANCHOR | Wait for tripod brace | Let the drone feet and anchor spikes settle. |
| LOWER_LINE | UP/DOWN arrows | Adjust line depth until the return becomes hot. |
| MATCH_TOOL | LMB on drone/line | Cycle the line attachment to the required tool. |
| REEL_ATTACH | RMB or R when signal is hot | Attach and hoist cargo while managing tension. |
| COLLECT | LMB on held cargo | Store visible cargo held under the drone. |
| RETURN_RESULT | TAB to StarFall shell | Return standardized result packet to Operation StarFall. |

## Active world profiles

- **Mimas:** crater snowpack over ice, snow-slide traversal, magnet default.
- **Enceladus:** cyan ice sheet / white buried terrain, solid ice traversal, magnet default.
- **Iapetus:** equatorial ridge / dark tholin slope, low-gravity ridge climb, grapple default.
- **Titan:** methane shoreline / tholin dunes, shoreline slide, hook default.

## HUD rule

The minimal HUD must show the current loop phase and the standardized action hint. Compact/full HUD can show deeper rig state, but the first line of guidance should still use the same sequence names.

## Help-panel rule

F1 help must list the shared action loop and must not imply that one world uses a different control scheme for the same operation stage.

## Contract test

```bash
python -B Worlds/main.py --world-action-contract-test --no-audio
```

The test must confirm:

- all four active worlds have action profiles
- all standard states have bindings
- HUD uses the standard action line
- help text describes the standard loop
- drill/deploy, reel/attach, collect, and TAB return result paths exist
