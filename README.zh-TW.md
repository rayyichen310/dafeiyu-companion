# dafeiyu-companion

[English](README.md) | **繁體中文**

給在 Discord 上扮演大肥魚（一條傲嬌、愛吃的 AI 胖魚）的 Hermes 聊天機器人用的陪聊功能。

| 功能 | 做什麼 | 開關 |
|---|---|---|
| [反應貼圖](#反應貼圖) | 每則回覆送出前，由 deepseek-flash 判斷大肥魚會不會有反應，再從 469 張附描述的貼圖挑一張。 | `memes` |
| [梗百科](#梗百科) | 使用者問某個梗時，把那一條加進這一輪；主模型也能用 `search_meme_wiki` 工具自己查。 | `memewiki` |
| [玩梗素材](#玩梗素材) | 每輪提供主模型 2～3 則梗。 | `jokes` |
| [人設提醒](#人設提醒) | 每輪加一行，維持人設語氣。 | 一律開啟 |

使用者可以在聊天裡開關各項功能（例如「關掉表情包」），主模型會呼叫 `companion_switch` 工具。
所有功能只在[設定](#設定)列出的平台作用（預設只有 Discord）。

## 反應貼圖

![這一輪：主模型寫回覆，plugin 清理、判斷、挑圖並加上 MEDIA 行。下一輪：主模型看到的是那張貼圖的描述。](docs/sticker-flow.zh-TW.svg)

1. **清理**：刪掉主模型自己在回覆裡寫的貼圖註記、`[[meme:…]]` 標記和貼圖 `MEDIA:` 行。
2. **判斷**：deepseek-flash 讀這一輪的使用者訊息和回覆，回答「不貼」，或照抄回覆裡情緒最明顯的
   那一句，並寫出那一句表現的反應（15 字以內，例如「被打臉、自嘲吃癟」）。
3. **挑圖**：deepseek-flash 依那一句和反應挑一張。跨所有 session 最近送出的 10 張不列入。
   - **全列**（預設）：全部描述放在 system prompt，幾乎整段都能吃到 prompt 快取。仍挑到最近用過的、
     或呼叫失敗時，改送一張沒用過的隨機圖片。
   - **向量**（設定 `meme_embed_url`）：只列出跟反應最接近的 8 張；呼叫失敗時送最接近的那張。
4. **送出**：在回覆最後加一行 `MEDIA:<絕對路徑>`，由 Hermes 的 Discord adapter 上傳，GIF 直接播放。
5. **下一輪**：主模型看到的先前貼圖是它的描述，例如 `[貼圖：張嘴輕咬一口，表情俏皮；適合：開玩笑假裝要咬人時]`，
   所以能接著聊自己貼過的圖。

判斷或挑圖失敗、逾時時，回覆照常送出、不附貼圖，錯誤寫進 log。

### 準確度與成本

用大肥魚真實的 Discord 回覆離線量測。

**挑哪張**：60 則線上有貼圖的回覆，由 Claude Sonnet 在不知道來源的情況下，替兩種模式挑的圖依搭配程度
評 1～5 分。評審讀的是描述，沒有看圖片。

| 模式 | 平均分 | 4 分以上 | 2 分以下 |
|---|---|---|---|
| 全列 | 2.95 | 19/60 | 21/60 |
| 向量取 8 張 | 2.73 | 13/60 | 26/60 |

**該不該貼**：109 則回覆中，Sonnet 標註該貼 14 則、不該貼 64 則。判斷跑兩次，每次都在該貼的 14 則裡
貼了 12 則，在不該貼的 64 則裡貼了 10 則。

**成本**，用 deepseek-flash 價格（每百萬 token 美元：輸入 0.15、命中快取的輸入 0.003、輸出 0.6）：

| 步驟 | 費用（美元） | prompt token 命中快取的比例 | 回應時間（中位數／最慢） |
|---|---|---|---|
| 判斷，每則回覆 | 0.000186 | 54% | 1.8／9.6 秒 |
| 挑圖，全列，每張貼圖 | 0.000285 | 97% | 2.4／8.8 秒 |
| 挑圖，全列，每張貼圖，API 沒有快取 | 約 0.0020 | 0% | — |
| 挑圖，向量取 8 張，每張貼圖 | 0.000161 | 0% | 1.7／4.3 秒 |

每 100 則回覆貼 30 張時，全列約 0.027 美元，向量約 0.023 美元（不含 embedding 服務本身）。

API 有 prefix 快取（例如 DeepSeek）就用全列；沒有快取或圖庫大很多時，用向量模式。

## 梗百科

離線的中文網路梗百科，6,696 條，簡體中文。繁體訊息會逐字轉成簡體再比對。

- **自動加入**：訊息在問某個梗（「去碼頭整點薯條是什麼梗」），或整則訊息只有一個 2～10 字、梗百科
  查得到的詞時，把那一條加進這一輪。加入的是一段簡短規則（照梗接話，被問才解釋）和詞條的用法與意思，
  共 270～1,040 字，中位數 560 字。日常短詞可能對到不相干的詞條，例如 `hi` 會對到 `hide`。
- **工具**：主模型可以用 `search_meme_wiki` 查任何詞。

## 玩梗素材

沒有加入梗百科的那一輪，從 24 則梗隨機抽 2～3 則，每則附適用場合，例如「急了（對方被戳到跳腳、
開始連珠炮時）」。主模型被要求一次最多用一個、不解釋、使用者難過時不用。每輪加 110～160 字。

## 人設提醒

每輪最後加一行「【語氣】照大肥魚人設說話：傲嬌、口癖、偶爾犯蠢，內容照常準確。」
工具呼叫多的長對話裡，靠這行維持人設檔定下的語氣。

## 需求

- Hermes Agent v0.22.5 以上，已在 v0.22.5 和 v0.23.1 測過。
- 貼圖需要：能用 `deepseek-flash` 的 DeepSeek API key，設為 `DEEPSEEK_API_KEY`。
- 選用，向量挑圖才需要：[Text Embeddings Inference](https://github.com/huggingface/text-embeddings-inference)
  的 `/embed` endpoint。開發時用 Qwen3-Embedding-8B。
- 執行 `fetch_sources.sh` 需要 bash、curl、unzip、sha256sum 和 Node.js。

plugin 只用 Python 標準函式庫。

## 安裝

1. 安裝並啟用 plugin。安裝時會詢問 `DEEPSEEK_API_KEY`，存進 `<HERMES_HOME>/.env`。

   ```bash
   hermes plugins install rayyichen310/dafeiyu-companion
   hermes plugins enable dafeiyu-companion
   ```

2. 在 `config.yaml` 的 `platform_toolsets` 裡，替要用這兩個工具的平台加上 `dafeiyu_companion` toolset。
3. 在主模型的人設或規則檔寫明「貼圖由系統自動附加，回覆只寫文字」。
4. 下載貼圖、梗百科和玩梗素材（約 320 MB）到 `<HERMES_HOME>/companion-data/`。腳本用釘選版本並驗證 SHA-256：

   ```bash
   bash <HERMES_HOME>/plugins/dafeiyu-companion/fetch_sources.sh all
   ```

5. 重啟 gateway。

## 設定

設定檔是 `<HERMES_HOME>/config/companion.json`，每輪讀取，改了下一輪就生效。沒有這個檔案就用預設值；
檔案讀不了或型別錯誤時，所有功能關閉並寫一筆錯誤 log。

```json
{
  "memes": true,
  "memewiki": true,
  "jokes": true,
  "platforms": ["discord"],
  "meme_embed_url": ""
}
```

| 欄位 | 意思 |
|---|---|
| `memes`、`memewiki`、`jokes` | 各功能開關。`memewiki` 也管工具。 |
| `platforms` | 功能作用的平台。 |
| `meme_embed_url` | 空字串：全列挑圖。填 TEI `/embed` 網址：向量挑圖。不重啟就設定的話，之後第一張貼圖要多花約 10 秒建描述索引。 |

要改某張貼圖的描述或排除它，改 plugin 資料夾裡的 `caption-overrides.json`
（`"<圖庫>/<路徑>": {"tag", "caption"}`；分類填 `skip` 會排除該圖）。

## 網路、檔案與隱私

- **DeepSeek API**（`https://api.deepseek.com`），只在 `memes` 開啟時：啟用平台上的每則回覆，都會送出
  這一輪的使用者訊息（最多 500 字）和回覆（最多 2,000 字）；要貼圖時再送出那一句、反應和圖片描述。
- **Embedding 服務**，只在設定 `meme_embed_url` 時：送出反應文字，每次啟動另送一次全部描述。
- **讀取**：經由 Hermes 的 secret scope 讀 `DEEPSEEK_API_KEY`，以及 `<HERMES_HOME>/companion-data/`。
- **寫入**：`<HERMES_HOME>/config/companion.json`（經由 `companion_switch`）和
  `<HERMES_HOME>/companion-data/recent-stickers.json`（最近 10 張貼圖）。
- 不執行 shell 指令。向量模式會開一條短暫的背景執行緒建描述索引。

## 來源與授權

| 功能 | 來源 | 原樣使用 | 這裡改了什麼 |
|---|---|---|---|
| 貼圖 | [yyh-001/dsh-meme-packs](https://github.com/yyh-001/dsh-meme-packs)，5 套 | 圖片 | 描述由 Claude Haiku 重寫（`caption-overrides.json`）。判斷和挑圖是這個 plugin 自己的。 |
| 梗百科 | [thawline/dsh-memewiki](https://github.com/thawline/dsh-memewiki) | 詞條、查詢與觸發規則、詞條格式、規則文字 | 改寫成 Python；加上繁體比對。 |
| 繁簡字表 | [BYVoid/OpenCC](https://github.com/BYVoid/OpenCC) | 字表，只用來比對 | — |
| 玩梗素材 | [Hanson0901/dsh-line-bot](https://github.com/Hanson0901/dsh-line-bot) `lib/jokes.mjs` | 24 則梗和適用場合 | 指示重寫。上游的限制只保留「使用者難過時不用」；上游另外規定正經話題和第一次聊天時不用、用不上就別用，並禁止貶低、地域、性別、疾病和政治相關的梗。 |
| 人設提醒 | 這個 plugin | — | — |

plugin 程式碼是 MIT（[LICENSE](LICENSE)）。貼圖是同人作品，只供個人非商業使用、不可再散布（部分為
CC BY-NC-SA 4.0），所以圖片用下載的、不進 git。梗百科程式是 MIT，詞條版權屬原作者與 cnmeme.wiki。
dsh-line-bot 是 MIT，OpenCC 是 Apache-2.0。釘選版本與檢查碼見
[docs/data-sources.zh-TW.md](docs/data-sources.zh-TW.md)。

## 測試

先跑過 `fetch_sources.sh` 再測；DeepSeek 和 embedding 服務以假的代替。

```bash
cd <HERMES_HOME>/plugins/dafeiyu-companion
python3 -I -m unittest discover -s tests -q
```
