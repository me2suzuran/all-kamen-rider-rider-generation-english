# All Kamen Rider: Rider Generation — English Translation

Fan translation of the Japanese Nintendo DS game *All Kamen Rider: Rider Generation* (Bandai Namco, 2011) into English, by **me2suzuran**.

## Download / play

Grab the patch from [`patch/`](patch/) and apply it to your own Japanese ROM with
[Rom Patcher JS](https://www.marcrobledo.com/RomPatcher.js/) or Floating IPS. Instructions and the required ROM
checksums are in [`patch/README.txt`](patch/README.txt). This repository does not contain the game.

## What's translated

- All story dialogue (1,934 lines, every Rider's boss conversations) and speaker names
- World map, stage names, missions, shop, bonuses, passwords, in-code strings
- 500 images: menus, dialogs, character select (abilities and move names), HUD, tutorials, shop, credits
- Dialogue font patched to proportional widths, plus an added apostrophe glyph

## Building from source

Requirements: Python 3.12, `pip install ndspy pillow numpy`, and the original ROM
`All Kamen Rider - Rider Generation (Japan).nds` (CRC32 `986B74F0`) in this folder.

```bash
python tools/krtl.py check      # validate text (length, pixel width, glyphs)
python tools/krtl.py build      # writes "All Kamen Rider - Rider Generation (English).nds"
python tools/mkbps.py make "All Kamen Rider - Rider Generation (Japan).nds" "All Kamen Rider - Rider Generation (English).nds" "patch/All Kamen Rider - Rider Generation (English) v1.0.bps"
```

## Layout

| Path | What |
|---|---|
| `tl/script/*.json` | Story dialogue (Japanese → English), one file per script; `*.context.txt` shows each variant in order |
| `tl/misc.json`, `tl/world.json`, `tl/arm9.json` | Names, menus, world map, shop, bonus/password text, strings inside the program |
| `tl/gfx/*.json` | Image edit specs (erase + redraw text); see `tl/gfx/README.md` |
| `tl/GLOSSARY.md` | Names and terms |
| `tools/krtl.py` | Extract / check / build |
| `tools/gfx.py`, `tools/gfxtl.py`, `tools/gfxview.py` | Nitro graphics decode/encode, image text editing, measuring helpers |
| `tools/mkbps.py` | BPS patch maker / applier |

Kamen Rider is © Ishimori Pro / TV Asahi / ADK / Toei. The game is © Bandai Namco Games. Non-commercial fan project.
