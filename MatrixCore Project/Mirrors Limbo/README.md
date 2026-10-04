# Mirror's Limbo — Pass 151 Linked Worlds

DreamCatcher and Andrew's Nightmare are now part of Mirror's Limbo. They live inside this
folder (`DreamCatcher/` and `DreamCatcher/modes/andrews_nightmare/`) and share one runtime
package, `gx_common/`. Keep the folder together; nothing else in the Prototype Lab is needed.

## Route

- **Limbo → DreamCatcher:** after the first return from Alt Limbo, face the roadside TV, press **E**, choose **DREAMCATCHER**.
- **DreamCatcher → Andrew's Nightmare:** at the bedroom TV press **E**, **Left/Right** to CH 07 DREAM, press **T**.
- **Andrew → DreamCatcher:** **Esc** then **Q** / RETURN TO DREAMCATCHER. After breaking the intercept, **Q** works without pausing. The Null-Layer disconnect wakes you automatically.
- **DreamCatcher → Limbo:** **Esc** → RETURN TO MIRROR'S LIMBO. After the attic finale, **Esc** (or waiting 10 s) wakes you in Limbo.
- **QUIT** or closing a window still exits to the desktop.

## What carries between worlds

- **Settings.** Limbo's settings are the single source: mouse sensitivity, invert-Y, master volume, display mode, resolution and v-sync. FOV follows Limbo as an offset, so each world keeps its designed look (Limbo 70 → DreamCatcher 74 → Andrew 86 at defaults). Changing these inside DreamCatcher or Andrew writes back to Limbo.
- **DreamCatcher house progress.** Task progress, props, TV state and warnings are saved when you leave the house (to Andrew, to Limbo or to the desktop) and restored when you come back. Finishing the attic finale clears it, so the next visit is a fresh house.
- **Completions.** Finishing DreamCatcher or Andrew's Nightmare is recorded in `linked_worlds.json` next to the Limbo saves. The TV menu shows it (`HOUSE CLEARED // NIGHTMARE BROKEN / DISCONNECTED`).

## Switching

Each world is still its own Panda3D process. The current window stays up behind a black
loading cover until the next world reports ready, then it exits. Exclusive fullscreen
minimizes instead. If the next world fails to start, the current one is restored.
Linked worlds are only offered from standalone Limbo. Inside HoloVerse the TV says so,
because switching would close the HoloVerse host.

## QA

- `GX_TRAVEL_QA=1 GX_TRAVEL_QA_PLAN=<plan.json>` drives the full chain (see `gx_common/travel_qa.py`). The verified chain is Limbo → DreamCatcher → Andrew (complete) → DreamCatcher (restored house, finale) → Limbo (completions shown).

# Mirror's Limbo — Pass 149 First-Return TV + Stair Landing Recovery

Pass 149 changes two player-facing progression/traversal problems without expanding the core feature set.

## Progression

A brand-new game now begins with **no road TV at all**. Before the player has genuinely returned from Alt Limbo there is no TV mesh, collision, practical-light anchor, movie/audio owner, semantic interaction anchor, or E target. The first legitimate Alt-Limbo return (`house_return` or `fear_return`) permanently discovers and constructs the TV. Reloading the first exterior, restarting the game, or a non-return cycle event does not unlock it.

The discovery is saved as `tv_discovered` in progress schema v12. Older saves migrate safely: if they already have `limbo_cycle_count >= 1`, the TV remains discovered.

This deliberately moves the TV/Framework investigation later in the loop so the endgame path is not sitting beside the initial spawn.

## Stair / patio recovery

The visible three-tread stairs remain presentation geometry. Pass 148 introduced a continuous semantic ramp, but its support reached full porch height exactly at the patio edge while deck support intentionally shrank inward. A player could stop on that narrow seam and fall, and descending could lower the player's feet while the capsule still overlapped the porch face.

Pass 149 changes the traversal authority:

- the ramp reaches full 0.70 m porch height **before** the player's capsule overlaps the patio front face;
- a flat top landing then continues beneath the patio edge and 0.38 m into the deck;
- the top landing is 0.80 m long in total, greater than the player diameter;
- the ramp is slightly wider (4.30 m) while remaining within the visible stair composition;
- normal and mirrored ramps derive from the same house anchors;
- F10 still shows red BoxSolid collision and cyan walk-ramp authority.

## Controls

- **WASD** walk
- **Mouse** look
- **Shift** sprint
- **Space** jump
- **E** static doors / TV / contextual interaction
- **F** FEAR / break VOID chase
- **Esc** pause/settings
- **F1** help
- **F10** collision debug with `--developer-shortcuts`

## QA

- `--pass149-test --no-audio` — TV discovery contract + 24 stair/deck seam dwells + inherited 120-route stair matrix
- `--pass149-capture --capture-size 1080p --no-audio` — matched first-Limbo/first-return TV frames + stair landing clean/collision views
- `--mirror-test --no-audio` — inherited Mirror/VOID/TV-world regression
- `--smoke-test --no-audio` — fresh runtime construction smoke

Panda3D 1.10.16 is the runtime authority for this pass.
