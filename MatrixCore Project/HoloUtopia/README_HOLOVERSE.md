# HoloUtopia — HoloVerse Native Compatibility

Pass03 fixes the empty-main/bootstrap selection failure. Overlay this package on the already-linked HoloUtopia folder; keep HoloVerse 282 unchanged and preserve `.holoverse_link.json`.

The adapter now selects the strongest real Panda3D game authority in the project instead of accepting the first ShowBase object created by `main.py`. Thin launchers and empty bootstrap apps cannot win over richer world/application modules.

If no actual game authority is present in the linked folder, native entry aborts with a precise source-missing diagnostic rather than displaying an empty world.
