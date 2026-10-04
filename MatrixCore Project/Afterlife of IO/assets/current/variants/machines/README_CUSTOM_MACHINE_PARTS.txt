AFTERLIFE OF IO — CUSTOM MACHINE PARTS

Powered Core Workshop output lives in this folder.
Each created part writes:
  custom_part_###.png
  catalog.json metadata entry

The PNG is generated from the selected source art and shape. SOURCE preserves the alpha-cutout silhouette and authored proportions; geometric shapes use proportional crop-fill rather than stretching the source art.

The catalog entry can store:
  role          Frame / Cosmetic / Gear / Pivot / Fan / Pipe / Core
  world_height  legacy-compatible numeric size field
  size_basis    max_edge for custom/variant art (Pass 124+)
  functions     optional rotate / tilt / shake presentation FX for Frame/Cosmetic roles
  snap_points   up to six [u, v] assembly snap points normalized to 0..1 across the saved PNG
  snap_schema   normalized_uv_v1

Snap points are edited directly in the Machine Workshop preview. They provide assembly alignment assistance for uneven or asymmetric custom parts. They do NOT resize or redefine the existing Pass 119 Conduit Pipe's fixed mechanical endpoints.

Pass 124 sizing rule:
  Custom/variant art uses the selected Compact/Standard/Large/Heavy value as its MAXIMUM WORLD EDGE.
  The source aspect ratio is preserved. A long rectangular PNG stays rectangular instead of being forced square, but its long edge is bounded so it cannot become enormous in-game. Existing base machine parts keep their established height-based sizing unchanged.

Do not rename a generated PNG without also renaming its catalog.json key.


PASS 126 SCALE RULE
All machine parts use one common size-envelope rule. The saved world_height field is the maximum edge of that envelope for compatibility. Source aspect ratio only decides the rectangular proportions inside it. No Pipe, role, filename, or source-folder special case may enlarge a part.
