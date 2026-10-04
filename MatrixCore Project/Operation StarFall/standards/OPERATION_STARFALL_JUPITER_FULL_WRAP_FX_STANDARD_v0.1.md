# Operation StarFall Jupiter Full-Wrap FX Standard v0.1

## Scope

This standard governs Jupiter as seen from Europa. It exists to prevent a wrapped gas giant from regressing into a sphere plus camera-facing storm, shadow, or lightning cards.

## Authority

- Europa owns every `europa_jupiter_*` generated asset.
- Triton owns `triton_neptune_generated.png` and must not regenerate or replace Europa Jupiter assets.
- The original `jupiter_sphere` is the only runtime geometry that owns Jupiter's visible surface FX presentation.

## Wrap rule

The Jupiter base, storm/lightning source frames, and terminator source are authored in 2:1 equirectangular texture space.

Runtime presentation uses complete opaque 2:1 wrapped frames. Each frame contains:

1. broad Jovian belt wrap,
2. lower-right broken Great Red Spot cloud structure,
3. optional tiny lightning filaments inside the storm,
4. curved spherical terminator/shadow.

The complete frame is applied to the original Jupiter sphere. Runtime animation swaps complete wrapped frames; it does not move camera-facing cards over the planet.

## Forbidden regressions

- no flat storm billboard,
- no flat shadow billboard,
- no floating lightning sprite/card,
- no extra transparent FX sphere visible to Analytic Scan,
- no Jupiter-specific multitexture stage required for the shipping presentation,
- no shared generated filename that allows Triton/Neptune generation to overwrite Europa/Jupiter assets,
- no dense tiny belt pattern that collapses into texture noise at Europa viewing distance.

## Readability rule

At the accepted Europa proof camera:

- broad cloud bands remain visible,
- the left hemisphere is visibly darker than the right through a curved terminator,
- the Great Red Spot remains on the lower-right visible hemisphere,
- the storm edge is broken/irregular rather than a perfect pasted oval,
- forced flash frames add localized pale filaments inside the storm only.

## Verification

Required commands:

```bash
python3 -m py_compile Worlds/main.py
cd Worlds
python3 -B main.py --moon europa --jupiter-full-wrap-fx-test --no-audio
python3 -B main.py --moon europa --test-shot ../verification/screenshots/opstar93_europa_jupiter_full_wrap.png --windowed-fullscreen --no-audio --no-loading-screen
python3 -B main.py --moon europa --test-shot ../verification/screenshots/opstar93_europa_jupiter_lightning_frame.png --jupiter-wrap-frame 2 --windowed-fullscreen --no-audio --no-loading-screen
```

Both proof screenshots must be 1920x1080. Visual QA must verify a meaningful left/right Jupiter luminance difference, a readable red storm region, and localized flash-frame color lift inside the storm.
