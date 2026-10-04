# Utopia Conflict — HoloVerse Native Integration

Pass42 replaces the failed Pass41 adapter only. Keep HoloVerse 282 unchanged.

Apply this overlay over the already-linked Utopia Conflict folder. Do not delete `.holoverse_link.json`. The real game remains the authority; the overlay only supplies the HoloVerse manifest/adapter and verification files.

Pass42 supports both direct game entry files and thin wrapper `main.py` launchers. It discovers the real project-local Panda3D application after import instead of rejecting the project based on literal strings in the wrapper.

TAB returns immediately to HoloVerse. ESC remains the shared HoloVerse menu. HoloVerse keeps its dedicated dimension camera and frozen host state.
