# All Kamen Rider: Rider Generation — English translation glossary

## Hard rules for game text
- ASCII only. No curly quotes, no "…" character (write `...`), no em dash (write `-`), no full-width letters.
- Dialogue lines (tl/script/*.json): max **34 characters** per line (6px font, ~204px box). Run
  `python tools/krtl.py check` from the project folder to validate.
- One English line per Japanese line. Lines that follow each other form one text box (usually 2 lines),
  so a sentence may be split across the two lines like the Japanese does.
- Each JSON entry is a *unique* Japanese line. The same line can appear in several variants with different
  neighbours, so the English line must still read correctly wherever it is used (see *.context.txt).
- Japanese "……" -> "...". Keep "！！" as "!!" when shouting. Keep the tone of each speaker.

## Script variants
Every stage script (01_00 … 05_01) has 30 variants. Variant N is the conversation when rider N (list below)
leads the team, so the hero-side lines in variant N are spoken by that rider, in that rider's voice.

| # | Japanese | English | who / voice |
|---|----------|---------|-------------|
| 0 | １ごう | Rider 1 | Takeshi Hongo, scientist, calm and heroic |
| 1 | ２ごう | Rider 2 | Hayato Ichimonji, photographer, cocky |
| 2 | Ｖ３ | V3 | Shiro Kazami, fiery |
| 3 | ライダーマン | Riderman | Joji Yuki, scientist |
| 4 | Ｘ | X | Keisuke Jin |
| 5 | アマゾン | Amazon | wild, simple speech |
| 6 | ストロンガー | Stronger | Shigeru Jo, boastful |
| 7 | スカイライダー | Skyrider | Hiroshi Tsukuba |
| 8 | スーパー１ | Super-1 | Kazuya Oki |
| 9 | ＺＸ | ZX | Ryo Murasame |
| 10 | ＢＬＡＣＫ | BLACK | Kotaro Minami |
| 11 | ＢＬＡＣＫ ＲＸ | BLACK RX | Kotaro Minami |
| 12 | シン | Shin | |
| 13 | ＺＯ | ZO | |
| 14 | Ｊ | J | |
| 15 | クウガ | Kuuga | Yusuke Godai, cheerful |
| 16 | アギト | Agito | Shoichi Tsugami, easygoing |
| 17 | りゅうき | Ryuki | Shinji Kido, earnest |
| 18 | ファイズ | Faiz | Takumi Inui, blunt |
| 19 | ブレイド | Blade | Kazuma Kenzaki |
| 20 | ヒビキ | Hibiki | relaxed big brother |
| 21 | カブト | Kabuto | Souji Tendou, arrogant ("Grandma said...") |
| 22 | デンオウ | Den-O | Momotaros, rude and loud |
| 23 | キバ | Kiva | Wataru / Kivat |
| 24 | ディケイド | Decade | Tsukasa Kadoya, smug |
| 25 | Ｗ | W | Shotaro & Philip |
| 26 | Ｗ（しょうたろう） | W (Shotaro) | hard-boiled wannabe |
| 27 | Ｗ（フィリップ） | W (Philip) | curious |
| 28 | オーズ | OOO | Eiji Hino, kind |
| 29 | バース | Birth | Akira Date |

Other speakers / names
- ジェネラル・シャドウ = General Shadow; ネオせいめいたい = Neo-Organism; アポロガイスト = Apollo Geist;
  シャドームーン = Shadow Moon; ジュダ = Juda; くずヤミー = Waste Yummy; キバット = Kivat; フォーゼ = Fourze
- かめんライダー = Kamen Rider; ライダー = Rider; しょくん = "my fellow" / "gentlemen"
- ゴルゴム = Gorgom; せいきおう = Century King; ブラックサン = Black Sun; こうたろう = Kotaro
- ＧＯＤ（ゴッド）ひみつけいさつ だいいちしつちょう = GOD Secret Police First Chief
- デンライナー = DenLiner; ジカンケイサツ = Time Police; じかんはんざいしゃ = time criminal
- ショッカー = Shocker; あくのそしき = evil organizations; かいじん = monsters; かんぶ = executives
- ほんごうたけし = Takeshi Hongo
- Den-O catchphrases: オレ、さんじょう！ = "Here I come!" ; さいしょからクライマックスだぜ = "I'm at my climax from the start!"

Game terms
- ライフチャージ = Life Charge; ひっさつわざ = Finisher; ちょうひっさつわざ = Super Finisher
- なんいど = difficulty; 「きけん」 = "Danger"; 「クライマックス」 = "Climax"; コイン = coins
- ワールド = World; ステージ = Stage; ショップ = Shop; ボス = Boss; タイリョク = HP
