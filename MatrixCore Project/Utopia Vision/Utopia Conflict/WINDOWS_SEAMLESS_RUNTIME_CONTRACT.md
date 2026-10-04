# Utopia Conflict Pass42 — Windows Native Acceptance

1. Keep HoloVerse 282.
2. Extract Pass42 over the existing linked Utopia Conflict folder.
3. Preserve `.holoverse_link.json`.
4. Launch HoloVerse and run the existing Utopia Conflict archive entry.
5. Confirm no second Windows window appears.
6. Confirm the log prints `utopia_conflict_source_inventory` and `utopia_conflict_runtime_class`.
7. Confirm `utopia_conflict_native_enter` follows.
8. Confirm the real Utopia Conflict menu/battle/editor appears.
9. Confirm HoloVerse's hidden camera/player do not move.
10. Confirm TAB returns to the exact HoloVerse state.
11. Confirm ESC uses the HoloVerse shared menu.
12. Confirm relaunching HoloVerse preserves the same dimension link.

If entry still fails, copy the single `utopia_conflict_native_enter_failed ...` line plus the immediately preceding `utopia_conflict_source_inventory ...` line; Pass42 now reports runtime discovery instead of the Pass41 marker gate.
