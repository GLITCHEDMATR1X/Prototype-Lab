# HoloVerse UI Authority

## Current rule

`data/HoloVerse/main.py` is the dominant HoloVerse UI authority.

All shared menu, pause, MatrixCore, Dimension Gates, transition, prompt, and parent-owned HUD behavior should be treated as belonging to the root HoloVerse app unless a later pass explicitly moves it into a shared UI module.

## Why this file exists

HoloVerse currently has UI/HUD code spread across root `main.py`, in-world runtimes, and standalone/native Dimension modes. HoloCore is now external under `MatrixCore Project/HoloCore` and owns only its local native-dimension prompts while mounted. This document and the adjacent manifest give future passes one scan-friendly place to check before changing HUD behavior.

## Ownership categories

### Root authority

- Root MatrixCore / Observatory UI
- Shared pause/menu overlay
- Shared Dimension Gates menu
- Transition overlay
- Parent-owned ESC behavior
- Player-facing text sanitation
- No-path / no-debug display policy


### Vector Arena native-dimension UI

Vector Arena is an external MatrixCore reality. During a native mount, HoloVerse exposes no gameplay HUD over the arena and owns only TAB return. Vector Arena owns its local combat HUD, H help toggle, between-set mutation chooser, and ESC pause overlay. The pause/help overlays are modal/toggled and must not occupy gameplay space when inactive.

### HoloCore external-dimension UI

HoloCore is not a HoloVerse sub-hub. Its project stays under `MatrixCore Project/HoloCore` and mounts through its folder-local native adapter. HoloCore may own local world/interact/help prompts while active; HoloVerse owns the shared window lifecycle, TAB return, host pause/menu state, and restoration after the dimension exits.

### In-world runtime UI

In-world runtimes may keep minimal contextual HUD elements temporarily. Future passes should replace permanent panels with state reports into root UI.

### Hosted standalone mode UI

Standalone Dimension modes launched through `holoverse_entry.py` wrappers should prefer parent-owned ESC/menu/return behavior. Their original gameplay HUD can stay for now, but wrappers should set clear environment flags so those modes can eventually hide local HUD when parent UI is available.

### Pygame mode UI

Pygame modes such as Vector Wars cannot directly share Panda3D DirectGui widgets. Their wrappers should still obey shared sizing, ESC return, and parent menu contracts. Combat-specific Pygame HUD should be minimized later.

## Future target

Create these real modules gradually:

```text
data/HoloVerse/ui/theme.py
data/HoloVerse/ui/universal_hud.py
data/HoloVerse/ui/universal_menu.py
data/HoloVerse/ui/gates_panel.py
data/HoloVerse/ui/prompt_panel.py
data/HoloVerse/ui/pause_overlay.py
data/HoloVerse/ui/mode_contract.py
```

Do not move everything at once. First make modes report state to the root authority, then retire duplicate panels one by one.

## Edit rule

Before editing HUD/UI in a mode, check:

```text
data/HoloVerse/ui/ui_manifest.json
```

That file groups known UI owners by category so changes do not require scanning the entire repo.


## Pass 277 — Linked dimension HUD cleanup

HoloVerse no longer draws a host-owned MODE / EXPERIMENT status strip or EXIT button over native linked realities. Native dimensions own their visible gameplay HUD. TAB remains the universal immediate return to HoloVerse. ESC remains the normal HoloVerse pause/menu surface; while a native dimension is active that menu exposes RETURN TO HOLOVERSE. Temporary full-screen transition/fade surfaces are allowed because they do not remain over gameplay.
