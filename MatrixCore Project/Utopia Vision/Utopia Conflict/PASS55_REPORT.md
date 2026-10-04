# Utopia Conflict — Pass 55 Pause Menu Input Repair

The pause/settings screen was functionally mouse-only. Pass 55 adds a single menu-input authority without changing combat or world systems.

## Player controls while paused

- **W/S** or **Up/Down**: move selection
- **Enter/Space**: activate selection
- **Mouse**: existing DirectButton interaction remains available
- **Esc**: resume

The selected item uses a cyan highlight and the pause panel shows the controls at its bottom edge. Opening the menu explicitly requests a visible cursor in absolute mouse mode.

## Validation

The dedicated Panda3D 1.10.16 regression opens the real pause menu through the event messenger, navigates to Draw Distance, activates it, navigates back to Resume, and resumes gameplay. Fresh 1920×1080 proof is stored at `verification/screenshots/pause_menu_input.png`. Existing presentation-readiness, help-reference, HUD-minimalism, standards, compile, and self-test regressions also pass.
