# Afterlife of IO — Current Design Authority

## Status

Current source-package authority: **Pass 147 — Mode Hub** (builds on Pass 146 — Campaign Integrity).

This document describes the game that exists now and the rules future passes must preserve. Historical pass-by-pass validation records are intentionally not shipped here.

## Core identity

IO is an entity trapped inside an artificial afterlife for an incomprehensibly long span of time. The game is built around two persistent temporal anchors of that same afterlife and the consequences of altering its Beginning.

The central player fantasy is **causal archaeology**:

**Present: discover a problem or consequence → Beginning: create/alter the cause → Present: return and observe what endured.**

The game should remain atmospheric, exploratory, mysterious, and mechanically readable rather than becoming a generic action game.

## The two temporal anchors

### Present / Far Future

- The established current afterlife.
- Decayed, dim, entropic, and largely peaceful until late progression.
- IO studies consequences, learns powers, inspects Shrines/Obelisks, uses machines, and follows Gleebs's thread.
- Present world position/state remains persistent across trips to the Beginning.

### Beginning / Past

- The earliest accessible state of IO's afterlife.
- Contains stationary Memory Guardians and intact causal structures.
- Guardian encounters are deliberate rather than roaming combat interruptions.
- Beginning world position/state remains independently persistent.

### Gleebs

Gleebs is the central temporal anchor and narrative guide. Temporal crossing is a dialogue choice at the central anchor, not a generic instant world-toggle key.

`Tab` belongs to Lantern Projection once that power is learned.

## Persistence model

The game maintains separate Present and Beginning state plus shared causal/progression state.

Important persistent categories include:

- player position/facing/walk layer per era;
- Guardian defeat state;
- Future Shrine/Obelisk consequences;
- learned Lantern powers;
- Archive/lore discovery;
- machine inventory and placements;
- manual save slots;
- presentation/settings preferences.

Past combat failure must not arbitrarily erase established Future progress.

## Memory Guardians

Memory Guardians are stationary Past entities representing archives/memories of IO's civilization.

Standard flow:

1. Find the Guardian in the Beginning.
2. Interact and hear dialogue.
3. Choose whether to enter battle.
4. Fight in the dedicated readable battle presentation.
5. Victory persists.
6. The corresponding Future Shrine/Obelisk manifests.
7. The Future monument can be bound as a persistent causal record and later challenged as an Echo.

This rule applies to **all seven** Memory Guardians. No Guardian may exist only as a defeated portrait/progression flag without its Future consequence. Guardian dialogue memory is also per-Guardian; refusing one Guardian must never alter another Guardian's conversation state.

Guardian order remains nonlinear except where explicit final-stage progression requires completion.

## Campaign completion

Recovering all seven civilization archives changes Gleebs's mission state from preparation to release. Returning to **Gleebs → Current Mission** must resolve into the campaign ending sequence rather than falling back to the ordinary topic menu.

The ending establishes that Gleebs honors the exchange and IO's continuity crosses beyond the afterlife. After completion the player may continue exploring the archived simulation or quit. Save schema v5 stores `campaign_complete`; older v4 saves remain valid.

## Lantern combat

The lantern is IO's combat focus and power-state communicator.

- Ranged attacks originate from the lantern.
- Ability colors must remain semantically consistent once established.
- Telegraphs, turn order, damage feedback, and command UI must stay readable.
- Battle presentation must not cover critical combat information with decorative HUD clutter.

## Lantern Projection

Projection is an outside-battle remote drone/camera ability.

- `Tab` launches/recalls it when learned.
- It begins with a short duration and can improve through progression.
- Hunter drones target the Projection, not ground IO.
- Projection upgrades/powers do not become an excuse to replace the main exploration loop.

## Archive and guidance

- `L` opens the Archive when records exist.
- `F1` always exposes the current Continuity Thread/contextual help.
- Guidance can be reduced or disabled in Settings, but F1 remains available on demand.
- Player-facing documentation must describe current controls only.

## Current pause / settings authority

Pause order is intentionally compact:

1. Resume
2. Save Game
3. Load Game
4. Settings
5. Quit to Desktop

Controls live under **Settings → Controls**.

Pause Quit requires explicit confirmation because manual progress can otherwise be lost.

Inventory is **not** buried in Pause: `I` opens the full IO Inventory directly during normal exploration.

## Inventory and hotbar

- The permanent 1–6 hotbar is the fixed MAIN MACHINE KIT quick-access strip.
- It is not the complete inventory.
- `I` opens the full owned machine-component inventory.
- Secondary, fabricated, and compatible legacy-owned parts stay in the broader inventory/workshop rather than expanding the permanent HUD.
- Raw source artwork must not be advertised as finished generic parts merely because a PNG exists.

## Machine authority

The proven drive rule is:

**Core + Gear + Pivot physically connected = powered drive.**

Additional principles:

- Connections should agree visually and mechanically through connector/socket authority.
- Pipe mechanics remain mechanical and do not secretly control temporal travel.
- HEAD / ACTUATOR / SENSOR / TOOL / FRAME accessories may consume/use powered assembly state but cannot bypass the Core/Gear/Pivot drive requirement.
- The MACHINE HEAD can diagnose required hardware/connection state.
- Autonomous locomotion is not implemented yet and must not be falsely presented as working.
- Machine loops/audio require stable channel ownership; loss of power or leaving the Past stops appropriate machine loops.

## Sable

Sable is a stationary Builder ghost tied to the construction history of IO's afterlife. Her presentation should remain calm, exacting, mysterious, and consistent with later Holoverse continuity. Her machine shop is a fabrication/catalogue interface, not a replacement for IO's direct Inventory.

## Present local-route authority

The accepted Present routing/fade behavior must remain intact:

- New Game begins at the accepted Present start near X=219, Y=294, facing right.
- The invisible Present local-route entry near X=199, Y=531 uses a protected black fade to the lower-right route.
- The enlarged lower-left exit near X=71, Y=972 uses the same protected black fade and returns IO near X=3181, Y=551 facing left.
- Camera relocation occurs while fully black.
- These local-route transitions are independent of Gleebs temporal travel.

## Presentation authority

- Internal logical canvas remains 1280×720.
- 1920×1080 is the primary review target; 1280×720 remains mandatory fallback.
- HUD elements must not overlap or cover ordinary gameplay unnecessarily.
- Replaceable menu/HUD assets and fonts should remain fail-soft.
- Text Style, Motion FX, Flash FX, Guidance, atmosphere controls, and fullscreen remain presentation settings, not gameplay balance changes.
- Deteriorated/archive text styling must not make required player instructions unreadable.

## Input authority

Keyboard/mouse is always supported. Controller support is optional and additive.

Important direct controls:

- `I` Inventory
- `L` Archive
- `F1` current thread/help
- `Esc` Pause/back
- `Tab` Projection
- `T` Machine Focus
- `1–6` main machine kit

Controller UI navigation should remain consistent. During ordinary exploration, right-stick click opens Inventory and D-pad Up opens Help. During Machine Focus, right-stick click retains its contextual flip action.

## Save / package authority

- Manual saves are atomic user-data files, not installation-folder files.
- Current package documentation should remain concise and current.
- Historical pass reports, old validation scripts/results, old screenshots, cache/bytecode, crash logs, and one-time migration artifacts do not belong in the playable source package.
- A build tool/script must never be claimed in documentation unless that file is actually included.

## Anti-regression rules

Do not reintroduce:

- `Tab` as generic temporal travel;
- automatic Present routing that bypasses accepted fade gates;
- square-stretched drone/fragment media;
- giant permanent diagnostic HUD panels;
- health/status UI that obscures gameplay unnecessarily;
- machine source PNGs masquerading as finished parts without metadata;
- center-distance-only machine connections when visible connector authority exists;
- pass-history/validation diaries inside player-facing documentation;
- controller-only or keyboard-only menu dead ends when an equivalent supported route already exists.

## Future work boundary

Future passes may expand machines, causal puzzles, Guardian content, world presentation, and progression only after preserving the current interaction, save, route, and interface contracts above.
