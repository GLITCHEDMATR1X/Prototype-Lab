AFTERLIFE OF IO — REPLACEABLE MENU ART & FONTS

Replace files IN PLACE. Keep the filename unchanged.

TITLE / BACKDROP
  background.png        Recommended 1280 x 720. Full-screen title backdrop.
  logo.png              Recommended up to 850 x 190. Transparent title/logo art.
  frame.png             Recommended 1280 x 720. Transparent full-screen border overlay.
  selector.png          Recommended up to 46 x 46. Active-item ornament for standard menus.

SHARED MENU SKINS
  panel.png             Shared scalable panel used by title, pause, settings, save and load.
  item.png              Shared scalable normal menu-row skin.
  item_selected.png     Shared scalable selected/highlighted menu-row skin.
  control.png           Shared scalable small control button, including settings − / +.

DIALOGUE / ARCHIVE OVERLAYS
  dialogue_panel.png    Shared scalable panel for Gleebs and related archive/dialogue screens.
  dialogue_selector.png LEGACY / preserved for compatibility. Pass 135 no longer renders the old round dialogue highlight placeholder.

FONTS
  fonts/title_font.ttf  Main headings and large menu titles.
  fonts/menu_font.ttf   Interactive choices and medium section headings.
  fonts/body_font.ttf   General body UI text.
  fonts/small_font.ttf  Small subtitles, prompts and footer instructions.

The shared skins are intentionally singular rather than duplicated into separate
pause/settings/save folders. Replace one file and every menu using that semantic
role updates automatically.

PNG transparency is supported. panel/item/control/dialogue artwork is scaled to
the required UI rectangle. Keep important borders/details away from the extreme
center if you want them to survive scaling cleanly.

Missing, corrupt, or unsupported replacement art is NONFATAL. The game falls
back to its original procedural framing/buttons for that role. Missing or bad
fonts fall back to a local system font or the default pygame font.

Menu art and fonts are presentation-only. They do not alter world layers,
collisions, temporal anchors, save data, Entity battles, lore, particles, or
causal progress.

Do not put world, battle, particle, or audio replacements in this folder; those
retain their existing semantic asset locations.
