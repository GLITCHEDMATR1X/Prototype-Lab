AFTERLIFE OF IO — REPLACEABLE MENU FONTS

These TTF files are loaded directly by the runtime. Replace any file in place and keep the same filename.

  title_font.ttf   Main menu / archive / dialogue headings
  menu_font.ttf    Interactive menu choices and section headings
  body_font.ttf    General body UI text
  small_font.ttf   Small prompts, subtitles and footer instructions

If a font file is missing or invalid, the game falls back safely to a local system font or the default pygame font.

Use reasonably readable Latin fonts for best results. Extreme script or symbol-only fonts may clip or become unreadable.

PASS 130 PRESENTATION MODES

WORN is the default game identity. It adds a very small deterministic erosion effect to rendered glyphs.
CLEAR removes that erosion and uses body_font.ttf at all hierarchy sizes for a cleaner, consistent reading option.
Both modes remain replaceable through these same TTF files.
