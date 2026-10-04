# Vector Wars Pass 22 — Display Surface Authority Repair

Status: CANDIDATE — Windows runtime acceptance required.

## Trigger
Player runtime screenshot from Pass 21 showed the valid startup frame remaining onscreen indefinitely while combat SFX could be heard. That proves the process/simulation can remain alive while gameplay presentation is not replacing the startup surface.

## Single task
Repair the OS display/presentation authority. No gameplay, balance, campaign, audio-content, save, or HoloVerse feature expansion.

## Root-risk addressed
Vector Wars cached the display Surface and only treated legacy VIDEORESIZE as resize authority. pygame-ce 2 also exposes WINDOWSIZECHANGED, WINDOWRESIZED, WINDOWMAXIMIZED and WINDOWRESTORED for window-manager changes. A maximized Windows window can therefore change physical presentation geometry outside the old VIDEORESIZE path.

## Changes
- APP_VERSION -> 0.9.0-pass22-display-surface-authority.
- Startup frame renders through pygame.display.get_surface() when available.
- Gameplay presentation reacquires pygame.display.get_surface() every frame.
- Actual client size is read from the current display Surface before presentation.
- 16:9 viewport is recomputed whenever the physical client size changed.
- WINDOWSIZECHANGED / WINDOWRESIZED / WINDOWMAXIMIZED / WINDOWRESTORED are handled alongside VIDEORESIZE.
- SDL2 WINDOW* resize notifications no longer call set_mode() redundantly.
- The fallback _sdl2 maximize call is skipped when WINDOWMAXIMIZED was already requested at set_mode().
- Previous Pass 20 startup-frame and Pass 21 startup-clock fixes are preserved.

## Regression authority
29/29 regression scripts pass on source tree.
Fresh-package replay required and performed before delivery.

## REJECT IF
- loading frame remains after combat audio begins;
- gameplay appears but is cropped/off-center after maximize/resize;
- F11 or resize breaks presentation;
- startup crashes/exits;
- previous campaign/control regressions return.

## Reference check
Project evidence:
- Player Pass 21 screenshot: startup frame visible indefinitely while combat SFX were audible.
- GLITCHED MATRIX failure ledger: launch/crash/input/presentation blockers stop feature work; actual runtime outranks automated reports.

Official reference:
- pygame-ce display documentation: pygame.display has one current display Surface; get_surface() returns it; flip() presents it; set_mode/window state can change display behavior.
- pygame-ce event documentation: pygame 2 exposes WINDOWSIZECHANGED, WINDOWRESIZED, WINDOWMAXIMIZED and related window events in addition to legacy VIDEORESIZE.

Unverified assumption:
- This source-level repair must still be accepted on the user's Windows pygame-ce 2.5.7 runtime. Container cannot execute pygame-ce here.
