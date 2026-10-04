# Operation StarFall Jupiter Spatial Authority Standard v0.1

## Scope
Europa Jupiter presentation.

## Authority rules
- Jupiter is a UV-mapped sphere and never a billboard.
- Europa Jupiter does not live directly under the exact camera-follow sky anchor.
- A dedicated celestial anchor follows 84% of camera translation; the remaining 16% supplies perceptible game-scale parallax.
- Camera rotation alone must not move Jupiter's world position.
- No active giant camera-facing glow or halo may sit behind Europa Jupiter.
- Jupiter uses oblate proportions: the two equatorial axes are equal and wider than the polar axis.
- Wrapped FX remain complete opaque 2:1 equirectangular frames on the original Jupiter sphere.
- Subtle globe rotation is allowed only when the storm, terminator, and lightning remain locked to the same wrapped sphere.
- Base visual grammar is horizontal lighter zones and darker tan/orange belts. Global splotchy noise is rejected.
- The Great Red Spot remains localized and its normal frame must not read as neon.

## Required verification
- `--jupiter-spatial-authority-test`
- `--jupiter-spatial-runtime-test`
- `--jupiter-full-wrap-fx-test`
- centered, turned, moved/parallax, and lightning proof screenshots at 1920x1080
- visual QA must meet the thresholds in `starfall_jupiter_spatial_authority_contract_v0.1.json`

## Acceptance principle
Jupiter must read as a distant 3D celestial body. Turning the camera moves it across the frame; moving the observer creates measured sky-direction parallax; rotating the camera does not translate the Jupiter node in world space.
