# GHOST SIGNAL: UTOPIA — Chapter One V1 RC3

A Pygame cyberpunk surveillance campaign where Andrew captures Utopia building by building while Gleebs protects the people, machines, and memories inside it.

## Chapter One

- 3 complete districts
- 11 hackable buildings
- 11 recoverable memories
- deterministic evidence-driven hacking
- building-specific Gleebs lockouts
- persistent profile, backup, recovery, settings, and accessibility
- Industrial Grid takeover finale and High Towers cliffhanger

## Launch

Inside Afterlife of IO: title → **MODES → GHOST SIGNAL** (unlocks after 4 Memory Guardians). It runs in Afterlife's window; `Esc` → `Q` (DISCONNECT — BACK TO AFTERLIFE) returns to the Afterlife title.

Standalone (from this folder):

```text
pip install -r requirements.txt
python main.py
```

## Controls

- WASD / edge pan — move across the satellite city or move a possessed drone
- Mouse wheel — zoom
- LMB — select, interact, or choose a hacking method
- RMB — back or close contextual panels
- 1–3 / Tab — switch camera feeds
- 4–8 — choose hacking methods
- E / Enter — enter building or confirm
- F1 / H — help
- F2 — settings
- M — memory archive on city map
- Shift+M — mute
- G — skip onboarding guide
- F11 — fullscreen
- ESC — close panel or pause

## Save contract

Chapter One V1 uses schema `ghost_signal_utopia.chapter_one.v1`, profile version 6. Historic profile versions 1–5 migrate forward. One automatic backup is retained, corrupt primary saves recover from backup, and newer future saves are preserved with writes disabled.

## Windows build

The standalone RC3 build/promotion scripts (`BUILD_WINDOWS.bat`, `RUN_WINDOWS_MANUAL_ACCEPTANCE.bat`, `PROMOTE_WINDOWS_V1.bat`) are not part of this Afterlife mode copy; Ghost Signal ships inside the Afterlife of IO build.
