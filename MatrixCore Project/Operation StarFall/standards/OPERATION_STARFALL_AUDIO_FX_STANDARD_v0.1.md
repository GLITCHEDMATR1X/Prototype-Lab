# Operation StarFall Audio + FX Authority Standard v0.1

Base phase: Mastering / Remastering
Current pass: Pass41 — Audio + FX Authority

## Core rule

Operation StarFall audio must be owned by one authority. Normal play can use audio, while tests, screenshots, headless runs, and explicit `--no-audio` runs must stay silent and stable.

## Runtime ownership

- The StarFall shell configures Panda3D audio.
- Embedded moon operations inherit silence only when the shell was launched with `--no-audio`, `--headless`, or `STARFALL_HEADLESS=1`.
- Embedded moon operations must not be forced silent during normal play.
- Moon operations own their local action cues and one world ambience bed.
- Returning to the shell must stop moon ambience, drill loops, and any other active moon SFX.

## World ambience rule

Each active moon world gets exactly one low-volume looping bed:

| World | Ambience cue |
|---|---|
| Mimas | `ambience_mimas.wav` |
| Enceladus | `ambience_enceladus.wav` |
| Iapetus | `ambience_iapetus.wav` |
| Titan | `ambience_titan.wav` |

Only the active world ambience may play. Other world ambience loops must be stopped.

## Action cue rule

Action cues are mapped through `ACTION_SFX_EVENT_MAP` in `Worlds/main.py`.

Current required cues:

- `drill_start`
- `drill_loop`
- `drill_deep_crack`
- `drill_breakthrough`
- `robot_activate`
- `robot_anchor`
- `robot_braced`
- `sonar_ping`
- `sonar_lock`
- `magnet_attach`
- `cargo_hoist`
- `cargo_collect`

## Silence safety

`--no-audio` must be accepted by the shell and moon world.

These modes must not load or play live audio:

- `--no-audio`
- `--headless`
- `--smoke-test`
- `--test-shot`
- `--boot-shot`
- `--offscreen`

## FX direction

Audio and visual FX should be paired to real actions:

- scan/sonar cue when the sonar pulse is meaningful
- lock cue when a signal or depth lock occurs
- drill cues through the drilling sequence
- tripod cues through deployment and bracing
- cargo cues through attach/hoist/collect
- ambience should describe the world without drowning action feedback

## Pass acceptance

Pass41 is accepted only if:

- normal shell code allows Panda3D/OpenAL audio
- `--no-audio` still disables audio
- embedded moon launches no longer force `--no-audio`
- all active worlds have ambience assets
- action cue assets exist
- returning from an embedded operation stops active SFX
- audio contract test passes
