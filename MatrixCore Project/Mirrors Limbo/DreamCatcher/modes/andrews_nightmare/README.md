# Andrew’s Nightmare — P21 (part of Mirror's Limbo)

Reached from DreamCatcher: at the bedroom TV press E, choose CH 07 DREAM, press T. ESC then Q
(or RETURN TO DREAMCATCHER) goes back. After breaking the intercept, Q works without pausing.
The Null-Layer disconnect records the ending and wakes you in DreamCatcher automatically.
Mouse sensitivity, FOV preference, volume and window mode follow Mirror's Limbo. This folder
must stay inside Mirror's Limbo; it uses the shared `gx_common` package there.

# Andrew's Nightmare — Pass 17: Ceiling Loop

A Panda3D 1.10.16 first-person analogue/digital nightmare chapter inside Utopia's DreamCatcher system.

Andrew moves through a connected dream instance that has been intercepted. Sleepers and false Sleepers can both appear at distance: some humanoid forms are real connected users and some are false reconstructions. Touching the active Sleeper disturbs the dream and throws Andrew through temporal datamoshing into another authored instance variation.

## Current gameplay loop

Explore while avoiding contact with the Sleeper. Activate the relay in the current recovered room to calm a linked destination and weaken the interception. Physically reach that destination to wake its relay, then continue until Deep Buffer. Completing all linked room recoveries destabilizes the intercepted instance globally and the Sleeper vanishes through temporal feedback.

Each run chooses one of **six authored route orders** through Archive Cell, Feedback Room and Dead Channel before Deep Buffer. The route stays fixed for the whole run. Dream-cycle changes alter presentation and secrets, not trusted topology/collision.

## Pass 17 — Ceiling Loop

A real Sleeper can no longer permanently body-block a narrow route. If Andrew holds a close, deliberate gaze from just outside contact distance (roughly 1.1–2.3 m), the Sleeper slowly sinks through the real floor. The same continuous humanoid surface reappears from the ceiling with no visible portal. Near the end of the wrap, the re-emerged body tucks upward into the ceiling, creating visible head clearance so Andrew can run beneath it.

The opening is temporary. The Sleeper remains fixed while wrapped and only reforms after Andrew has cleared the immediate area; if he returns underneath during reformation, it tucks back up rather than creating an unavoidable hit. Floor-level Sleeper contact is disabled only while the visual clearance is actually open. The ordinary touch-to-disturb rule returns as soon as the Sleeper reforms.

This is separate from Visitor Resonance: the close band opens a blocked route, while the existing 2.45–7.25 m observation band produces the temporary DreamCatcher signal read. No HUD meter, portal plane, teleport, or collision lie was added.

## Pass 16 — Visitor Resonance

The real Sleeper is now more than an avoid-only hazard.  If Andrew deliberately keeps the Sleeper in view from roughly 2.5–7 m for about 1.5 seconds, he can temporarily read the signal without touching the person.  There is no meter.  The Sleeper's whole-body registration tightens while the lock forms; on success Andrew's distance vision clears for a few seconds, false Sleepers disappear, and the current world-space destination beacon becomes easier to read.

The read can happen once per recovery stage.  Breaking observation lets the Sleeper move again, so using the mechanic deliberately creates a risk/reward decision instead of turning it into a free scan.  The hidden glasses remain the only permanent route into the Null Layer.

A new original `sleeper_resonance.wav` cue marks a successful read.  The mechanic never changes collision or level topology and adds no permanent HUD.

## Pass 15 — visual foundation recovery

This is a recovery pass, not a content expansion. The previous player-facing presentation was rejected because the Sleeper exposed primitive/snowman construction, the camera/vision language was not strong enough in play, and the datamosh read too much like a generic glitch treatment.

The Sleeper is now a single seamless 3D humanoid surface loaded from `assets/models/sleeper_continuous.bam`. Close and side views no longer reveal stacked boxes, spheres, cylinders or joint caps. Two very faint whole-body registration echoes remain for damaged DreamCatcher signal language, but individual anatomy is never duplicated as separate primitives.

Andrew's baseline dream vision now has stronger **depth-based nearsightedness**: nearby geometry remains usable while distant rooms lose detail. The blur comes from the actual scene depth texture, not a radial/fullscreen mask. Corrupted space also retains restrained focus drift, analogue softness, scanlines, grain, tracking instability and authored room darkness. Stable spaces calm the corruption but do not magically cure Andrew's eyesight.

The **False-near corridor** uses a stronger authored perspective lie. Its opening begins under a telephoto-like FOV and the lens widens as Andrew advances, so the room ahead resists the normal rate at which it should appear to approach. The effect releases before the actual threshold; collision/topology never move.

Temporal datamoshing now freezes the last meaningful pre-contact camera-motion vector and reuses it after the instance changes. Large teleport deltas are explicitly ignored. Old frames persist through deterministic macroblock regions and are progressively overwritten by the new room. Event-only posterization was removed so the transition is carried by temporal history rather than a fake compression overlay.

## Audio

Pass 14's six original ambient WAV loops in `assets/audio/music` and the existing SFX library remain intact. Sleeper contact slows/pitches down and wobbles the active ambience, fades it through the datamosh, then advances to another track in the next instance. Null Layer removes the score after its transition cue. Missing optional audio or `--no-audio` remains safe.

## Progressively failing interception

Each dream cycle can expose harmless false-Sleeper structures. They can resemble people through Andrew's Distance blur but resolve into ordinary braces/supports up close. As linked rooms are recovered, false Sleepers progressively disappear. The first successful room recovery also exposes the Memory seam and its real shortcut.

## Optional glasses / Null Layer

Andrew's glasses are hidden at a difficult but reachable authored anchor that can change between dream cycles. Near them: `E // WEAR`.

Putting them on exposes the Null Layer: the same architecture with textures, stabilizers, Sleepers, false Sleepers, anomalies, interference traces, distance blur and nightmare post-processing removed. The score stops. A raw connection point appears in Deep Buffer; near it: `E // DISCONNECT`.

## Existing spaces and secrets

Lightless Gallery, Echo Room, Witness Alcove, Return Room continuity errors, rare sharp-eared/green-eye traces, Memory seam shortcut, changing dream-cycle presentation, false Sleepers, hidden glasses and the Null Layer remain in place.

## Controls

- `WASD` — move
- `Mouse` — look
- `SHIFT` — sprint
- `SPACE` — jump
- `CTRL` — crouch
- `E` — use nearby relay / wear glasses / disconnect in Null Layer
- `ESC` — pause; never instant quit
- `F11` — borderless/windowed toggle where supported

## Development / QA

Normal launch: `python main.py`

Windowed: `python main.py --windowed`

No-audio smoke: `python main.py --smoke-test --no-audio`

Deterministic gameplay regression: `python main.py --self-test`

Static/source contract: `python tools/verify_build.py`

Temporal inspection helper: `python tools/capture_mosh_sequence.py`

A fixed run profile can be reproduced with `--dream-seed <number>`.

## Status

**CANDIDATE.** Panda3D gameplay/visual verification is required for this pass, followed by final-package regression. Native Windows borderless/cursor/focus/F11 remains a target-machine acceptance gate.
