# 資料來源與授權

[English](data-sources.md) | **繁體中文**

plugin 讀的圖片、梗百科和玩梗素材都不在這個 repo 裡。`fetch_sources.sh` 依下表的釘選版本下載到
`<HERMES_HOME>/companion-data/` 並驗證 SHA-256；已下載的圖庫和驗證過的 `memes.db` 會略過。

```bash
bash <HERMES_HOME>/plugins/dafeiyu-companion/fetch_sources.sh [packs|memewiki|jokes|opencc|all]   # 預設 all
```

## 上游來源與釘選

| 用途 | 上游 | 釘選 | 授權 | 位置（在 `companion-data/` 下） |
|---|---|---|---|---|
| 表情包 | [yyh-001/dsh-meme-packs](https://github.com/yyh-001/dsh-meme-packs) release `dafeiyu-001-v1.3.0`（24 張 JPG） | zip SHA-256 `9fca6a4fc101232b39ab79181b9ed1b12289cf4890b3fadac89576545e51b3a4`，942,084 B | personal | `meme-packs/dafeiyu-001-v1.3.0/` |
| 表情包 | 同上 release `dafeiyu-learned-v1.1.1`（31 張 JPG） | `62ce5dbd8175e9947e2af73c92098f851730ccd82ca1e3018362249c62fe9eb8`，3,516,925 B | personal | `meme-packs/dafeiyu-learned-v1.1.1/` |
| 表情包 | 同上 release `pack-mvc2p5cv-v1.0.0`「GPT生大肥鱼」（18 張 PNG） | `34265f752716343c76802a4111770718bce568a81176786762feb4df82fca6a5`，8,152,792 B | CC-BY-NC-SA-4.0，署名 Anterique0 | `meme-packs/pack-mvc2p5cv-v1.0.0/` |
| 表情包 | 同上 release `dafeiyu-2-emotes-v1.0.0`（239 張 GIF，300×300） | `fec3d7c61106f5db4a9b5e42561169834a627404326d5fd8b3c7ec34165ab07f`，170,699,011 B | noncommercial-fan（EmoteLab EULA；角色上善无形、ZipZipPipe；模型 0x4682B4） | `meme-packs/dafeiyu-2-emotes-v1.0.0/` |
| 表情包 | 同上 release `dafeiyu-blue-emotes-v1.0.1`（157 張 GIF，400×400） | `1d36fc417720ea54c60df1259bc300d5785322bfccf9302bd88a3946e0dde3f2`，135,559,054 B | noncommercial-fan（同上；轉碼 yyh-001） | `meme-packs/dafeiyu-blue-emotes-v1.0.1/` |
| 梗百科 | [thawline/dsh-memewiki](https://github.com/thawline/dsh-memewiki) `e377a9b87d2bcb6fee8f22e31afc2bf72ee3f5a4`，`data/memes.db`（6696 條） | SHA-256 `5d1d1857985b1d5602b886ed8ec79759a97b41451c1a855c354d7b2d9b820c4a`，16,834,560 B | 程式 MIT；詞庫版權歸原作者與 cnmeme.wiki（見 `memewiki/NOTICE`） | `memewiki/` |
| 玩梗種子 | [Hanson0901/dsh-line-bot](https://github.com/Hanson0901/dsh-line-bot) `87d5bea0d76546f132cf95cadf52e8f74c28e23a`，`lib/jokes.mjs` 的 `DEFAULTS`（24 則）；注入文案也取自同檔 `contextText` | — | MIT | `jokes/dsh-line-bot-jokes-defaults.json`、`jokes/LICENSE-dsh-line-bot` |
| 玩梗（wanjiqi，預設關） | [Chu-Xin-r/wanjiqi-meme](https://github.com/Chu-Xin-r/wanjiqi-meme) `de4eac5ba5275ba08012fa71619298b19e9dcae6`，`skills/wanjiqi-meme/assets/memes_top100.json`（100 則，長度 4～40 的 60 則可用，篩法同 dsh-line-bot `host.mjs` 的 `joke-import-wanjiqi`） | — | MIT | `jokes/wanjiqi-memes_top100.json`、`jokes/LICENSE-wanjiqi-meme` |
| 繁→簡比對表 | [BYVoid/OpenCC](https://github.com/BYVoid/OpenCC) `fae2a0a911c30764e669a7d8b0591cd8e852934a`，`data/dictionary/TSCharacters.txt`（單字層級，只用來比對，不轉換輸出） | — | Apache-2.0 | `opencc/` |

圖庫張數（zip 內 `index.db`）與 `memes/` 實際檔案數一致：24、31、18、239、157，無缺檔。
各圖庫的 `manifest.json`（授權、署名、來源）與 `index.db`（每張圖的分類 tag、caption、keywords）隨 zip 下載、原樣保留；
plugin 用自己附的 `caption-overrides.json` 取代其中的分類和描述。這些圖庫只供自己的 bot 使用，不可商用，也不可再散布。

## 動態圖格式

五套圖庫全部是原生格式：JPEG（55）、PNG（18，非 APNG）、GIF（396）。Discord 直接播放 GIF，所以**沒有轉檔**。
單檔最大 2,370,925 B（遠低於 Discord 上傳上限），沒有超過 8 MB 的檔案。
