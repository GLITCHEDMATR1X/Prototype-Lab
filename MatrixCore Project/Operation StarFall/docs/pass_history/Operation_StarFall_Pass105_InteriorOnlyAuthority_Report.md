# Operation StarFall Pass105 — Interior Only Authority

Single target: normal play stays in the ship interior.

Changes:
- Removed the `F` binding that toggled between interior and flight.
- Removed flight-mode control instructions from the shell help screen.
- Preserved dormant flight implementation for legacy QA compatibility only; it is no longer part of normal player controls.
- Normal startup remains interior-first.

No terrain, dock, planet, mission, lighting, or progression systems were redesigned in this pass.

Status: CANDIDATE. Panda3D runtime verification is pending because the current reset environment does not have Panda3D importable.
