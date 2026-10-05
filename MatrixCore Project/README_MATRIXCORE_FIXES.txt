MatrixCore Project fixes (Pass 282.83 audit)

Copy these into your "MatrixCore Project" folder (same paths; overwrite when asked):

  Vector Wars/main.py
    - changing audio volume crashed when saving the setting (undefined variable)
    - firing a torpedo in the ocean operation crashed (wake drawn before its function existed)
  Utopia Conflict (Utopia Vision/Utopia Conflict/main.py)
    - a hidden error in the sound-file lookup (behaviour unchanged, the error is gone)
  Mirrors Limbo/main.py
    - saved your position 2-3 times a second; now every 5 s and only when you moved
    - a missing ghost model was searched for again for every ghost; now once

Also: Mirrors Limbo/assets/models/ghost_human.egg is not on GitHub - the repo's .gitignore
blocked every .egg file (fixed now). If you have that file locally, commit it so it is backed up.
