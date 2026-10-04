# Operation StarFall Planet Vision Standard v0.1

## Goal
Provide lightweight, readable planet-surface view filters that give the player a distinct screen-treatment option without replacing normal play.

## Rules
- `T` cycles planet vision modes while on planetary surfaces.
- Required modes: `STANDARD`, `ANALYTIC`, `THERMAL`, `LOWLIGHT`, `SPECTRAL`.
- Effects must visibly alter the scene using view-wide treatment (render tint / overlay), not just HUD text.
- HUD must show the active vision mode.
- The effect must work in both rover and remote drone views.
- The feature must remain lightweight. Startup default is `ANALYTIC` so the player immediately sees the survey treatment; `STANDARD` remains selectable with `T`.

## Intended Feel
- **Analytic**: cool cyan survey look and current startup default.
- **Standard**: clean normal view, still available from the T cycle.
- **Thermal**: warm contrast look.
- **Low-Light**: green gain look.
- **Spectral**: false-color purple/blue look.

## Validation
- Source must bind `T` to the mode-cycle function.
- A contract test must verify the mode list, Analytic startup default, overlay/update hooks, UI visibility, and screenshot flag support.


## Pass56 refinement
- Non-standard vision modes may add a **subtle transparent pixel-glitch breakup**.
- The effect should read like a lightly damaged display where light/scan energy catches, without blocking terrain, hotspots, or drone/rover readability.
- Standard View remains clean and unglitched by default.


## Pass57 refinement
- **Analytic Scan** is the mandatory default whenever the player enters a world, regardless of launch path or previous setting.
- Analytic Scan saturation is reduced to better simulate **old robotic vision**.
- Players can still cycle modes with **T** after world entry.


## Pass58 refinement
- Radiation exposure now increases robotic-vision distortion.
- Airless or more exposed worlds should show stronger scan breakup than protected worlds.
- Each world applies a lower-saturation baseline so the overall scene reads more like instrument footage.
