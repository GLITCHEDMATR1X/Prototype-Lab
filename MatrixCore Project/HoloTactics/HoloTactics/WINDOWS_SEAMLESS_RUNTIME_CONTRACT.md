# HoloTactics Pass 16 — HoloVerse Windows Seamless Runtime Contract

## Authority

HoloTactics remains the real game. `main.py`, `holotactics_core.py`, the five-sector route, procedural tactical actors, ability loot, UI, SFX and music remain source authority.

HoloVerse only owns the outer runtime when linked natively.

## Native linked runtime

| Runtime concern | Authority while linked |
|---|---|
| Windows OS window | HoloVerse existing window |
| ShowBase | HoloVerse existing ShowBase |
| Panda frame loop | HoloVerse |
| HoloTactics presentation update | `HoloTacticsApp.hosted_step()` from host frame |
| Camera/lens during play | Real HoloTactics camera setup, restored to HoloVerse on exit |
| 3D scene | Real HoloTactics `scene_root` |
| HUD | Real HoloTactics `hud_root` |
| UI scale / HUD visibility | HoloVerse settings |
| Fullscreen / borderless / VSync | Existing HoloVerse window; HoloTactics cannot reopen it |
| Graphics quality | HoloVerse setting applied only to HoloTactics scene subtree |
| Source SFX/music | HoloTactics, using HoloVerse master/music/SFX mix values |
| Generic HoloVerse native music | Suppressed while HoloTactics owns source audio |
| Cursor | Visible; manifest declares no mouse capture |
| TAB | Immediate return to HoloVerse |
| ESC | Shared HoloVerse pause/menu and Return to HoloVerse path |

## Input parity

The linked game receives the real standalone actions:

- WASD / arrows — target cursor
- Enter / Space — start/select/continue
- LMB — target/select/move
- RMB / F — attack
- M — move
- Q — Gleebs Patch Pulse
- X — one-shot ability
- E — end turn
- N / C — continue journey
- H — HoloTactics HUD
- V — SFX toggle
- B — music toggle
- R — reset to title

TAB is reserved by HoloVerse while linked. ESC remains host menu authority.

## Standalone / compatibility fallback

Standalone `python main.py` still creates its own ShowBase normally.

When HoloVerse must compatibility-launch instead of native-mount, the external process consumes the HoloVerse settings/environment contract for:

- width / height
- window X/Y origin
- fullscreen / borderless mode
- VSync
- FPS target metadata
- HUD visibility / UI scale
- graphics quality metadata
- master / music / SFX / ambience volumes
- mouse, controller and display metadata

No host placeholder tactical board exists.
