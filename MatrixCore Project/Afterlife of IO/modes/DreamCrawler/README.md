# Dream Crawler Pass 12 — Hostable Core & Entropy Ruin Dives

## Pass 12 — what changed

- The game now lives in `dreamcrawler_core.py`, which has no import-time side effects (no window, no audio, no folders created). `main.py` is a thin standalone launcher.
- Entropy uses the same engine for **archive-ruin dives**: pressing `E` at Entropy's marked ruin sends this nine-bot team underground inside Entropy's window. Floor 1 hides the stairs down; floor 2 is the vault, where a WARDEN crawler guards the Data Fragment. Any explorer can take it; the team then regroups at the **ASCENT LINE** to climb out, and Entropy continues with the fragment carried back to the ship. Entropy's collapse clock runs at 1/4 speed underground.
- Mouse controls: hold LMB to walk toward the cursor, RMB to use a weapon.
- Crash logs go to `%LOCALAPPDATA%\GLITCHED MATRIX\DreamCrawler\logs` instead of the install folder.
- Performance: each room is pre-rendered once and field-of-view is cached per tile (identical visuals, roughly half the frame cost).
- The room banner sits below the chat log so the two no longer overlap.
- Launchers now start `main.py` (they pointed at a missing `DreamCrawler2D.py`).

The standalone Pass 11 loop below is unchanged.

---

# Pass 11 — Crawler Senses & Personalities

A co-op perception crawler where nine explorers independently reveal a procedural cavern, scavenge one-use weapons and treasure, survive one crawler, and descend through the stairs.

## Core loop — protected

Explore → scavenge → evade or fight the crawler → find the stairs → descend into a newly generated cavern.

Pass 11 deliberately does not add a second progression layer, extra enemies, currencies, quests, or a new HUD panel.

## Launch

- Windows: double-click `RUN_DREAMCRAWLER.bat`
- Python: `python main.py`
- MatrixOS: existing `PYGAME_OS_LAUNCHER=1` launch remains supported.

Standalone launch is supported by default. Set `DREAMCRAWLER_REQUIRE_MATRIX=1` only if a distribution specifically requires MatrixOS-only launching.

## Controls

- `WASD` / Arrow keys — move
- Hold `LMB` — walk toward the cursor
- `SPACE` / `RMB` — use one carried weapon when the crawler is in range
- `M` — mute/unmute music and sound
- `ESC` — quit
- Resize freely; gameplay retains a 16:9 logical frame with letterboxing.

## Pass 11 — Crawler Senses & Personalities

Every generated room now deterministically receives one of four crawler profiles. The same crawler health, collision, attack rules, loot, stairs, procedural generation and room loop remain intact.

- **LISTENER** — short vision, strong hearing; footsteps are especially dangerous.
- **WATCHER** — long line-of-sight, weak hearing; walls and corners matter more.
- **STALKER** — shadows grouped explorers and commits more aggressively against isolated targets.
- **WARDEN** — remains tied to the stair region and gives up distant pursuit instead of roaming the entire cavern.

The crawler now uses limited perception rather than permanent omniscience:

- sight requires range and real cavern line-of-sight;
- movement, loot interaction and weapon use create AI noise events;
- losing sight changes pursuit into investigation of the last-known location;
- once awareness expires, non-Wardens return to idle while the Warden returns to the stairs;
- the Stalker can hold distance from a grouped party instead of always charging directly.

The room-entry message and the crawler's existing on-entity label identify the current behavior profile. A small replaceable `alert` cue plays only when the crawler newly commits to chasing the human player. No new permanent HUD region was added.

## Pass 10 — Expedition Knowledge Network preserved

Each explorer still owns a private perception map. Floor/wall exploration is never copied between characters. Actionable discoveries transfer only when living explorers physically meet with line-of-sight:

- stairs
- crawler last-known position
- weapon pickups
- treasure pickups

Relayed information can continue onward through other explorers, while stale loot/crawler reports are pruned.

## Earlier repairs preserved

- Game-folder-anchored asset and crash-log paths.
- Standalone launch support.
- Crawler A* pathfinding through real walkable tiles.
- Collision-safe crawler movement.
- Edge-triggered/rate-limited one-use attacks.
- Replaceable generated ambience and SFX.
- Non-rectangular shaped crawler sprite instead of the old square noise texture.

## Audio replacement

Replace files in `assets/sfx/` using the same cue stem (`spawn`, `exit`, `step`, `caught`, `hit`, `loot`, `alert`) with WAV, OGG, or MP3. The music folder loads and loops the first supported audio file alphabetically.

## Validation

Run:

```bash
python tools/verify_build.py
```

The verifier does not require Pygame. It checks source syntax/contracts, all four crawler profiles, hearing/vision/last-known-state behavior, Warden territory rules, Stalker isolation preference, Pass 10 knowledge relay/privacy, procedural room reachability, crawler path authority, attack gating, WAV integrity, and package hygiene.
