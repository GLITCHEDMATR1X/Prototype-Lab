# Operation StarFall Pass109 — Planet Display Lifecycle

Base: Pass108 Planet Display Authority Candidate.
Status: CANDIDATE. GXTOOL/static/regression checks pass; Panda3D runtime/visual acceptance is still pending because the reset container lacks the CPython 3.13 Linux Panda3D 1.10.16 payload.

One task: recheck and harden the Pass108 remote planet display lifecycle.

Changes:
- retain a reference to partially initialized embedded planet instances so failed constructors can release their owned tasks, events, audio, UI, and roots;
- add shell-owned fallback cleanup for embedded render/UI roots and operation tasks after failed launch or TAB return;
- expose feed region/camera, loading-root, delayed loading-task, interior, flight, and display visibility through the GXTOOL lifecycle snapshot;
- measure return cleanup after the shell/display has actually been restored;
- update stale operation-cycle tests from the old stashed/full-camera architecture to the Pass108 interior + secondary-feed-camera authority.

Frozen: terrain, missions, rewards, rover/drone mechanics, loading art, display styling, and normal shell gameplay.
