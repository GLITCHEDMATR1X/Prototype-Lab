# Operation StarFall Atmospheric FX Standard v0.1

Contract: `operation_starfall_atmospheric_fx_v0.1`

## Purpose
Atmospheric FX must make each moon more immersive without lying about the real body.
Atmosphere, haze, mist, plume, and visibility effects are owned by per-world profiles.
They are not one global orange/blue filter copied across every moon.

## World rules

### Titan
- Titan is the only active moon here with a dense atmosphere.
- Use warm orange/brown nitrogen-methane haze and reduced horizon clarity.
- Hydrocarbon seas/lakes remain methane/ethane sample targets from a safe bank.
- Do not use cyan/green gas volumes as the main sky identity.

### Enceladus
- No thick atmosphere.
- Atmospheric-looking FX should come from water-vapor and ice-particle plume material.
- Keep plume/ice mist cyan-white and local to the icy surface/sky.

### Mimas
- No thick atmosphere.
- Use only subtle regolith/crater dust visibility effects.
- Do not add weather/cloud systems.

### Iapetus
- Airless body.
- Dark-side visibility reduction is lighting, terrain contrast, horizon falloff, and tholin dust tone.
- Do not add fake clouds/weather.

## Implementation rules
- Use low-cost billboards/cards and fog settings.
- Do not raise terrain resolution for atmosphere work.
- Atmosphere layers must be profile-owned.
- Effects must be deterministic and pass `--atmospheric-fx-contract-test`.
- All active worlds need screenshot proof with `--atmosphere-fx-shot`.

## Acceptance checks
- Python compile passes.
- All four active worlds pass the atmospheric contract.
- Existing liquid, drone camera, rover/drone, signal rescue, power, action, progress, audio, generation, Windows, screen, display, and transport contracts still pass.
- Fresh screenshots are created for Mimas, Enceladus, Iapetus, and Titan.


## Pass58 refinement
- Titan should read significantly thicker and dimmer than before, with stronger haze and reduced horizon clarity.
- Overall world color saturation should stay restrained, especially on Titan.
