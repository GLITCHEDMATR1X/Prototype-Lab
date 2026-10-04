# The Indigo Giant

Orbit, a small human, crosses an endless pale desert with Nyx, the Indigo Giant, a silent
companion twenty metres tall. The planet is REDACTED: its name was scratched from every chart
by those who left it, and it is dying. It burns by day and freezes by night, and Crimson,
a red giant, hunts them both. Panda3D 1.10.16, Python 3.10–3.13, Windows 11.
Recommended: RTX 2070, 16 GB RAM, 4K monitor (1080p works too).

The history of every pass is in `CHANGELOG.md`.


## Run it

- **From the GLITCHED MATRIX Prototype Lab:** launch it as usual.
- **From HoloVerse:** Gleebs > Dimension Archive > *The Indigo Giant* (the folder must sit beside HoloVerse in Prototype Lab). It opens in HoloVerse's window. **TAB** takes you back to HoloVerse at any time, so *be Nyx / be Orbit* is on **V** there. "Quit" becomes *return to HoloVerse*, and your journey is saved. See *In HoloVerse* below.
- **Double-click `RUN_INDIGO_GIANT.bat`:** it installs what is missing on first run.
- **Missing modules?** Run `INSTALL_REQUIREMENTS.bat` once. It finds a 64-bit Python and installs Panda3D 1.10.16 and numpy, then writes `install_requirements_last.txt`.
- **From a terminal:** `python main.py`

| Option | Does |
|---|---|
| `--no-title` | skip the title screen |
| `--new` | start a new journey (the old save is kept as a backup) |
| `--fps` | show the frame-rate meter (F3 toggles it) |
| `--no-vsync` | uncapped frame rate, for benchmarking |

**Saves, settings and your keys** live in `%LOCALAPPDATA%\GLITCHED MATRIX\INDIGO GIANT\`. The journey is saved automatically; F5 saves now.

**Settings** (title screen, or Esc > settings):
- Resolution: native, which is 4K on a 4K screen, or 3840×2160 down to 1280×720.
- Fullscreen, vsync, anti-aliasing.
- Volumes, mouse sensitivity, invert Y, first-dawn hints.
- Every key can be rebound in game.


## Controls (defaults — change them in Esc > settings > keys)

| You (Orbit) | Key | Nyx | Key |
|---|---|---|---|
| walk | W A S D | come | 1 |
| jog / sprint | Shift / Shift + Ctrl | stay | 2 |
| look around, and up | hold right mouse · arrows | lift me / set me down | 3 |
| jump · crouch | Space · C | go there (where you point) | 4 |
| use · hold to dig, search, climb, read | E | shade me | 5 |
| eat / drink | G | whistle (it runs to fight) | Q |
| sleep (night: in a shell or by Nyx) | Z | gesture wheel | hold middle mouse |
| poison a blood branch | X | be Nyx / be Orbit | Tab |
| give to / take from Nyx | T / Y | Nyx: punch (tap) · hammer blow (hold, let go) | left click or F |
| reset camera | R | Nyx: kneel | K |
| make things · journal · all controls | B · J · F1 | wake Nyx when it is down | tap E ×3 beside it |
| menu · wake after falling | Esc · Enter | quick save · music · fps | F5 · M · F3 |

In HoloVerse, Tab is HoloVerse's (back to HoloVerse), so *be Nyx / be Orbit* uses V for that visit.


## How the journey works

- **Heat and cold:**
  - By day the sun heats you. About 5 minutes of unbroken sun kills.
  - Shade cools you: Nyx's shadow (press 5), shells, landmarks and places.
  - **Shells** are big enough to walk into. Walk in through the arched mouth of an unbroken shell (or press E at its mouth) to cool off, recover and hide from Crimson, awake, any time of day; walk out the same way. A cracked shell is only shade until you patch it (hold E: 3 scraps and 1 resin).
  - By night the cold does the same. Keep warm beside Nyx, by riding it, among lantern stones, by eating a blood scrap, or by sleeping.
- **Food and making:**
  - Blood branches heal you and feed both giants. Smash them into scraps (hold E).
  - Dig finds and search places for materials.
  - Make a sun cloak, sand wraps, a water skin and a shoulder canopy (B).
- **Nyx (the Indigo Giant):**
  - It follows, carries you, shades you, senses places and fights Crimson.
  - It gets tired and cold at night.
  - It has fight stamina. Knocked out, it waits for you to wake it (tap E three times beside it), or it gets up at dawn.
  - **At night it glows** indigo. The glow shields it (hits cost it less, the cold drains it less) and its light warms you up to ~24 m away.
  - Hold E beside it at night to **take some of its glow**. While you carry it:
    - breath: effort costs less
    - work: you dig, search and smash faster
    - health: you heal slowly, and heat, cold and blows hurt you less
  - The glow drains as you spend breath by day and fades at once if you run out.
- **Crimson (the red giant):**
  - It follows your tracks and eats blood branches, leaving crumbs as clues.
  - By day it is sneaky when fed and aggressive when hungry or angry. At night it rests.
  - Knock it out and it lies down for 2.5 minutes, then has lost you for a whole day before it finds your trail again.
  - With pale scraps you can feed it poison while it lies there, to weaken it.
  - **At night it burns crimson.** Come within ~24 m and its light swells into a crimson wave (a ring on the sand shows how far it reaches). Get out of the ring before it bursts, or be thrown down and hurt; an unbroken shell or Nyx's shoulder keeps you safe. Resting or knocked out at night, it is warded: blows glance off and it will not take poison. Beat it by day.
- **The desert:**
  - An endless trail of landmarks.
  - Hidden places in tiers: common near the start, uncommon from ~1.6 km, rare from ~3.4 km.
  - Four legends far out (8–18 km), found by following the stories other places tell.
  - Lantern stones only show at night. Towers let you look out.
  - The journal (J) has a *places* page with every kind of place, and the stories you have heard.
  - **Etchings:** 14 standing stones cut with glowing marks, from ~60 m out to ~9.4 km. Hold E beside one to read it. Together they tell who Nyx, Orbit and Crimson are, why this world is called REDACTED, and who might come for them. At night they glow and can be seen from ~250 m. J > *notes* keeps the ones you have read.
- **The ending:**
  - Find the rare pale bloom (6.5 km out, hinted by far camps, painted poles and sitting giants), tear it up, work its scraps into a blood branch (X), and let Crimson eat it. Crimson is strong, but not wise: it eats what is bitter because it is there.
  - When Crimson has lain down for good, the sky answers. **Gleebs** comes down in a beam of light, as a hologram, to take Nyx and Orbit away from this dying world. It waits for as long as you like.
  - Walk into its light with Nyx beside you and hold E to leave REDACTED. Gleebs will not take one who is alone. Crimson stays behind.
- **Measured length:** finding every kind of place takes a rider about 17–22 hours, a mixed player 22–28 and a walker on foot 35–43 (`.dev/tools/discovery_probe.py`, Pass 58 speeds). Real players take longer.


## In HoloVerse

In the lore, HoloVerse is the present, and each dimension is an archive of the past that Gleebs brought with him. This one is the record of Nyx and Orbit on REDACTED, before Gleebs gave them their places in HoloVerse (Nyx in the Hills of Life, Orbit as the HoloSpace flight guide).

- HoloVerse finds the game through `holoverse/holoverse_dimension.json` (a native responder) and mounts it in the same window through `holoverse_native_adapter.py`. The game is the same code in both places. `indigo_giant/holoverse_host.py` holds everything that changes while hosted.
- The window, TAB and the audio device belong to HoloVerse. The game keeps its own saves, settings and keys (in `%LOCALAPPDATA%`, as always).
- On leaving, HoloVerse keeps a small result: day, etchings read, whether Crimson has fallen, and whether Nyx and Orbit have left with Gleebs. Once they have, Nyx and Orbit mention it when you talk to them in HoloVerse.
- Older HoloVerse builds without the catalog entry: use LINK SIMULATION and pick this folder's `main.py`.


## What's where

```
Indigo Giant/
  main.py                   start here (the Prototype Lab cabinet and RUN_INDIGO_GIANT.bat run it)
  RUN_INDIGO_GIANT.bat      double-click to play (installs what is missing)
  INSTALL_REQUIREMENTS.bat  installs Panda3D 1.10.16 and numpy
  requirements.txt
  controls.json             default keys, editable by hand (your in-game changes live with your saves)
  cover.png                 the picture on the Lab cabinet
  icon.png                  the picture in HoloVerse's Dimension Archive
  holoverse_native_adapter.py  how HoloVerse mounts the game in its window
  holoverse/                HoloVerse responder: holoverse_dimension.json, identity.json, README.txt
  dimension.json            the archive's title, symbol and colour for HoloVerse
  indigo_giant/             the game (a Python package)
  assets/ audio/ shaders/ ui/     models, sounds, shaders, fonts
  docs/                     pass notes, screenshots, the animation map
  .dev/                     checks and tools (not needed to play; the Lab cabinet does not list them)
```

**The game package** (`indigo_giant/`):

| File | What it is |
|---|---|
| `app.py` | the game: terrain streaming, characters, camera, movement, combat, Crimson's hunt; `main()` |
| `paths.py` | where the game's files are (the one place that knows) |
| `holoverse_host.py` | playing inside HoloVerse: borrowing its window, TAB, leaving cleanly, the result HoloVerse keeps |
| `locomotion.py` | walk cycles driven by the ground covered (feet never slide); gait speeds |
| `survival.py` | companion AI (follow, carry, shade, gestures), bags |
| `desert.py`, `desert_world.py`, `desert_geom.py` | heat, stamina, finds, shells, landmarks |
| `places.py`, `places_geom.py` | hidden places, tiers, legends, rumours, secrets |
| `wild.py` | the giants' lives: hunger, mood, tracks, night, cold |
| `fight.py` | giant stamina, knock-outs, waking Nyx, Crimson's calm day, poison, fighting as Nyx |
| `glow.py` | Nyx's night glow, and the glow you can carry |
| `crimson.py` | Crimson's powers at night: its wave and its ward |
| `endgame.py` | the pale bloom and Crimson's last meal |
| `lore.py` | the etchings: 14 stones of lore across the desert, and the journal's notes page |
| `gleebs.py` | the end: the Gleebs hologram (the Utopia Vision model in `assets/gleebs/`), its beam, leaving REDACTED |
| `journey.py`, `daycycle.py`, `flora.py`, `sky.py` | making, journal, day/night, blood branches, sky |
| `hud.py`, `frontend.py`, `teach.py`, `settings.py`, `controls.py` | HUD and panels, title and settings, first-dawn hints, display and keys |
| `audio.py` | 3D sound and music (every sound is a replaceable file — see `audio/README_AUDIO.txt`) |
| `savegame.py` | saves (atomic, with a backup; a damaged save is kept aside) |
| `skinned_actor.py`, `gltf_idle.py` | GPU-skinned characters |

The modules import each other relatively (`from . import desert`), so the package can be dropped into a bigger project without its module names colliding.

**Checks and tools** (`.dev/`):
- `.dev\RUN_CHECKS.bat` runs every check and prints one summary. You can also run `python .dev/run_checks.py pass61` for just one. Each check starts the game without a window and prints PASS/FAIL lines.
- `.dev\RUN_DIAGNOSTIC.bat` checks every required file and library, then starts the game and logs everything to `.dev/diagnostic.log`. Send that file back if the game will not start.
- `python .dev/checks/pass44.py --soak-only` runs a 30-minute performance soak.
- `python .dev/tools/playthrough.py` has a scripted player live three in-game days with every game task running, and reports errors, stuck states, frame times and whether the save reloads.
- `python .dev/tools/discovery_probe.py` measures how long the desert takes to discover.
- `python .dev/tools/make_placeholder_audio.py` rebuilds the placeholder sounds. It never overwrites your own.
