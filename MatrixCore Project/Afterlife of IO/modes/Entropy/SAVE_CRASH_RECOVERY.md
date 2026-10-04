# Entropy — Save / Crash Recovery

Pass 30 keeps the existing save schema v5 and hardens the storage and lifecycle around it.

## Windows player-data location

```text
%LOCALAPPDATA%\GLITCHED MATRIX\Entropy
```

Important files:

```text
saves\save_state.json
saves\save_state.previous_good.json
logs\session_state.json
logs\runtime.log
logs\fatal_fault.log
crashes\Entropy_crash_*.zip
```

The active save is written through a same-directory temporary file, flushed to the OS, atomically replaced, then parsed again before the write is accepted. A validated previous-good generation is retained. If the active save is truncated or invalid JSON at launch, Entropy loads the previous-good copy and repairs the primary file automatically.

The campaign payload stays schema v5. Pass 30 does not reset or translate six-fragment progression, upgrades, cargo, HOME/ship-recovery progress, or Gleebs completion.

## Lifecycle protection

- Active play checkpoints every 20 seconds.
- Entering pause also checkpoints, which covers controller disconnect and focus-loss pause paths.
- A large post-start frame gap is treated as a suspend/resume boundary and pauses before collapse or movement timing advances.
- A clean exit marks the session clean. An active/crashed prior marker is recognized at the next boot.

## Crash reports

Crash reports are local only. Nothing is uploaded automatically.

Each verified crash bundle includes a human-readable report, JSON report, bounded runtime/fault-log tails when available, build/runtime metadata, and minimal game context such as campaign phase, system index, Data Fragment count and collapse state.

Crash bundles deliberately exclude save-file contents, environment-variable dumps, arbitrary filesystem listings, and redact common per-user path prefixes.

On Windows, double-click `OPEN_ENTROPY_CRASH_FOLDER.bat` to open the crash folder.
