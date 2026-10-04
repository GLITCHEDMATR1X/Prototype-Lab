# The Indigo Giant — changelog

Newest first. Each pass has a detailed note (`docs/pass_notes/PASSnn_*_NOTE.txt`) and, from Pass 38, a check (`.dev/checks/passnn.py`; before Pass 62 these were `tools_passnn_check.py` at the top level).

## Pass 63 A HoloVerse Dimension

- **The Indigo Giant is now an archive in HoloVerse.** Put the folder beside HoloVerse in Prototype Lab and it appears in Gleebs > Dimension Archive as *The Indigo Giant* (symbol IG, indigo). It still runs on its own exactly as before: from the Lab cabinet, `RUN_INDIGO_GIANT.bat` or `python main.py`.
- **Same window, no second engine:** HoloVerse mounts the game inside its own window (the Mirror's Limbo pattern).
  - The game's world lives under its own node, so its lights, fog, shader and shadows never touch HoloVerse's scene.
  - HoloVerse owns the window: resolution, fullscreen, vsync and anti-aliasing show "set by HoloVerse".
- **Keys while in HoloVerse:**
  - **TAB always returns to HoloVerse.** "Be Nyx / be Orbit" moves to **V** for that visit only; your saved keys still say TAB.
  - The key screen will not take TAB while hosted.
- **Leaving:** "quit" reads **return to HoloVerse** on the title, the Esc menu and the ending card. The journey is saved first. A new journey restarts inside the same window.
- **Nothing left behind:** on the way out the game removes every task, key binding, sound, node and piece of UI it made and restores the few HoloVerse settings it changed. Tested with five round trips into the real HoloVerse (TAB, Esc menu, new journey): no difference in HoloVerse afterwards.
- **HoloVerse remembers the archive:** it records the day, the etchings read (as fragments, x/14), whether Crimson has fallen, and, when Nyx and Orbit have left with Gleebs, the signal `indigo_giant_archive_complete`.
- **HoloVerse (three small edits):** its catalog knows the project, it prefers the Dimension Archive for it, and once you have finished the archive **Nyx and Orbit remember REDACTED** in their HoloVerse conversations.
- **New files:** `holoverse_native_adapter.py`, `holoverse/` (responder, fixed identity, readme), `dimension.json`, `icon.png` (the archive picture), `indigo_giant/holoverse_host.py`.
- **Fix:** a save made before Gleebs was ever placed no longer fails.

Details: `docs/pass_notes/PASS63_HOLOVERSE_DIMENSION_NOTE.txt`. Check: `.dev/checks/pass63.py`.

## Pass 62 A Neater Build

- **Nothing changes in play.** Saves, settings, your keys and how the Prototype Lab starts the game are the same. Only where files live has changed.
- **Top level:** now only what you need to play: `main.py` (a small launcher), the two `.bat` files, `requirements.txt`, the README, this changelog, your `controls.json`, and a new `cover.png` so the Lab cabinet has a picture.
- **`indigo_giant/`:** the game is now a Python package. Its modules can't collide with the Steam game's own (`audio`, `hud`, `settings`...) when it is folded in. `paths.py` is the one place that knows where the files are.
- **`docs/`:** pass notes, screenshots and the animation map.
- **`.dev/`:** checks and tools. The Lab cabinet no longer lists them: it offered 59 files, now 30.
  - `RUN_CHECKS.bat` runs every check with one summary.
  - `RUN_DIAGNOSTIC.bat` is refreshed to check the Gleebs model, fonts and the package.
- **`TIDY_OLD_FILES.bat`:** run it once. It moves the old top-level copies and stale files (the Pass 12 `validation.txt`, an old log and CSV, `app.py`, `__pycache__`) into `_to_delete\pass62\`. It never deletes anything and never touches `controls.json` or saves.

Details: `docs/pass_notes/PASS62_TIDY_BUILD_NOTE.txt`. Checks: `.dev\RUN_CHECKS.bat`.

## Pass 61 Nyx, Orbit and Crimson; the Etchings; Gleebs and the End of REDACTED

- **Names:** Nyx is the Indigo Giant, Orbit is you, Crimson is the red giant, and the planet is REDACTED. Every message, label, prompt, hint, help page and story uses them. Code names, sound keys and saves are unchanged.
- **Etchings:** 14 standing stones cut with glowing glyphs, from ~60 m out to ~9.4 km.
  - By day the marks are dark cuts. At night they glow cyan, with a glimmer you can see from ~250 m.
  - Hold E to read one. Together they tell who Nyx, Orbit and Crimson are, why the world is called REDACTED, that it is dying, and who might come.
  - J > *notes* keeps the ones you have read.
- **The end - Gleebs comes:** when Crimson has eaten the pale branch and lain down for good, a beam of light falls from the sky ahead of you.
  - Gleebs (the Utopia Vision model) forms in it as a 26 m cyan hologram, with crawling scanlines, flicker and glitches, and speaks.
  - It waits in its light for as long as you like. Walk in with Nyx beside you and hold E to leave REDACTED. It will not take you alone.
  - A short scene follows: Nyx and Orbit rise up the beam, then a last look at Crimson, left lying below as the beam goes out.
  - The card "they left REDACTED" ends it: new journey or quit.
  - Gleebs' state is saved. An older save with Crimson already dead brings Gleebs on load.
- **Fixed:** the spoken lines were drawn in dark ink even at night, where they could hardly be read. They now switch to pale night ink with a soft shadow.
- **Sounds:** new placeholders for reading an etching, Gleebs arriving, speaking and the departure.

Details: `PASS61_NYX_ORBIT_GLEEBS_NOTE.txt`. Check: `python tools_pass61_check.py`.

## Pass 60 The Red One's Crimson Powers

- **Night only:** the red one burns crimson. It fades in with the dusk and out at dawn. Its body glows, a crimson halo hangs round it, and a crimson light falls on the sand and on you.
- **The crimson wave (avoid it):**
  - When you or Indigo come within ~24 m, its light swells for 1.8 s and a pulsing ring on the sand shows how far the wave will reach (30 m). Then it bursts.
  - Caught inside, you are thrown back, dazed and hurt (40 life, less with Indigo's glow on you). Indigo is winded and staggered; its own glow softens it.
  - A jog gets you out of the ring in time; a walk does not.
  - Inside an unbroken shell, or riding on Indigo's shoulder, it passes you by.
  - It takes 6 s to swell again. Awake, the red one stands and raises its arms to call it.
- **The crimson ward:** resting at night, or knocked out at night, it cannot be beaten. Blows glance off (and set off a wave), and it will not take a pale scrap. By day it has no power at all.

Details: `PASS60_CRIMSON_POWERS_NOTE.txt`. Check: `python tools_pass60_check.py`.

## Pass 59 Indigo's Night Glow

- **At night Indigo glows** radiant indigo. It fades in with the dusk and out at dawn.
  - Its body shines with a bright rim, a halo hangs round it, and it shows through the night haze as a beacon.
  - Its light falls softly on the sand around it (~30 m) and on you, on the side facing it.
- **It protects Indigo:** hits cost it 40% less stamina, and the cold drains it half as fast. Knocked out, the glow sinks to an ember.
- **It warms you:** inside its light (up to ~24 m, beyond the 14 m of its body heat) the night cold eases.
- **Take some of it:** at night, hold E beside Indigo. Each draw dims Indigo a little for a few minutes. You get a faint indigo shimmer and a glow bar. While you carry it:
  - breath: effort costs x0.6
  - work: dig, search and smash in 0.7 of the time
  - health: you heal slowly, and heat, cold and blows hurt x0.65
  - night: the cold creeps in slower
- **It fades:** by day it is spent as you spend breath, and a little each minute. It fades away at once if you run out of breath.
- It is saved with your journey.

Details: `PASS59_INDIGO_GLOW_NOTE.txt`. Check: `python tools_pass59_check.py`.

## Pass 58 Look Up, Footprints, Pace, Fighting as Indigo

- **Camera:**
  - Drag with the right mouse (or use the arrow keys) to look around and now also up. The view used to stop at the horizon.
  - Past level, the camera stays low behind your character and tilts up, to the sky, the giants and the towers.
  - It looks further down too, and it never goes into the sand. Before, it could sink behind a dune.
- **Footprints:**
  - They lie along the way you walk. A mirrored heading used to lay them across the path at any diagonal: the "stretched, horizontal" look.
  - They are shaped like soles: a round heel, a narrow arch on the inner side, a wide ball, left and right mirrored. They start at the ankle.
- **Quicker on foot:** walk 1.45, jog 5.6, sprint 8.4 m/s (were 1.2 / 4.4 / 6.6), with quicker acceleration.
  - The feet stay planted, and jog and sprint now play at their natural pace.
  - The giants are unchanged.
- **Fighting as Indigo:**
  - **Punch:** left mouse or F. Jab and cross alternate, and a press during a punch chains the next one in.
  - **Hammer blow:** hold, then let go. Indigo winds up, strikes twice, drives the red one back and staggers it.
  - **Aim assist:** a blow turns Indigo to the red one and steps in when it is just out of reach.
  - **Facing:** blows land only where Indigo faces.
  - **Timing:** punches land when the fist is out.

Details: `PASS58_LOOK_FOOTPRINTS_PACE_FIGHT_NOTE.txt`. Check: `python tools_pass58_check.py`.

## Pass 57 Build Review

- **Saves:** shells restored by a saved journey now keep their levelled sand. After a load their floors used to be up to 0.5 m uneven.
- **Shells Indigo sets down** get level sand too, kept through saves. Branches, scraps and finds beside them follow the new ground.
- **Doorways:**
  - Brushing the doorframe near the opening slides you in (or out), instead of stopping you dead.
  - Inside the doorway, its sides are walls you slide along.
- **Indigo:**
  - It walks round to your side of a shell.
  - It never reaches in through a roof to lift you.
  - It never sets you down in a shell's wall.
- **Playthrough:** the automated playthrough now shelters in shells. Over 3 days and two seeds: 0 problems, 10–13 shell visits per run.

Details: `PASS57_BUILD_REVIEW_NOTE.txt`. Check: `python tools_pass57_check.py`.

## Pass 56 A Natural Mouth

- **An arched doorway:** the mouth is now a smooth, rounded arch set into the front of the shell, 2.2 m high and ~3 m across at the sand. Its feet splay out where they meet the sand, and its edge is gently worn. Before, it was a notch cut along the mesh rows: flat-topped, with straight sides.
- **A real shell wall:**
  - a ribbed outside and a pearly inside (lilac and rose)
  - a rounded lip, 14 cm thick, joining them all round the rim and the mouth, and turning out a little like a real shell's lip
  - the foot of the shell is sand-stained
- **Broken holes** in cracked shells follow a jagged break with a visible wall edge. They were stair-stepped squares.
- **No more horns:** the two hinge "ears" at the back read as horns and are gone. A few small barnacles sit low on the sides and back.
- **Domed higher:** 3.2 m (was 2.7), so the doorway sits in the front instead of taking a bite out of the whole face. The room inside is bigger too: ~5.2 × 4.6 m of standing room.
- **Walking follows the real shape:**
  - You pass through the part of the arch that clears your head (~1.5 m wide), not its low sides.
  - Inside, you walk wherever the roof is above your head. Before, you could walk into the low rim with your head through the roof.
- The shell models are closed and drawn one-sided (they were two-sided sheets). Each is ~10k triangles, built once at load (~0.13 s).

Details: `PASS56_NATURAL_MOUTH_NOTE.txt`. Check: `python tools_pass56_check.py`.

## Pass 55 Walk-in Shelters

- **Shells are bigger than you now:** 6.8 × 6.0 m and 2.7 m high, with a 2.1 m arched mouth (they were 3.8 × 3.2 × 1.35 m, smaller than the player).
- **Walk in and out:** no key and no sleeping needed. Inside an unbroken shell you cool off, heal and recover stamina, and the red one loses you (unless it saw you go in). Move about freely inside and walk out through the mouth. **E** at the mouth still steps you in.
- **Solid walls:** you can only get in or out through the mouth. An overturned shell is solid all round, and a cracked shell is shade (not a hiding place).
- **See-through:** the shell you stand in fades to 35%, so the camera still shows you.
- **Level floors:** the sand under every shell is levelled, so it sits flat. Shell sites are chosen beyond the built ground, so the terrain never rebuilds under you.
- **Indigo steps around shells** instead of walking through them. The red one still strides over them.

Details: `PASS55_WALK_IN_SHELTERS_NOTE.txt`. Check: `python tools_pass55_check.py`.

## Pass 54 Polish
See `PASS54_POLISH_NOTE.txt`: fixes from a full code review and a three-day automated playthrough.

## Pass 53 Giant Stamina

- **Stamina:** both giants have fight stamina. Punches and hits wear it down, and it recovers between blows (fast once the fight stops). A giant is knocked out only when a hit lands while it is exhausted. A straight fight lasts ~25–30 s (was ~5 s).
- **Indigo knocked out:** tap **E** beside it three times to wake it. Left alone, it gets up at dawn.
- **The red one knocked out:** it lies for 2.5 minutes, so run. It gets up dazed and has lost you for a whole day. Then it finds your tracks again. Hitting it while it is dazed ends the calm.
- **Poison:** with pale scraps on you, tap **E** beside the knocked-out red one to feed it one. Each of up to 3 doses weakens its stamina, blows, pace and sight, and keeps it down longer. The poisoned blood branch still ends it for good.

Details: `PASS53_GIANT_STAMINA_NOTE.txt`. Check: `python tools_pass53_check.py`.

## Pass 52 Feet That Match the Ground

- No more running in place or skating. Every walk cycle, for you, Indigo and the Red Giant, now advances by the ground actually covered. Planted feet stay planted at any speed, including accelerating, slowed by heat or cold, sneaking or AI-driven. The human jog's foot slip went from ~137% to 1.4%.
- Footprints and step sounds land at each foot's real touchdown, where the foot is.
- **Human speeds** now match their animations: walk 1.2, jog 4.4 and sprint 6.6 m/s (were 1.35 / 2.5 / 3.5). The human changes pace quickly (standing to jog in ~0.3 s) and still stops the moment you let go.
- **The giants** keep their speeds, and now stride on their walk cycle at every pace: heavy and always grounded.
- **Indigo's "shade me"** now lands its shadow on you every time (it could stop on the very edge before).

Details: `PASS52_FEET_MATCH_GROUND_NOTE.txt`. Check: `python tools_pass52_check.py`.

## Pass 51 The Deep Desert

- The desert now takes a long time to know. Measured with a headless explorer (`tools_discovery_probe.py`), finding every kind of place takes a rider about 17–22 play hours (was 7–14), a mixed player 22–37 (was 12–32) and a walker 44–83+ (was 20–23).
- **Tiers by distance:**
  - common kinds everywhere (the eight nearest the start are one of each)
  - uncommon from ~1.6 km
  - rare from ~3.4 km
  - three new kinds: lantern stones, split geode, sunken village
- **Four legends, one each per world:** the Sleeping Titan (8 km), the Sky Well (11 km), the Small City (14 km) and the Red Cradle (18 km).
- **Rumours:** some places tell a rough story of which way a legend lies. Stories heard together narrow it down, and Indigo senses a legend you have heard of from farther away.
- **Secrets:** Indigo opens the stone hand, breaks the geode and lifts the Titan's rib. The sitting giant's hollow shows only by moonlight. Climb towers to spot what you have not found. The lantern stones only glow at night, and keep the cold off. Drinking at the Sky Well makes the sun heat you 15% slower from then on.
- **Journal:** a new **places** page lists every kind (`?` for the ones not found) and the stories heard.
- The first pale bloom now grows 6.5 km out (was 3.2), so the ending can no longer be stumbled on in the first hour.
- `INSTALL_REQUIREMENTS.bat` installs Panda3D 1.10.16 and numpy for the Prototype Lab launch.

Details: `PASS51_DEEP_DESERT_NOTE.txt`. Check: `python tools_pass51_check.py`.

## Pass 50 First Launch

- **Title screen** over the living desert: continue · day N (or begin), new journey, settings, quit. The world waits until you choose.
- **Settings** (from the title or Esc → settings):
  - Display: resolution (native = your monitor, 4K on a 4K screen; or 3840×2160 / 2560×1440 / 1920×1080 / 1600×900 / 1280×720), fullscreen, vsync, anti-aliasing. A window never opens larger than the desktop.
  - Sound: master, music, effects, ambience.
  - Play: mouse sensitivity, invert mouse Y, first-dawn hints.
- **Keys**: rebind every action in game. Click it and press a key (Esc cancels). A key already in use swaps. Esc always stays the menu key.
- **First dawn**: a new journey shows one quiet hint at a time (walk, call Indigo, dig, shade, lift, shells, journal/make/controls). Each hint goes the moment it is done. Indigo looks toward what the hint is about.
- Settings and your keys are saved in the save folder (`%LOCALAPPDATA%\GLITCHED MATRIX\INDIGO GIANT`).
- `--no-title` skips the title.

Details: `PASS50_FIRST_LAUNCH_NOTE.txt`. Check: `python tools_pass50_check.py`.

## Pass 49 Fixes & Balance

- All ten items from the post-Pass-48 review are fixed.
  - The Red Giant fights back when hit while busy.
  - Interrupted meals are cancelled.
  - A resting Red Giant no longer blocks sleep.
  - Finding food and bait no longer scans every branch each frame.
  - Saves are fixed.
  - The journal fits its page, and F1 help is up to date.
- Poisoning a branch now has its own key: **X**. E still smashes.
- Following your tracks, the Red Giant walks at about 1.6 m/s: faster than your walk, slower than your jog.

Details: `PASS49_FIXES_BALANCE_NOTE.txt`. Check: `python tools_pass49_check.py`.

## Pass 48 Living Giants

- With nothing else to do, the Red Giant follows your tracks.
- It gets hungry and plucks blood branches to eat, leaving crumbs that tell you when it was there and which way it went.
- By day it is sneaky when fed: it freezes while you watch it. When hungry or angry it turns aggressive.
- At night the cold drains both giants. They slow down, and when spent they hunch down to rest.
- You get cold at night. Stay close to Indigo, ride it, or sleep curled against it.
- Blood scraps are food for you and Indigo.

Details: `PASS48_LIVING_GIANTS_NOTE.txt`. Check: `python tools_pass48_check.py`.

## Pass 47 The Pale Bloom

- Places lie farther apart, and there are six new kinds: petrified tree, great nest, leaning tower, salt flat, totem poles and a sea-serpent spine.
- The only ending: find the very rare pale bloom (camps, totems and statues point the way), tear it up, and work its pale scraps into a blood branch.
- The Red Giant's favourite food is the blood branch. It comes, eats the poisoned branch, and does not get up again. After that the journey goes on without it.

Details: `PASS47_PALE_BLOOM_NOTE.txt`. Check: `python tools_pass47_check.py`.

## Pass 46 The Wide World

- Hidden places across the whole desert, with nothing pointing at them: skull, arch, oasis, glass field, hoodoos, stone ring, husk, camp, statue and hand.
- Each place is always there, decided by the world seed. Find them to name them and add them to the journal.
- Some hide a cache. At the oasis you can drink, at the stone ring you can rest, and many places give shade.
- No visible edge: fog is total where the built ground ends. Every chunk has a skirt, and ground builds fast enough for full-speed riding.

Details: `PASS46_WIDE_WORLD_NOTE.txt`. Check: `python tools_pass46_check.py`.

## Pass 45 Smooth Giants, Fog & Text

- Characters are GPU-skinned: smooth motion at any frame rate (the giants were 6–12 fps flip-books). Loading is faster and memory use is lower.
- Fog blankets everything, landmarks included, and fades tall things into the sky colour behind them.
- Messages sit at the bottom of the screen, below the player.

Details: `PASS45_ANIMATION_FOG_NOTE.txt`. Check: `python tools_pass45_check.py`.

## Pass 44 Stability, Performance & Look

Same game, with no known bugs and flat performance:
- Every Pass 43 audit item is fixed (B1–B16). Nothing responds while paused or falling asleep.
- Saves now keep: hidden, riding, the held shell, Indigo's mode and the Red Giant's state.
- A save that can't be read is kept aside, never overwritten.
- Frame time stays flat over long journeys (lighter shade proxies, batched footprints, active-only world lists, scraps that expire).
- A new sky: a time-of-day gradient, sun and moon discs, dusk glow and stars.
- The sun lighting was fixed; the ground no longer turns black when you look toward the horizon.

Details: `PASS44_STABILITY_NOTE.txt`. Check: `python tools_pass44_check.py` (add `--long` for the 30-minute soak).

## Pass 43 The Journey Loop

**Launch with `main.py`** (was app.py). An ongoing loop:
- Day and night, with a moving sun and heat that follows it.
- Sleep in a shell at night (Z); it becomes camp.
- Make gear (B): sun cloak, sand wraps, water skin, shoulder canopy.
- Plant blood-branch seeds.
- An endless landmark trail, with a journal (J).
- The journey is saved automatically.

A quiet new HUD shows only what matters. Keys can be rebound in `controls.json`.
Fixed: SHIFT + WASD and the arrow keys. Esc opens a pause menu.
Details: `PASS43_JOURNEY_LOOP_NOTE.txt`. Check: `python tools_pass43_loop_check.py`.

## Pass 42 Journey

Softer dunes (median slope 5 deg, was 17), level ground under landmarks, shells, finds
and plants, no glowing markers: landmarks are hazy silhouettes on the horizon and Indigo
turns to look at what it senses. Everything is spread wider (landmarks out to ~1.1 km).
Details: `PASS42_JOURNEY_NOTE.txt`. Check: `python tools_pass42_world_check.py`.

## Pass 41 Controls

WASD is now exact: characters walk where the keys point (camera-relative, diagonals too)
and **face** the way they walk (W used to make the human moonwalk toward the camera).
Actors are no longer mirror images. The giant pivots and slows for sharp turns.
**Hold the right mouse button** to orbit the camera. Details: `PASS41_CONTROLS_NOTE.txt`.
Check: `python tools_pass41_controls_check.py`.

## Pass 40 Sound

3D footsteps, roars and gesture sounds, desert ambience, and music that fades in with
the fighting and drifts in as ambient cues. **Every sound is a replaceable file** in
`audio/`; see `audio/README_AUDIO.txt`. Effects must be **mono** to be positioned in 3D.
Details: `PASS40_SOUND_NOTE.txt`. **M** mutes the music. Check: `python tools_pass40_check.py`.

## Pass 39 The Desert

Heat and shade, finds the giant senses from afar, a non-linear landmark trail, and
sea-shell shelters the Red Giant tries to overturn.  Full details and tuning:
`PASS39_DESERT_NOTE.txt`.

| Key | Action |
|---|---|
| 5 / wheel lower-right | SHADE ME — the giant keeps its shadow over you |
| Q / wheel upper-left | WHISTLE — works from inside a shell; Indigo runs in to fight |
| E / hold E | crawl into / out of a shell · dig · study a landmark · patch a shell · smash a branch |
| G | eat (water gourd when hot, moss pods otherwise) |
| Giant: E | lift / set down a shell |

About 5 minutes of unbroken sun kills; riding is full sun too.
Check: `python tools_pass39_check.py`.

## Pass 38 Companion & Survival

A survival game between a small human and the Indigo Giant — Fantastic Planet's
scale with Journey's wordless companionship.  Full details and controls:
`PASS38_COMPANION_SURVIVAL_NOTE.txt`.

## Quick controls (human)

| Key | Action |
|---|---|
| 1 / 2 / 3 / 4 | COME / STAY / LIFT ME (again: SET ME DOWN) / GO THERE (mouse point) |
| Middle mouse (hold) | gesture wheel — flick and release |
| Hold E | smash a blood branch → 4 scraps |
| T / Y | give scraps to the giant / take them back |
| Riding: W, click, TAB | walk where you look, go to clicked point, take the reins |
| Giant: F, K | punch or smash a branch, kneel |

## What Pass 38 adds

* Companion AI: follow, stay, go there, lift onto shoulder, carry, set down.
* Blood branches: heal (limited sap), smash into scraps, regrow after 4 min.
* Inventories: human 12 scraps, giant 60.
* Red Giant as an ongoing boss: scared off at low health, knocked out at zero,
  lurks and returns sooner each time.
* Fixes: giant kneel while player-controlled, colour-scale in the sketch shader,
  a punch cut short by the end of a defence no longer freezes the giant.

Check: `python tools_pass38_check.py` (headless, prints PASS/FAIL).

## Pass 37 Performance & Stability

## Play

- Windows: double-click `RUN_INDIGO_GIANT.bat` (installs `requirements.txt` on first run if needed).
- Python: `python app.py` (add `--fps` to show the frame counter; `F3` toggles it in game).
- If it won't start: `RUN_INDIGO_DIAGNOSTIC.bat` writes `indigo_diagnostic.log`.

## Why Pass 36 ran so badly

About 180 ms of Python work every frame, before the GPU even started:

1. **Hidden "proxy" shadows were rebuilt every frame.** The visible shadow is the real
   shadow map, but the old stylised shadow proxies (kept only for a future shade query)
   were still rebuilt 30 times a second. Each rebuild asked for 30 joint positions per
   actor, and each lookup re-solved the whole 67-node glTF skeleton in numpy, costing about
   4 ms. That's ~90 solves per refresh, and 60 % of every frame.
2. **Startup took 30–40 s.** Every animation frame of every actor was built one vertex
   and one triangle at a time in Python, and the 7.6 MB GLB was re-read for each clip.
3. **Terrain streaming hitched.** Each new chunk called the noise function five times
   per vertex, costing about 12–25 ms per chunk as you walked.
4. **Uncapped frame rate** (`sync-video false`) let frame times swing and pinned the GPU.
5. **Shader path on Windows:** `indigo_diagnostic.log` shows "Could not find shader
   file". Panda3D was given a raw Windows path.

## What Pass 37 changed (nothing about gameplay)

- Joint positions are baked with each animation frame and read from a table,
  interpolated between frames. Footprints still use the exact skeleton solve (a
  couple of times per second), so they land exactly where Pass 36 put them.
- Hidden proxy shadows update only their shade-query data; no geometry is rebuilt
  while they are hidden. `giant_shadow_contains()` still works.
- Animation baking writes whole vertex blocks at once, shares one triangle list across
  all frames and actors, and parses the GLB once. The meshes are byte-identical to Pass 36.
- Terrain chunks sample each height once and write vertices in one block. The output is
  byte-identical to Pass 36 (same chunk signatures).
- Vsync is on (use `--no-vsync` for benchmarking). There is a frame counter on `F3` / `--fps`.
- Shader files load through `Filename.fromOsSpecific` (Windows-safe paths).
- Footprints are capped at 240 (the oldest fade out first), and the temporary baking
  cache (~120 MB) is freed after load.

Measured here with `python perf_probe.py` (game logic per frame, excluding rendering):

| Route | Pass 36 | Pass 37 |
|---|---|---|
| Startup | 30 s | 3.4 s |
| Human walk | 180 ms | 2.2 ms |
| Human sprint | 147 ms | 2.4 ms |
| Giant jog (225 chunks) | 188 ms | 2.5 ms |

A rendered frame compared against Pass 36 differs by at most 1/255 per colour channel (0 pixels differ by more than 2).
Health, damage, AI, speeds, cameras, controls, animations and retry rules are unchanged.

---


## Pass 30 Human Retry Flow

## Scope
One task only:
- remove the human soft-lock after a successful Red Giant takedown
- preserve Red stomp damage, Red knockout/flee, Indigo defense/melee, camera, shadows, terrain, and prior movement systems

No eating, burrows, loot, stealth, object searching, checkpoints, save-state logic, or lives system was added.

## Workflow authority
The project requires one main target per pass, previous-task recheck, and actual player-facing improvement. A downed human that can no longer move had become a basic-playability dead end, so recovery took priority over another combat feature.

## Reference
Panda3D 1.10 event handling uses `accept()` to bind key events to application methods. Pass 30 binds `enter` to the local retry handler using that normal engine path.

## What changed
- When the human is downed, the normal compact control HUD changes to a clear `HUMAN DOWNED` state.
- A compact `[ENTER] RETRY` prompt appears.
- Pressing ENTER performs a local encounter retry without restarting Panda3D or rebuilding the terrain world.
- Human returns to its original safe start beside the Indigo Giant with full health and idle control.
- Indigo Giant returns to its encounter start with full health and cleared melee/kneel motion state.
- Red Giant returns to its original encounter spawn with full health and cleared hunt/melee/knockout/recovery/flee state.
- Control returns to the human and the human third-person camera is immediately restored.

## Why this is intentionally minimal
This is a prototype retry, not a finalized death/respawn design. It prevents a soft-lock while leaving larger game rules—lives, checkpoints, saves, being eaten, rescue, etc.—for later explicit passes.

## Smoke proof
`smoke_human_retry.py` verifies:
- real stomp damage downs the human
- downed prompt is visible
- disturbed giant/Red state is reset by retry
- human, Indigo Giant, and Red Giant return to their encounter starts
- all three health pools restore to 100
- Red state returns to idle
- control and camera return to the human

Screenshots:
- `screenshots/smoke/pass30_human_downed_retry_prompt.png`
- `screenshots/smoke/pass30_retry_restored.png`

## Regression proof
Rechecked on this branch:
- Red stomp damage
- Red Giant 300-second knockout -> recovery -> flee
- giant-vs-giant melee / Indigo defense
- human/Indigo camera and control profiles

## Open limitation
The retry is intentionally a local encounter reset. It is not yet a lore-level respawn, save/checkpoint system, or final game-over flow.
