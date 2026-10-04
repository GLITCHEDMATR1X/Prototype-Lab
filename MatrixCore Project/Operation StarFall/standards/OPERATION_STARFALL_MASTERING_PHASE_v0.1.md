# Operation StarFall — Mastering / Remastering Phase v0.1

## Core purpose

Operation StarFall is now in **Mastering / Remastering Phase**. New passes should stop behaving like isolated experiments and should convert the whole directory into one solid game experience across all active instances.

The active instances are:

- StarFall shell / Saturn operations map
- Mimas
- Enceladus
- Iapetus
- Titan

## Mastering rule

A change is accepted only when it improves the shared experience without making any active world feel like a separate prototype.

## Directory ownership

```text
main.py                         StarFall shell and Saturn operations
Worlds/main.py                  active moon runtime
Worlds/display_config.py        only display/window authority
Worlds/transport_link.py        only world-return/launch authority
Worlds/mission_index.json       local mission discovery contract
Worlds/mission_registry.json    active world registry
standards/                      rules, contracts, phase docs
tools/                          validation and package-hygiene tools
verification/reports/           generated JSON/text reports
verification/screenshots/       latest proof screenshots/contact sheets
Worlds/verification/reports/    world runtime proof reports
Worlds/verification/screenshots/ latest world proof screenshots
assets/generated/               shell generated loading/sky assets
Worlds/assets/generated/        world generated textures/fx masks
Worlds/assets/sfx/              shared world sound cues
```

## What belongs in future mastering passes

### Audio and FX

- Every player action should have a clear feedback cue.
- `--no-audio` must never crash.
- Ambience cannot stack when switching worlds or menus.
- Shared SFX should live under `Worlds/assets/sfx/` unless a shell-only cue belongs at root.

### Progress

- Every active world needs objective state, completion state, and return/result state.
- Prototype Lab points are exported by the level and validated/saved by the Lab.
- UI text must come from real progress state, not placeholder claims.

### Generation

- Terrain, spires, rocks, lakes, and FX placement must be deterministic by world/seed.
- Rock and structure bases should intersect into terrain to avoid visible gaps.
- Visual-only spires must not become invisible blockers.
- Snap points and interaction zones must be recognizable and sized by the object shape.

### Actions

- Shared controls must mean the same thing in every world.
- TAB returns to StarFall when embedded.
- ESC opens an understandable pause/options path.
- H cycles HUD style.
- F1 opens help.
- Space jumps/climbs on surfaces.

### UI and screen size

- One display authority: `Worlds/display_config.py`.
- One HUD canvas rule: centered 16:9 safe canvas.
- Default HUD: minimal.
- Full command strip appears only in full HUD/help/menu contexts.
- Normal play cannot show stale verification labels.

### Windows and optimization

- Default: fixed bordered 16:9 window.
- Large: fixed 1920×1080-style window via flag.
- Fullscreen/windowed fullscreen stay opt-in.
- Package cannot contain `__pycache__`, `.pyc`, stale root pass reports, or random root screenshots.
- Performance work should reduce mesh/state/text churn before adding more effects.

## Mastering pass sequence

1. Pass40 — Mastering Foundation / Package Hygiene
2. Pass41 — Audio + FX Authority
3. Pass42 — Progress / Result Contract Across Worlds
4. Pass43 — World Action Consistency
5. Pass44 — Generation Rules / Rock & Terrain Authority
6. Pass45 — Optimization + Windows Settings Polish

## Pass acceptance rule

Each pass must include:

```text
BASE USED:
FILES CHANGED:
FILES REMOVED FROM RELEASE:
COMMANDS RUN:
SCREENSHOTS / REPORTS CREATED:
CONTRACTS PASSED:
KNOWN ISSUES:
ACCEPT / REJECT:
```
