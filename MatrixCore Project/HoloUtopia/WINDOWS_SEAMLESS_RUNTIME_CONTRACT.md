# HoloUtopia Pass03 — Windows Acceptance

1. Keep HoloVerse 282 unchanged.
2. Overlay Pass03 onto the same linked HoloUtopia folder.
3. Do not delete `.holoverse_link.json` and do not relink.
4. Launch HoloVerse and run HoloUtopia.
5. `holoutopia_authority_inventory` should rank the project Python files.
6. An empty/bootstrap `main.py` must not become the mounted delegate.
7. `holoutopia_runtime_class` should identify the real gameplay application/module.
8. Real HoloUtopia geometry/HUD/gameplay must appear in the existing HoloVerse window.
9. No second ShowBase/window/frame loop.
10. TAB returns immediately and restores exact HoloVerse state. ESC uses the shared HoloVerse menu.

If the folder contains no actual game source, the correct diagnostic is `No non-bootstrap HoloUtopia game authority found`; do not accept an empty scene as success.
