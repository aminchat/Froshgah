#!/usr/bin/env bash
# جمع‌آوری فروشگاه‌ها + ساخت سایت + کامیت و پوش روی همین شاخه.
# داخل Codespaces کافی است بنویسید:  ./scripts/collect-and-publish.sh
#
# متغیرهای قابل تنظیم:
#   IG_TAGS        هشتگ‌های اینستاگرام با کاما (بدون #)
#   IG_KEYWORDS    کلیدواژه‌های اینستاگرام با کاما (به هشتگ تبدیل می‌شوند)
#   TG_QUERIES     عبارت‌های جستجوی تلگرام با کاما
#   LIMIT          حداکثر پست/پیام برای هر عبارت
#   NO_BIOS=1      بیوی نویسنده‌ها خوانده نشود (سریع‌تر)
#   DRY_RUN=1      فقط بساز، کامیت/پوش نکن
set -uo pipefail
cd "$(dirname "$0")/.."

PY="${PYTHON:-python}"
command -v "$PY" >/dev/null 2>&1 || PY=python3

IG_TAGS="${IG_TAGS-پوشاک,مانتو,فروشگاه_پوشاک}"
IG_KEYWORDS="${IG_KEYWORDS-}"
TG_QUERIES="${TG_QUERIES-فروشگاه پوشاک,مزون مانتو}"
LIMIT="${LIMIT-25}"
EXTRA=""
[ "${NO_BIOS:-0}" = "1" ] && EXTRA="--no-bios"

echo "▶ جمع‌آوری | IG: «$IG_TAGS» + «$IG_KEYWORDS» | TG: «$TG_QUERIES» | limit: $LIMIT"
"$PY" -m froshgah run \
  --ig-tags "$IG_TAGS" \
  --ig-keywords "$IG_KEYWORDS" \
  --tg-queries "$TG_QUERIES" \
  --limit "$LIMIT" \
  --data data/stores.json --site docs $EXTRA \
  || echo "⚠️ جمع‌آوری با خطا/محدودیت تمام شد؛ نتایج قبلی دست‌نخورده می‌ماند."

echo
"$PY" -m froshgah stats

BRANCH="$(git rev-parse --abbrev-ref HEAD)"
git add data docs
if git diff --cached --quiet; then
  echo "✓ تغییری نبود؛ چیزی پوش نشد."
  exit 0
fi
if [ "${DRY_RUN:-0}" = "1" ]; then
  echo "🧪 DRY_RUN: کامیت و پوش انجام نشد."; git status --short data docs; exit 0
fi
git -c user.name="${GIT_NAME:-froshgah-bot}" -c user.email="${GIT_EMAIL:-froshgah-bot@users.noreply.github.com}" \
  commit -q -m "data: به‌روزرسانی فروشگاه‌ها ($(date -u '+%Y-%m-%d %H:%M UTC'))"
git pull --rebase --autostash origin "$BRANCH" >/dev/null 2>&1 || true
git push origin "HEAD:$BRANCH" && echo "✅ پوش شد؛ سایت GitHub Pages تا ۱–۲ دقیقه دیگر به‌روز می‌شود."
