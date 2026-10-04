# Operation StarFall Pass110 — Interior Authority Cleanup

Status: **CANDIDATE**

Primary task: recheck Pass109 and remove the remaining normal-player routes/copy that exposed the rejected flight architecture.

## Change
- Removed the pause-menu `RETURN TO FLIGHT` route.
- ANOM remains a selectable observatory node but no longer switches the shell into flight mode.
- ANOM map/station copy now identifies it as interior analysis.
- Removed stale `F FLIGHT` observatory copy and unused shell `f` event ownership.
- Preserved Pass108 16:9 remote planet display and Pass109 lifecycle/input handoff.

## Validation boundary
GXTOOL is primary. Pass108/109/110 static contracts pass. Panda3D runtime/visual proof remains pending because the GXTOOL Linux CPython 3.13 Panda3D 1.10.16 payload is still unavailable in this reset container. No visual acceptance is claimed.
