#!/bin/bash
# 招待コードの入れ替え（GOPIPE_JOIN_CODES）
#
# なぜ要るか: 招待コードを知っている人は誰でも、その組織にユーザーを作れる（web/src/app/api/signup/route.ts）。
#            スクショ・チャット・ログに一度でも写ったら、その場で入れ替える。
#
# 使い方:  ./scripts/rotate-join-code.sh HARUKI
#          （第1引数＝.secrets.local のキー接頭辞。例: HARUKI → HARUKI_JOIN_CODE）
#
# このスクリプトがやること:
#   1. 新しいコードを作る
#   2. web/.env.local と .secrets.local の中身を書き換える（**画面には出さない**）
#   3. Vercel の GOPIPE_JOIN_CODES を production / preview / development すべて差し替える
#   4. 新コードを**クリップボードに入れる**（画面に出さずにLINEへ貼れる）
# やらないこと: 本番デプロイ（最後に自分で `vercel --prod` を打つ）
set -euo pipefail
cd "$(dirname "$0")/.."

WHO="${1:-HARUKI}"
KEY="${WHO}_JOIN_CODE"
ENVFILE="web/.env.local"
SECFILE=".secrets.local"

command -v vercel >/dev/null || { echo "vercel CLI が見つかりません"; exit 1; }
[ -f "$ENVFILE" ] || { echo "$ENVFILE がありません"; exit 1; }
[ -f "$SECFILE" ] || { echo "$SECFILE がありません"; exit 1; }

OLD=$(grep -E "^${KEY}=" "$SECFILE" | head -1 | cut -d= -f2- | tr -d '"' | tr -d "'")
[ -n "$OLD" ] || { echo "$SECFILE に ${KEY} がありません"; exit 1; }

NEW=$(openssl rand -hex 8)

# --- JSON の中の「旧コードというキー」を新コードへ差し替える（slug/name はそのまま） ---
CUR=$(grep -E "^GOPIPE_JOIN_CODES=" "$ENVFILE" | head -1 | cut -d= -f2-)
NEXT=$(OLD="$OLD" NEW="$NEW" CUR="$CUR" python3 - <<'PY'
import json, os, sys
cur = os.environ["CUR"].strip().strip("'").strip('"')
old, new = os.environ["OLD"], os.environ["NEW"]
d = json.loads(cur) if cur else {}
if old not in d:
    sys.stderr.write("旧コードが GOPIPE_JOIN_CODES に見つかりません。中身を確認してください。\n"); sys.exit(2)
d[new] = d.pop(old)                      # 会社（slug/name）はそのまま引き継ぐ
print(json.dumps(d, ensure_ascii=False, separators=(",", ":")))
PY
)

# --- ローカルの2ファイルを書き換え（値は表示しない） ---
python3 - "$ENVFILE" "$SECFILE" "$KEY" "$NEW" "$NEXT" <<'PY'
import io, re, sys
envfile, secfile, key, new, nextjson = sys.argv[1:6]
s = io.open(envfile, encoding="utf-8").read()
s = re.sub(r"^GOPIPE_JOIN_CODES=.*$", "GOPIPE_JOIN_CODES=" + nextjson.replace("\\", "\\\\"), s, flags=re.M)
io.open(envfile, "w", encoding="utf-8").write(s)
t = io.open(secfile, encoding="utf-8").read()
t = re.sub(r"^%s=.*$" % re.escape(key), f"{key}={new}", t, flags=re.M)
io.open(secfile, "w", encoding="utf-8").write(t)
PY

# --- Vercel の env を3環境とも差し替え（非対話・値は標準入力から流す） ---
for TARGET in production preview development; do
  vercel env rm GOPIPE_JOIN_CODES "$TARGET" --yes >/dev/null 2>&1 || true
  printf '%s' "$NEXT" | vercel env add GOPIPE_JOIN_CODES "$TARGET" >/dev/null
  echo "  ✓ Vercel env 更新: $TARGET"
done

printf '%s' "$NEW" | pbcopy
echo
echo "完了。新しい ${KEY} は **クリップボード** に入っています（画面には出していません）。"
echo "  1) このあと  vercel --prod  で本番へ反映"
echo "  2) LINEに ⌘V で貼って、はるき様へお渡しください"
echo "  3) 旧コードは無効です（もう誰も使えません）"
