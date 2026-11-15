# Data sources and licenses

**English** | [繁體中文](data-sources.zh-TW.md)

The images, the meme wiki and the joke seeds the plugin reads are not in this repository.
`fetch_sources.sh` downloads them at the pinned versions below into `<HERMES_HOME>/companion-data/`
Every downloaded file, LICENSE and NOTICE files included, is checked against the SHA-256 in the
table below or in the script before it is unpacked, run or moved into place; a mismatch aborts
the script. Packs already present and a verified `memes.db` are skipped.

```bash
bash <HERMES_HOME>/plugins/dafeiyu-companion/fetch_sources.sh [packs|memewiki|jokes|opencc|all]   # default: all
```

## Upstream sources and pins

| Use | Upstream | Pin | License | Location (under `companion-data/`) |
|---|---|---|---|---|
| Stickers | [yyh-001/dsh-meme-packs](https://github.com/yyh-001/dsh-meme-packs) release `dafeiyu-001-v1.3.0` (24 JPG) | zip SHA-256 `9fca6a4fc101232b39ab79181b9ed1b12289cf4890b3fadac89576545e51b3a4`, 942,084 B | personal | `meme-packs/dafeiyu-001-v1.3.0/` |
| Stickers | same, release `dafeiyu-learned-v1.1.1` (31 JPG) | `62ce5dbd8175e9947e2af73c92098f851730ccd82ca1e3018362249c62fe9eb8`, 3,516,925 B | personal | `meme-packs/dafeiyu-learned-v1.1.1/` |
| Stickers | same, release `pack-mvc2p5cv-v1.0.0` "GPT生大肥鱼" (18 PNG) | `34265f752716343c76802a4111770718bce568a81176786762feb4df82fca6a5`, 8,152,792 B | CC-BY-NC-SA-4.0, by Anterique0 | `meme-packs/pack-mvc2p5cv-v1.0.0/` |
| Stickers | same, release `dafeiyu-2-emotes-v1.0.0` (239 GIF, 300×300) | `fec3d7c61106f5db4a9b5e42561169834a627404326d5fd8b3c7ec34165ab07f`, 170,699,011 B | noncommercial-fan (EmoteLab EULA; character 上善无形, ZipZipPipe; model 0x4682B4) | `meme-packs/dafeiyu-2-emotes-v1.0.0/` |
| Stickers | same, release `dafeiyu-blue-emotes-v1.0.1` (157 GIF, 400×400) | `1d36fc417720ea54c60df1259bc300d5785322bfccf9302bd88a3946e0dde3f2`, 135,559,054 B | noncommercial-fan (as above; transcoded by yyh-001) | `meme-packs/dafeiyu-blue-emotes-v1.0.1/` |
| Meme wiki | [thawline/dsh-memewiki](https://github.com/thawline/dsh-memewiki) `e377a9b87d2bcb6fee8f22e31afc2bf72ee3f5a4`, `data/memes.db` (6,696 entries) | SHA-256 `5d1d1857985b1d5602b886ed8ec79759a97b41451c1a855c354d7b2d9b820c4a`, 16,834,560 B | code MIT; entries belong to their authors and cnmeme.wiki (see `memewiki/NOTICE`) | `memewiki/` |
| Joke seeds | [Hanson0901/dsh-line-bot](https://github.com/Hanson0901/dsh-line-bot) `87d5bea0d76546f132cf95cadf52e8f74c28e23a`, the `DEFAULTS` array of `lib/jokes.mjs` (24 seeds); the injected wording also comes from `contextText` in that file | `lib/jokes.mjs` SHA-256 `ca2d3b31435e74199fff2d93321d9492a9855dfc7a91310af7edfe1bbddde0cd`, checked before Node extracts the array | MIT | `jokes/dsh-line-bot-jokes-defaults.json`, `jokes/LICENSE-dsh-line-bot` |
| Traditional → Simplified matching table | [BYVoid/OpenCC](https://github.com/BYVoid/OpenCC) `fae2a0a911c30764e669a7d8b0591cd8e852934a`, `data/dictionary/TSCharacters.txt` (character level; used for matching only, never to convert output) | SHA-256 `9ff46a7d30e5765375eb13d33f2b03a34d298913caf2b120380679f33ae1642d` | Apache-2.0 | `opencc/` |

The image count in each pack's `index.db` matches the files in its `memes/`: 24, 31, 18, 239 and
157. Each pack's `manifest.json` (license, credits, source) and `index.db` (category tag, caption
and keywords per image) come with the zip and stay as downloaded; the plugin replaces the
categories and captions with its own `caption-overrides.json`. The packs are for your own bot
only: no commercial use and no redistribution.

## Image formats

All packs are used as published: JPEG (55), PNG (18, not APNG) and GIF (396). Discord plays GIFs
inline, so nothing is converted. The largest file is 2,370,925 B.
