# Entropy World Classes — Pass 3

Entropy chooses from twelve deterministic planetary surface classes. Each class now drives an unbounded absolute-coordinate terrain field. A world class changes geological height grammar, palette, fog depth, horizon weather, streamed field objects, foliage density, ancient ruin art, and its dedicated looped ambient sound.

## Original classes

- **Serekh Dunes / desert** — rolling dunes, mineral debris, sand drift.
- **Nivalis Reach / ice** — pale ridges, frozen relics, snow.
- **Viridian Crown / jungle** — dense organic silhouettes, rain, overgrown ruins.
- **Cinder Atlas / volcanic** — dark broken heights, ash and cinders.
- **Aurel Glass / crystal** — sharp luminous terrain, suspended glass fragments.
- **Pelagos Vault / oceanic** — low blue-green terrain, mist and drowned-looking relics.

## New Pass 2 classes

- **Mycelian Bloom / fungal** — swollen organic basins, magenta ground, cyan spores, dense alien growth.
- **Ferric Grave / rust** — stepped iron mesas, orange haze, cinders and industrial-looking wreckage.
- **Ilyr Salt Mirror / salt** — broad pale flats with rare mineral islands and sparse ancient monuments.
- **Noctilucent Basin / abyss** — deep dark valleys, isolated cyan ridges, floating luminous embers.
- **Tempest Plateaus / storm** — broad shelf terrain, cold storm light, hard rain and lightning.
- **Roseglass Barrens / roseglass** — tall pink crystalline splinters, narrow valleys and glass fall.

## Pass 3 audio identity

Each supported world ID maps directly to a generated seamless WAV under `assets/sfx/ambience/surface/`. Entering a ruin replaces the surface sound with the dungeon, castle or catacomb loop. Entering the ship silences both and starts the interior hum.

## Deterministic verification

Any surface class can be forced for testing without changing normal random world selection:

```bash
python main.py --no-audio --test-shot verification/screenshots/fungal.png --test-state surface --test-seed 17 --test-biome fungal
```

Supported IDs:

`desert`, `ice`, `jungle`, `volcanic`, `crystal`, `oceanic`, `fungal`, `rust`, `salt`, `abyss`, `storm`, `roseglass`

## Pass 20 single-world mix

Only one planet is shown in each system. The planet's class is selected from the complete twelve-class list above using the existing deterministic shuffled material pool. Across 1,000 verification seeds, all twelve classes appeared as the sole active planet. No biome or surface variation was removed.

Pass 25 uses the same twelve-class system mix for the six-Data-Fragment expedition. Recovering the marked Data Fragment no longer auto-warps; the player can keep salvaging, return to the ship, refuel or upgrade, and choose when to leave the system.

## Seamless surface generation

Pass 22 removes the former finite planetary edge. Every world streams deterministic 64-unit chunks around the player across both positive and negative coordinates. Chunk borders share one continuous terrain field, and bounded caches discard distant rendered regions without changing what will regenerate when the player returns. Newly explored chunks distribute recoverable trees, plants, and surface objects through the same persistent salvage/fuel-cell processing rules used in the original charted area.

The visual grammar is geological rather than streak-based: macro plates, folded ridges, basins, strata, fractures, and localized mineral deposits shape relief and color. Accent hues appear mainly where deposits intersect faults instead of crossing the whole screen as decorative bands.

## Pass 27 landmark silhouettes

The twelve established terrain families now also have a large visual anchor identity: Sun Ring, Cryo Needles, Root Cathedral, Caldera Crown, Prism Choir, Flood Pylons, Spore Crown, Foundry Ribs, Mirror Obelisk, Void Lantern, Storm Mast, and Roseglass Fan. Three deterministic visual-only anchors are generated per surface. They are kept clear of the ship and archive ruins and never affect collision or resource logic.


## Pass 33 expedition identity

The twelve world classes remain the same. Pass 33 adds no thirteenth biome and changes no terrain or hazard values. Instead, each class now has a compact archive-record identity used consistently by arrival guidance, surface routing and ship storage. Brand-new consecutive systems strongly prefer a different hazard family/world class before their seed is committed, reducing procedural repetition while preserving random seeded generation. Existing saved systems are not regenerated.

The six required archive slots also rotate their preference across the six existing ruin families (ziggurat, observatory, bastion, spire, sepulcher, labyrinth). This selection occurs only inside the existing reachable target pool, so the established route-distance contract remains intact.
