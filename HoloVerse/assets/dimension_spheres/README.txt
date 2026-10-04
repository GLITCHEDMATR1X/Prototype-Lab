HoloVerse Dimension Sphere Textures

These are 2:1 equirectangular seamless sphere textures. Replace any PNG while keeping the same filename.

Fallbacks:
  native.png   - native Panda3D adapter
  adapted.png  - adapted same-window reality
  linked.png   - generic/legacy external prototype
  legacy.png   - explicit legacy compatibility project
  missing.png  - unresolved/moved link

Per-dimension override:
  Add <dimension_id>.png in this folder. Non-alphanumeric characters are converted to underscores.
  Example UUID 31f4ab0a-2168-4faf-8c40-066483f61a83 -> 31f4ab0a_2168_4faf_8c40_066483f61a83.png

Project-local override:
  A linked project may provide holoverse/dimension_sphere.png or dimension_sphere.png beside its main.py.

Recommended authoring size: 1024x512 or 2048x1024. Keep left and right edges tile-compatible.
