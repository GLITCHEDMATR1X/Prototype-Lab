# Vector Wars — Pass 19 HoloVerse Legacy Readiness + Full Regression Audit

## Scope
One task: audit the complete Pass 18 branch for regressions and prepare Vector Wars for the current staged HoloVerse LEGACY/external integration path without rewriting its Pygame renderer.

## Regression gate
- Starting Pass 18 package: 25/25 regression scripts PASS.
- Pass 19 source tree after changes: 26/26 PASS.
- Final package must reproduce 26/26 after fresh extraction.

## Regressions / blockers found

### 1. Normal startup was still forcing AIR
`--auto-mode` defaulted to `air`, and startup applied that after campaign-save restoration. This meant an ordinary launch could override the campaign-owned phase.

Repair:
- no explicit `--auto-mode` => `phase_progression.active_mode` owns startup;
- `--auto-mode air/ground/foot/ocean` remains explicit QA-only behavior;
- Panda/HoloVerse normal launch helpers no longer force an Air test front.

### 2. External launch-safe mode skipped normal Pygame shutdown
The old code conflated Panda3D launch-safe behavior with true in-process embedding. A legacy external child launched with `--panda3d-launch` therefore skipped `pygame.quit()` at normal exit.

Repair:
- `in_process_embedded` and `launch_safe` are separate authorities;
- an external HoloVerse/Panda child uses launch-safe window behavior but still calls `pygame.quit()` before process exit;
- true in-process embedding alone can retain ownership of Pygame lifecycle.

### 3. Package debris
Removed stale `main.py.pre18`, `__pycache__`, and `.pyc` files from the shipping candidate.

## HoloVerse LEGACY contract
Added `holoverse_legacy_contract.json` and a permanent regression test.

Normal HoloVerse launch:
- engine remains pygame-ce;
- compatibility = LEGACY;
- external child process;
- campaign/save authority chooses initial phase;
- `--holoverse-launch` identifies HoloVerse ownership for return wording;
- ESC opens deliberate return confirmation;
- host may suppress child music through `HOLOVERSE_ROOT_OWNS_MUSIC`;
- host may expose shared SFX through `HOLOVERSE_SHARED_SFX_DIR`;
- host may redirect player data through `VECTOR_WARS_USER_DATA`;
- child exits cleanly; HoloVerse is then responsible for restoring its suspended state.

QA launch remains separate and may explicitly request an auto-mode.

## Why LEGACY rather than a renderer rewrite
Current project direction explicitly stages linked realities as LEGACY/external first, with ADAPTED/NATIVE conversion considered individually later. Vector Wars remains a Pygame renderer for this pass. No claim of same-window native Panda3D rendering is made.

Panda3D's normal task system runs cooperatively through its host task manager, which is one reason running an unrelated Pygame main loop inside the same native lifecycle should be treated as a deliberate port/adaptation project rather than casually mixed into the host loop.

Reference: https://docs.panda3d.org/1.10/python/programming/tasks-and-events/tasks

For the LEGACY route, HoloVerse should own the child-process lifecycle and wait for the Vector Wars child to terminate before restoring the host. Python's subprocess documentation defines `Popen.wait()` as waiting for child termination and returning its return code.

Reference: https://docs.python.org/3/library/subprocess.html

## Host-side compatibility warning
A validator copy preserved inside the older GXT.6.3 HoloVerse tooling expects a previous Vector Wars `native_panda` / pass88 same-window adapter contract. That conflicts with the newer project handoff that explicitly calls for a LEGACY/external contract first and defers the native-compatibility decision.

This pass follows the newer handoff and does NOT recreate stale native adapter files merely to satisfy that older validator.

Before calling integration accepted, the current HoloVerse build must be tested against this contract and its registry/validator updated if it still enforces the obsolete native-only rule.

## Acceptance boundary
This container still cannot execute pygame-ce 2.5.7, so the following are not claimed as runtime-accepted here:
- actual Pygame window opening under HoloVerse;
- ESC return presentation in the real child window;
- host suspend/restore behavior;
- repeated HoloVerse -> Vector Wars -> HoloVerse cycles;
- orphan window/process/audio verification on the target system.

Those are the next host-side acceptance checks. Source/regression readiness is verified; native runtime acceptance is pending.
