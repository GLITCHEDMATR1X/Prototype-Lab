AFTERLIFE OF IO — CURRENT BATTLE ASSETS

These filenames are runtime authority:
  background.png   authored 1280x720 battle background
  gleebs.png       Gleebs support figure on IO's side
  the_gate.png     The Gate support figure on the Guardian side

Do not restore architecture_left.png or architecture_right.png.
Battle fog/wisp/glow still use the accepted derived presentation until explicitly migrated in a later pass.

PASS 95 REPLACEABLE FALLBACK
----------------------------
fallback_chamber.png — replaceable diagnostic/fail-soft chamber shown only when the normal battle background is unavailable. The old procedural chamber remains the final safety fallback if this PNG is also missing/corrupt.
