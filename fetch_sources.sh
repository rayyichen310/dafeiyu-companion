#!/usr/bin/env bash
# Download every upstream source of the dafeiyu-companion plugin at its pinned revision
# into <HERMES_HOME>/companion-data. Every downloaded file is checked against the SHA-256
# below before it is unpacked, executed or moved into place; a mismatch aborts the script.
# Existing packs and a verified memes.db are kept. HERMES_HOME defaults to two levels above
# this script, i.e. the Hermes home (or profile) whose plugins/ directory holds the plugin.
# Usage: bash fetch_sources.sh [packs|memewiki|jokes|opencc|all]   (default: all)
set -euo pipefail
here="$(dirname "$(readlink -f "$0")")"
data="${HERMES_HOME:-$here/../..}/companion-data"
mkdir -p "$data"
cd "$data"
echo "data directory: $(pwd)"
what="${1:-all}"

PACKS_REPO=yyh-001/dsh-meme-packs
MEMEWIKI_REPO=thawline/dsh-memewiki
MEMEWIKI_SHA=e377a9b87d2bcb6fee8f22e31afc2bf72ee3f5a4
MEMEWIKI_DB_SHA256=5d1d1857985b1d5602b886ed8ec79759a97b41451c1a855c354d7b2d9b820c4a
LINEBOT_REPO=Hanson0901/dsh-line-bot
LINEBOT_SHA=87d5bea0d76546f132cf95cadf52e8f74c28e23a
OPENCC_REPO=BYVoid/OpenCC
OPENCC_SHA=fae2a0a911c30764e669a7d8b0591cd8e852934a

# get <repo> <commit> <path> <sha256> <dest>: download one file at a pinned commit, verify
# its SHA-256, and only then move it to <dest>.
get() {
  local tmp; tmp="$(mktemp)"
  curl -sSL --fail -o "$tmp" "https://raw.githubusercontent.com/$1/$2/$3"
  if ! echo "$4  $tmp" | sha256sum -c --status -; then
    rm -f "$tmp"; echo "SHA-256 mismatch: $1@$2:$3" >&2; exit 1
  fi
  mv "$tmp" "$5"
}

fetch_packs() {
  declare -A SHA=(
    [dafeiyu-001-v1.3.0]=9fca6a4fc101232b39ab79181b9ed1b12289cf4890b3fadac89576545e51b3a4
    [dafeiyu-learned-v1.1.1]=62ce5dbd8175e9947e2af73c92098f851730ccd82ca1e3018362249c62fe9eb8
    [pack-mvc2p5cv-v1.0.0]=34265f752716343c76802a4111770718bce568a81176786762feb4df82fca6a5
    [dafeiyu-2-emotes-v1.0.0]=fec3d7c61106f5db4a9b5e42561169834a627404326d5fd8b3c7ec34165ab07f
    [dafeiyu-blue-emotes-v1.0.1]=1d36fc417720ea54c60df1259bc300d5785322bfccf9302bd88a3946e0dde3f2)
  mkdir -p meme-packs
  tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' RETURN
  for t in "${!SHA[@]}"; do
    [ -f "meme-packs/$t/manifest.json" ] && { echo "pack $t: present"; continue; }
    curl -sSL --fail -o "$tmp/$t.zip" "https://github.com/$PACKS_REPO/releases/download/$t/$t.zip"
    echo "${SHA[$t]}  $tmp/$t.zip" | sha256sum -c -
    mkdir -p "meme-packs/$t"; unzip -qo "$tmp/$t.zip" -d "meme-packs/$t"
  done
}

fetch_memewiki() {
  mkdir -p memewiki
  if ! { [ -f memewiki/memes.db ] && echo "$MEMEWIKI_DB_SHA256  memewiki/memes.db" | sha256sum -c - >/dev/null 2>&1; }; then
    get $MEMEWIKI_REPO $MEMEWIKI_SHA data/memes.db $MEMEWIKI_DB_SHA256 memewiki/memes.db
  fi
  get $MEMEWIKI_REPO $MEMEWIKI_SHA LICENSE \
    4769abdc93544fe5de3969d17e02c81682c2c56b74b061ee0cba7a2aed708142 memewiki/LICENSE
  get $MEMEWIKI_REPO $MEMEWIKI_SHA NOTICE \
    4fd46fe7df29ac1657afca19279591cffa67e8653804148609008b8f59c9a713 memewiki/NOTICE
}

fetch_jokes() {
  mkdir -p jokes
  get $LINEBOT_REPO $LINEBOT_SHA LICENSE \
    e64222dc3110cbd90a415921608150bf522d104f22bdec8f8b3ac98562b5778a jokes/LICENSE-dsh-line-bot
  # DEFAULTS array of lib/jokes.mjs, evaluated verbatim (no rewording). Node runs only the
  # copy whose SHA-256 matches the reviewed revision.
  local src=jokes/.jokes.mjs
  get $LINEBOT_REPO $LINEBOT_SHA lib/jokes.mjs \
    ca2d3b31435e74199fff2d93321d9492a9855dfc7a91310af7edfe1bbddde0cd "$src"
  node -e '
    let s = require("fs").readFileSync(0, "utf8");
    const a = s.indexOf("const DEFAULTS = ["), b = s.indexOf("\n]\n", a);
    const arr = new Function("return " + s.slice(a + "const DEFAULTS = ".length, b + 2))();
    process.stdout.write(JSON.stringify(arr, null, 2) + "\n");
  ' < "$src" > jokes/dsh-line-bot-jokes-defaults.json
  rm -f "$src"
}

fetch_opencc() {
  # Character-level Traditional->Simplified table (Apache-2.0), used only to fold
  # queries for matching against the simplified-Chinese meme wiki.
  mkdir -p opencc
  get $OPENCC_REPO $OPENCC_SHA data/dictionary/TSCharacters.txt \
    9ff46a7d30e5765375eb13d33f2b03a34d298913caf2b120380679f33ae1642d opencc/TSCharacters.txt
  get $OPENCC_REPO $OPENCC_SHA LICENSE \
    b534e465949558eec2597b04f5092b5e161236a68dfbfd04d547592ac3964308 opencc/LICENSE
}

case "$what" in
  packs) fetch_packs ;;
  memewiki) fetch_memewiki ;;
  jokes) fetch_jokes ;;
  opencc) fetch_opencc ;;
  all) fetch_packs; fetch_memewiki; fetch_jokes; fetch_opencc ;;
  *) echo "usage: $0 [packs|memewiki|jokes|opencc|all]"; exit 2 ;;
esac
