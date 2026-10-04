# Afterlife of IO — Pass 147 Mode Hub

Current source-package authority for **Afterlife of IO**.

Pass 147 turns Afterlife of IO into the hub for the Prototype Lab modes. Everything from Pass 146 (Campaign Integrity) is unchanged.

## Modes (title screen → MODES)

Modes unlock from campaign progress in any manual save slot, and stay unlocked once earned:

| Mode | Unlocks when | What it is |
|---|---|---|
| HEX CONTRACT | 2 Memory Guardians defeated | Guild contract tactics |
| GHOST SIGNAL | 4 Memory Guardians defeated | City network infiltration |
| ENTROPY | Campaign complete (endgame) | Six dying systems, six archives |

- A mode opens **in the same window** (no second window, no flash) and keeps your window size / fullscreen choice.
- Quitting a mode — its EXIT / QUIT / DISCONNECT option, which now reads **RETURN TO AFTERLIFE** — brings you back to the Afterlife title.
- Defeating a Guardian that crosses a threshold shows `MODE UNLOCKED: …` in-game immediately.
- If a mode ever crashes, Afterlife stays up and shows a notice on the title; details go to `startup.log`.

Mode code lives in `modes/<Mode>` and is loaded by `mode_host.py`. Each mode can still be launched on its own from its folder.

### Entropy × DreamCrawler ruin dives

In Entropy, pressing `E` at the marked archive ruin sends the nine-bot DreamCrawler team underground (in the same window):

1. Floor 1 — find the stairs down.
2. Floor 2 — the archive vault; a WARDEN crawler guards the Data Fragment. Anyone on the team can grab it.
3. Regroup at the **ASCENT LINE** to climb out, then carry the fragment back to the ship and secure it at CARGO.

The collapse clock runs at **1/4 speed** underground and freezes while the dive is paused. `Esc` pauses and offers a retreat; a retreat or a downed diver leaves the fragment below and you can dive again while the system survives.

## In HoloVerse

Afterlife of IO is also an archive in HoloVerse's Dimension Archive (Gleebs > Dimension Archive > *Afterlife of IO*). In the lore it is IO's past: the afterlife it escaped with the civilization archives Gleebs needed, before IO became HoloVerse's HoloForge guide.

- HoloVerse 282.50+ finds it on its own anywhere inside Prototype Lab or MatrixCore Project (`holoverse/holoverse_dimension.json`, with a fixed id in `holoverse/identity.json`).
- It opens in **its own window** (Afterlife is pygame, HoloVerse is Panda3D), with your usual saves and settings.
- While launched from HoloVerse, *Quit* and *Quit to Desktop* read **RETURN TO HOLOVERSE**. Choosing it brings you back to HoloVerse.
- On the way out it tells HoloVerse how many Memory Guardians are defeated and whether the campaign is complete. Once it is, IO remembers its afterlife when you talk to it in HoloVerse.
- `holoverse_link.py` holds all of this; run on its own, nothing changes. Check it with `python tools/verify_holoverse_link.py`.

## Pass 146 recap

- All seven Memory Guardians keep independent encounter memory; every first defeat manifests a Future Shrine/Obelisk.
- Recovering all seven archives and returning to **Gleebs → Current Mission** plays the ending and stores `campaign_complete`.
- Manual save schema **v5** (v4 slots still load).

## Core keyboard / mouse controls

- `WASD` / arrows — move
- `Shift` — sprint
- `Space` — hop
- `E` — interact / talk / use; near a powered Core, open Machine Workshop
- `I` — open IO Inventory
- `L` — Archive
- `F1` — Continuity Thread + contextual help
- `Esc` — pause / back
- Mouse wheel or `+` / `-` — zoom
- `Tab` — launch / recall Lantern Projection when learned
- `R` — Causal Resonance when learned
- `Q` — Veil Ward when learned

### Machines

- `1–6` — place the corresponding MAIN MACHINE KIT part near IO
- `T` — optional Machine Focus
- `[` / `]` — cycle owned machine parts
- Hold LMB on a placed part — telekinetically move it
- `Ctrl` + LMB — flip a placed part horizontally
- RMB — reclaim a placed part into IO's machine inventory
- `` ` `` / `F10` — developer console

The six-slot hotbar is quick access only. `I` opens the broader inventory.

## Pause / Settings

`Esc` opens Pause:

1. Resume
2. Save Game
3. Load Game
4. Settings
5. Quit to Desktop

Title screen: Continue, New Game, Load Game, **Modes**, Settings, Quit.

Settings contains **Controls**, Audio, Display/presentation options, guidance, fullscreen, and accessibility/presentation choices already supported by the game.

## Controller

- Left stick — move
- Left-stick click — sprint toggle
- `A` — interact / confirm
- `B` — back
- `X` — hop / context action
- View / Back — Archive
- Right-stick click — Inventory during exploration; flip while in Machine Focus
- D-pad Up — Help
- Menu / Start — Pause
- `Y` — Lantern Projection
- `LB` — Veil Ward
- `RB` — Causal Resonance

## Campaign contract

Seven stationary Memory Guardians exist in the Beginning/Past. They may be challenged in nonlinear order. Every first defeat must produce a persistent corresponding monument in the Present/Future. The first three Shrines retain their established progression effects; the remaining four preserve the recovered causal record and support Echo rematches.

When all seven archives have been recovered, returning to Gleebs and reading **Current Mission** resolves the campaign rather than returning to an unfinished dialogue loop. Completion is stored when the current manual slot is known; otherwise it is included the next time the player manually saves.

## Save compatibility

- Current manual save schema: **v5**.
- Existing v4 slots load through migration.
- The original First Witness `entity` block is retained for compatibility while v5 also stores all seven Guardians under `entity_states`.
- New v5 causality data stores the four additional Future Shrines and campaign completion.

## Launch

Windows:

```text
RUN_GAME.bat
```

Direct Python:

```text
python main.py
```

Install dependencies if required:

```text
INSTALL_DEPENDENCIES.bat
```

Verify the mode hub headlessly:

```text
python tools/verify_pass147_mode_hub.py
```

Native Windows remains the final acceptance lane for Pygame rendering, controller feel, cursor behavior, and audible loop quality.
