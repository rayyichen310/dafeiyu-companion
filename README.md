# dafeiyu-companion

**English** | [繁體中文](README.zh-TW.md)

Companion features for a Hermes chat bot that plays 大肥魚 (Dafeiyu, a tsundere, food-loving AI fish)
on Discord: reaction stickers, a Chinese internet-meme wiki, joke seeds and a persona reminder.

The sticker part is the main one. The chat model does not choose stickers. Before each reply is
sent, a small model (deepseek-flash) reads the reply, decides whether 大肥魚 would react to it,
and picks one image from about 470 captioned stickers.

## What it does

| Hermes surface | Behaviour |
|---|---|
| `pre_llm_call` hook | If the user asks about a meme and the wiki has it, appends that one wiki entry to the turn. Otherwise appends 2–3 joke seeds. Always appends a one-line persona reminder. |
| `transform_llm_output` hook | Steps 1–4 of the [sticker pipeline](#sticker-pipeline): clean the reply, decide, pick, attach the sticker. |
| `llm_request` middleware | Step 5: shows earlier stickers to the chat model as `[貼圖：<caption>]`. |
| Tool `search_meme_wiki` | Looks up a meme, slang word or abbreviation in the offline wiki (6,696 entries, simplified Chinese). |
| Tool `companion_switch` | Turns each feature on or off from the chat ("關掉表情包"). |

All hooks act only on the platforms listed in the config (Discord by default).

## Sticker pipeline

![This turn: the chat model writes the reply; the plugin cleans it, decides, picks a sticker and appends a MEDIA line. Next turn: the chat model sees that line as the sticker's caption.](docs/sticker-flow.svg)

1. **Clean.** Only the sticker picked below should be sent, but the chat model sees earlier stickers
   as `[貼圖：<caption>]` notes (step 5) and may write one itself. Any such note, `[[meme:…]]`
   marker or sticker `MEDIA:` line in the reply is removed, so it never shows up as text or as a
   second image.
2. **Decide.** deepseek-flash reads this turn's user message and the reply. It answers `不貼`
   (no sticker), or two lines: the reply's most emotional sentence, quoted as written, and the
   single reaction it shows in 15 characters or fewer, for example `被打臉、自嘲吃癟` (proven wrong, laughing at itself).
3. **Pick.** deepseek-flash picks one image for that sentence and reaction. The last 10 stickers
   sent, across all sessions, are left out. There are two modes:
   - **Full list** (default): every caption is in the system prompt in a fixed order, so the
     prompt cache covers almost all of it. The recent stickers are named in the user message.
     If the model picks a recent one anyway, or the call fails, a random unused image is sent.
   - **Embedding**: set `meme_embed_url`. The reaction is embedded and only the 8 captions whose
     "適合：" (when to use) part is closest are offered. If the call fails, the closest one is sent.
4. **Send.** Append `MEDIA:<absolute path>` to the reply. Hermes's Discord adapter uploads the
   file; GIFs play inline. The transcript keeps the `MEDIA:` line.
5. **Next turn.** The `llm_request` middleware shows each stored sticker line to the chat model as
   `[貼圖：<full caption>]`, for example `[貼圖：張嘴輕咬一口，表情俏皮；適合：開玩笑假裝要咬人時]`.
   The model knows which sticker it sent and can refer to it, but sees neither the image nor the
   path.

If the decision or the embedding lookup fails or times out, the reply goes out without a sticker
and the error is logged. All timeouts together stay inside Hermes's 30 s plugin hook limit.

## Accuracy and cost

Measured offline on real 大肥魚 Discord replies, with deepseek-flash prices (USD per million
tokens: 0.15 input, 0.003 input served from cache, 0.6 output).

**Accuracy.** 60 replies that had a sticker live. For each reply, the caption chosen by each
mode was shown to Claude Sonnet among other candidates, in random order and without saying where
it came from, and scored 1–5 for fit. The judge read the caption text, not the image.

| Mode | Mean score | Scored ≥4 | Scored ≤2 |
|---|---|---|---|
| Full list | 2.95 | 19/60 | 21/60 |
| Embedding, top 8 | 2.73 | 13/60 | 26/60 |

**When to post.** 109 Discord replies, labelled by Sonnet as should post (14), either way (31)
or should not post (64). In each of two runs, the decision posted on 12 of the 14 "should" and
on 10 of the 64 "should not".

**Cost, prompt cache included.** The decision runs on every reply; the pick runs only when a
sticker is sent.

| Step | Cost (USD) | Share of prompt tokens served from cache | Latency, median / max |
|---|---|---|---|
| Decide, per reply | 0.000186 | 54% | 1.8 / 9.6 s |
| Pick, full list, per sticker | 0.000285 | 97% | 2.4 / 8.8 s |
| Pick, full list, per sticker, if the API had no cache | ≈0.0020 | 0% | — |
| Pick, embedding top 8, per sticker | 0.000161 | 0% | 1.7 / 4.3 s |

At an assumed 30 stickers per 100 replies, decide + full list costs about USD 0.027 per 100
replies, and decide + embedding about USD 0.023. The embedding service itself is not counted.
The full-list system prompt is about 12,000 tokens. After the cache expires (some hours
without use), the next pick pays about USD 0.0018 to write it again.

**Recommendation.**

- API with a prefix cache (DeepSeek and others): use the full list. It is the most accurate.
- API without a cache: the full list costs about 7 times more per sticker. If you run an
  embedding service, use the embedding mode.
- Much larger sticker library: the full-list prompt grows with the library; the embedding mode
  does not.

## Requirements

- Hermes Agent with the plugin hooks above (developed against v0.22.5).
- A DeepSeek API key with access to `deepseek-flash`, in the environment or in
  `<HERMES_HOME>/.env` as `DEEPSEEK_API_KEY`. The model and endpoint are fixed in `meme_marker.py`.
- Optional, for the embedding mode: a [Text Embeddings Inference](https://github.com/huggingface/text-embeddings-inference)
  `/embed` endpoint. Developed with Qwen3-Embedding-8B.
- Python standard library only; no extra packages.
- For `fetch_sources.sh`: bash, curl, unzip, sha256sum, and Node.js (used once to extract the
  joke seeds).

## Setup

1. Install and enable the plugin. The install asks for `DEEPSEEK_API_KEY` and saves it to
   `<HERMES_HOME>/.env`.

   ```bash
   hermes plugins install rayyichen310/dafeiyu-companion
   hermes plugins enable dafeiyu-companion
   ```

   Without the CLI: clone this repository to `<HERMES_HOME>/plugins/dafeiyu-companion/` and add
   `dafeiyu-companion` to `plugins.enabled` in `config.yaml`.
2. Add the `dafeiyu_companion` toolset to the platforms that should have the two tools
   (`platform_toolsets` in `config.yaml`).
3. Tell the chat model, in its persona or context file, that stickers are added automatically and
   its replies should be text only. This plugin does not add that instruction itself.
4. Download the images, the meme wiki and the other sources (about 320 MB) into
   `<HERMES_HOME>/companion-data/`. The script uses pinned versions and checks their SHA-256:

   ```bash
   bash <HERMES_HOME>/plugins/dafeiyu-companion/fetch_sources.sh all
   ```

5. Restart the gateway.

## Configuration

`<HERMES_HOME>/config/companion.json`. It is read on every turn, so changes apply on the next
turn without a restart. A missing file means the defaults.
A file that cannot be read or has a wrong type turns every feature off and logs an error.

| Key | Default | Meaning |
|---|---|---|
| `memes` | `true` | Stickers |
| `memewiki` | `true` | Meme wiki injection and the `search_meme_wiki` tool |
| `jokes` | `true` | Joke seeds |
| `jokes_wanjiqi` | `false` | Add the cruder wanjiqi joke source to the seeds |
| `platforms` | `["discord"]` | Platforms the hooks act on |
| `meme_embed_url` | `""` | Empty: full-list pick. A TEI `/embed` URL: embedding pick. Without a restart, the first sticker afterwards also builds the caption index (about 10 s); after a restart it is built at startup. |

```json
{
  "memes": true,
  "memewiki": true,
  "jokes": true,
  "jokes_wanjiqi": false,
  "platforms": ["discord"],
  "meme_embed_url": ""
}
```

### Data files

- `caption-overrides.json`, in this plugin directory: the caption and category of every image
  (`"<pack>/<path>": {"tag", "caption"}`). It always replaces the caption and category in the
  upstream `index.db`, which stays as downloaded. Tag `skip` removes an image. The captions were
  rewritten by Claude Haiku in the form `<what the picture shows>；適合：<when to send it>`.

In `<HERMES_HOME>/companion-data/`, written by `fetch_sources.sh` and the plugin:

- `meme-packs/`: 5 sticker packs, 469 images, each with the upstream `index.db` and `manifest.json`.
- `recent-stickers.json`: the last 10 stickers sent. Written by the plugin.
- `memewiki/memes.db`, `jokes/`, `opencc/`: meme wiki, joke seeds, and a character table used to
  match Traditional Chinese text against the simplified-Chinese wiki.

## Network, files and privacy

- **DeepSeek API** (`https://api.deepseek.com`): on every reply on an enabled platform, this
  turn's user message (up to 500 characters) and the reply (up to 2,000) are sent for the
  decision. When a sticker is sent, the quoted sentence, the reaction and the captions are sent
  for the pick. Nothing is sent when `memes` is off.
- **Embedding endpoint**: only when `meme_embed_url` is set: the reaction text and, once per
  startup, all captions.
- **Reads**: `<HERMES_HOME>/.env` (only the `DEEPSEEK_API_KEY` line) when the variable is not
  set, and `<HERMES_HOME>/companion-data/`.
- **Writes**: `<HERMES_HOME>/config/companion.json` (via `companion_switch`) and
  `<HERMES_HOME>/companion-data/recent-stickers.json`.
- No shell commands. One short-lived background thread builds the caption index in the
  embedding mode.

## Licenses of the bundled data

The sticker packs are fan works for personal, non-commercial use and may not be
redistributed (some are CC BY-NC-SA 4.0). The images are therefore downloaded, not committed.
The meme wiki code is MIT and its entries belong to their authors and cnmeme.wiki. Sources,
pinned versions and the license of each: [docs/data-sources.md](docs/data-sources.md).

## Tests

```bash
cd <HERMES_HOME>/plugins/dafeiyu-companion
python3 -I -m unittest discover -s tests -q
```

Run them after `fetch_sources.sh`: they read the meme wiki, the joke seeds and the matching table
from `<HERMES_HOME>/companion-data/`. DeepSeek and the embedding service are replaced with fakes,
so the tests need no network.
