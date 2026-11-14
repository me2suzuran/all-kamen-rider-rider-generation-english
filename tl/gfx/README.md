# Translating text inside images

Images are edited by *spec*: a JSON file `tl/gfx/<Group>.json` mapping asset ids to a list of ops.
`python tools/krtl.py build` applies every spec and re-imports the pixels into the ROM (palette-matched).
Work only through specs. Never edit tools/*.py, never run `krtl.py build` (the lead does that).

## Asset ids
- `Folder/name` = background screen (`_Data/Folder/name.NSCR` + `.NCGR` + palette), usually 256x192.
- `Folder/name#N` = sprite cell N of `_Data/Folder/name.NCER` (char data from `.NCGR` or `.NCBR`).
  Coordinates are relative to the rendered cell image (top-left = 0,0).

## Workflow (run from the project folder)
1. `python tools/gfxview.py list <Folder>`: lists every screen and every sprite cell with its size.
2. Look at the images. `python tools/gfxview.py grid <asset> <out.png> [x0 y0 x1 y1] [scale]` writes a zoomed
   render with an 8px grid and coordinates. Write scratch PNGs to your scratchpad, then open them with Read.
3. Measure exactly:
   - `python tools/gfxview.py rows <asset> x0 x1 y0 y1` prints an ASCII map per row (`#` bright, `+` mid, `.` dark,
     space = transparent). Use it to find the exact text rows, dotted separator lines and box edges.
   - `python tools/gfxview.py colors <asset> x0 y0 x1 y1` gives the most common colours (text colour, outline, background).
4. Write ops in your JSON file. One JSON object holds all of that group's assets.
5. `python tools/gfxtl.py preview <filter>` writes `tl/gfx/preview/<asset>.png` (original | translated, 2x).
   `python tools/gfxview.py sheet <pattern> <out.png>` stacks previews. **Look at every preview you produce**
   and iterate until clean: no Japanese remnants, no smears, no broken borders or separator lines, text inside its box.

## Ops (rect = [x0, y0, x1, y1], end exclusive)
Erase first, then draw text.
- `{"op":"fill","rect":R,"mode":"tile","from_y":Y,"period_y":P}`: rows copied from the clean block starting at row Y,
  repeating every P rows, phase-aligned. Use this for boxes with horizontal scanline texture (common: period 2 or 3).
  Check the texture with `rows`/`colors` first. `from_x`/`period_x` do the same for columns: e.g. `from_x` = a
  clean column right of the text and `period_x: 1` erases text on buttons whose stripes are horizontal.
- `{"op":"fill","rect":R,"mode":"inpaint","min_luma":170,"grow":1}`: removes bright text (or `max_luma` for dark
  text, or `"colors":[[r,g,b],...],"tol":60`) by diffusing the surrounding background inward. Best for gradients,
  photos and irregular textures. `grow` widens the mask to catch outlines and anti-aliasing.
- `{"op":"fill","rect":R,"mode":"h"}` / `"v"`: linear interpolation from the pixels just outside R (left/right or
  above/below). Good for smooth gradients when those edge pixels are clean.
- `{"op":"fill","rect":R,"mode":"row"}`: each row becomes its most common colour. Only for flat boxes where text is
  sparse in every row; dense bold text breaks it.
- `{"op":"fill","rect":R,"color":[r,g,b]}`: flat colour.
- `{"op":"copy","src":R,"dst":[x,y]}`: copy a block of the ORIGINAL image (e.g. a clean piece of button).
- `{"op":"text","text":"Line 1\nLine 2","rect":R,"color":[r,g,b],"outline":[r,g,b]|null,"shadow":[r,g,b]|null,
   "font":"12"|"10","bold":true|false,"align":"center"|"left"|"right","lh":12,"dx":0,"dy":0,"spacing":0}`
  - font "12": glyph cell 11px tall (caps ~8-9px). Default line height 12. Normal body text and headings.
  - font "10": glyph cell 9px tall. Small labels: button pills, captions, cramped boxes.
  - bold: 1px heavier; use for headings / big button labels that were bold in Japanese. Body text: `false`.
  - Text that is too wide gets its letter spacing squeezed once, then a WARN is printed. Fix every WARN: shorten
    the English, use font "10", or add lines.
  - Copy the original look: same text colour (sample it), same outline/shadow colour if the Japanese had one.

## Style
- Translate meaning, keep it short. Buttons and headings: Title Case ("Back to Title"). Descriptions: sentence case.
- Leave alone: logos, title logo, company logos, copyright lines, letters/numbers already in Latin, icons, button glyphs (A/B/X/Y/L/R).
- Sprite cells often come in pairs (normal / highlighted, or different palettes). Translate every variant the same way.
- If an image has no Japanese text, skip it. If text cannot be removed cleanly, do your best and report it.
- A `NOTE ... new tiles appended` line in the preview output means the image shares tiles; that's OK.

## UI glossary (keep consistent; story names are in tl/GLOSSARY.md)
| Japanese | English |
|---|---|
| ケッテイ | OK |
| モドル | Back |
| トジル | Close |
| キリカエ | Switch |
| ススム | Next |
| はい / いいえ | Yes / No |
| メニュー | Menu |
| つづきから / はじめから / パスワード | Continue / New Game / Password |
| かんたんモード / ふつうモード | Easy Mode / Normal Mode |
| やさしい / ふつう / むずかしい | Easy / Normal / Hard |
| きけん / クライマックス (difficulties) | Danger / Climax |
| ステージ / ミッション / ワールド | Stage / Mission / World |
| ステージクリアボーナス / クリアボーナス / ミッションボーナス | Stage Clear Bonus / Clear Bonus / Mission Bonus |
| レベルセレクト | Level Select |
| タイトルにもどる / メニューをとじる / モードきりかえ | Back to Title / Close Menu / Switch Mode |
| ライダー / プレイヤー / パートナー | Rider / Player / Partner |
| タイリョク | HP |
| ライダーパワー | Rider Power |
| ひっさつわざ / ちょうひっさつわざ | Finisher / Super Finisher |
| けいけんち | EXP |
| コイン | Coins |
| ライフチャージ | Life Charge |
| オートセーブ | Autosave |
| ダッシュ / ジャンプ / ガード / いどう | Dash / Jump / Guard / Move |
| ノーマルアタック / ハードアタック | Normal Attack / Hard Attack |
| ライダーアビリティ | Rider Ability |
| キャラみぎむきのばあい | (when facing right) |
| デンゲンをきって、DSカードをさしこみなおしてください | Turn the power off and reinsert the DS Card. |
| DSカードをぬかないでください | Do not remove the DS Card. |
| Rider names | Rider 1, Rider 2, V3, Riderman, X, Amazon, Stronger, Skyrider, Super-1, ZX, BLACK, BLACK RX, Shin, ZO, J, Kuuga, Agito, Ryuki, Faiz, Blade, Hibiki, Kabuto, Den-O, Kiva, Decade, W, OOO, Birth, Fourze |
