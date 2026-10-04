# Operation StarFall Pass113 — Remote Telemetry Layout Repair

Status: **ACCEPTED AUTHORITY** for Pass113 scope. Exact-package static/runtime gates passed through GXT.6.

Primary task: repair the telemetry/readability regression exposed by the first real Pass112 1920×1080 Triton runtime screenshot.

Implemented:
- Embedded planet-local sonar, planet-vision overlay/label, access strip, and duplicate local HUD chrome remain hidden while the StarFall shell owns the remote feed.
- The 16:9 feed region remains unchanged at `(0.11, 0.89, 0.11, 0.89)`.
- The lower monitor bezel is extended without resizing the feed.
- Live objective, action/progress/sonar status, and TAB-disconnect controls now render in that bezel outside the planet display region.
- Existing return-controls runtime self-test now expects the local sonar/vision HUD to remain hidden after closing the embedded options modal.

Runtime evidence:
- GXT.6 + Panda3D 1.10.16, CPython 3.13 Linux.
- Triton active-feed screenshot: 1920×1080.
- Operation active with no load error and embedded moon UI hidden.
- ESC/options exclusivity and TAB return cleanup PASS with zero render/UI/feed residue after return.

Frozen scope: terrain, missions, rewards, loading flow, feed dimensions, camera ownership, and gameplay controls.

Acceptance summary:
- Focused static contract: TECHNICAL_PASS (19/19).
- GXT.6 runtime active-feed proof: VISUAL_PASS at 1920×1080.
- GXT.6 screenshot review: PASS (7.99/10, 0 high-severity issues).
- ESC/options/TAB return cleanup: PASS with zero render/UI/feed residue.
- GXT.6 regression vs exact Pass112: no removals or out-of-scope changes.
- Package checker / Python / JSON / ZIP integrity: PASS.
