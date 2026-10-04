# Operation StarFall Pass102 — Reference 1080p Display Authority

Status: **CANDIDATE**

## Base and target

Base: Pass101 Operation Launch Authority Candidate.
Primary target: remove contradictory startup sizing and make 1920x1080 the normal render/UI authority without reintroducing the old fixed-window problem on larger desktops.

## Findings

Pass101 supported 1920x1080, but normal startup still inherited the Pass97 `desktop_resizable` default and the shell fallback still contained `win-size 1600 900`. In the headless runtime this produced a 1600x900 default surface even though the project design canvas and several presets were 1920x1080.

Panda3D 1.10 documentation confirms that window properties supplied before `ShowBase` determine initial window creation, while later `requestProperties()` changes are deferred to a subsequent window task/frame. Pass102 therefore keeps startup authority in the shared pre-ShowBase display configuration instead of adding another post-launch resize.

## Changes

- Added `reference_1080p_window` as the normal shared display mode.
- Default saved preset is now `reference_1080p_auto`.
- Removed the shell fallback's 1600x900 startup assumption; fallback is 1920x1080.
- On a simulated 1920x1080 desktop with a 1040px work area, normal startup keeps an exact 1920x1080 render surface using borderless placement rather than shrinking for the taskbar.
- On a simulated 2560x1440 desktop, normal startup uses a centered decorated/resizable 1920x1080 client.
- On a simulated 1280x720 desktop, normal startup keeps an exact 1280x720 borderless fallback and does not go below the documented minimum.
- Existing explicit desktop-fit, bordered, compact, borderless-desktop and exclusive-fullscreen modes remain available.
- Embedded moon display options now expose and persist the same `REFERENCE_1080P` authority.
- The untouched Pass97 shipped default profile migrates to the Pass102 reference preset; explicit saved alternate presets are preserved.
- Updated transport/display metadata and the current screen standard to v0.3.

## Runtime and visual verification

- Panda3D 1.10.16 default headless runtime surface: 1920x1080.
- Primary flight capture: 1920x1080.
- Saturn operations map primary capture: 1920x1080.
- Minimum regression capture: 1280x720.
- Cross-world display contract: PASS.
- Screen-layout contract: PASS.
- Transport-link display inheritance: PASS.
- Pass101 operation launch authority: PASS.
- Pass100 shell UI authority: PASS.
- Pass99 Mimas modal/return regression: PASS.
- Mimas -> ship -> Enceladus -> ship lifecycle: PASS.

## Pending

Native Windows verification is still required to confirm actual OS decoration/taskbar behavior, DPI scaling, resize/maximize behavior and the exact 1080p startup surface on the user's machine. Until that is seen, this remains CANDIDATE rather than ACCEPTED AUTHORITY.

## Fresh-package preverification

A clean Pass102 archive was extracted into a blank directory. From that extracted copy: source compilation passed, package hygiene passed before runtime, the display-authority test reported a 1920x1080 default surface, a fresh 1920x1080 flight frame was rendered, shell authority passed, operation-launch authority passed, Mimas modal/return passed, the complete Mimas -> ship -> Enceladus -> ship cycle passed, and package hygiene still passed afterward with no `__pycache__` or bytecode residue.

## Panda3D reference used

Implementation follows Panda3D 1.10 window authority semantics: initial properties are supplied before `ShowBase` through configuration, while `GraphicsWindow.requestProperties()` is a deferred runtime request. Pass102 therefore fixes normal startup in the shared pre-ShowBase display configuration instead of adding another post-launch resize layer.

Official references:
- https://docs.panda3d.org/1.10/python/reference/panda3d.core.WindowProperties
- https://docs.panda3d.org/1.10/python/reference/panda3d.core.GraphicsWindow
- https://docs.panda3d.org/1.10/python/programming/configuration/configuring-panda3d
