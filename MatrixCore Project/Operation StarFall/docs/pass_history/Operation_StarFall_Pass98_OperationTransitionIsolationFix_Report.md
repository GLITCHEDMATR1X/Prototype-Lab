# Pass98 — Operation Transition Isolation Fix

Fixed the reproduced first-world to second-world transition failure.

- shell flight/interior roots are stashed during embedded operations
- shared camera is parented to the active planet render root
- camera is reclaimed before planet root removal
- CommonFilters cleanup runs at planet teardown
- second embedded planet can create a fresh filter pipeline
- drone entry altitude/pitch and camera XY terrain clearance prevent terrain-clip starts
- operation overlay follows current operation code

Verified Mimas launch from flight mode, return to ship, Europa second launch, return to ship, zero embedded render/UI residue.
