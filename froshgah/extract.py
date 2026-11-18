"""استخراج اطلاعات فروشگاه‌های پوشاک از متن پست/پیام."""
from __future__ import annotations

import hashlib
import re

from .models import Store
from .normalize import fold_digits, normalize

# ——— الگوها ———
_MOBILE_RE = re.compile(r"(?<!\d)(?:\+?98|0098|98|0)?9\d{9}(?!\d)")
_LANDLINE_RE = re.compile(r"(?<!\d)0\d{2,3}\d{7,8}(?!\d)")
_WA_RE = re.compile(r"(?:https?://)?(?:www\.)?wa\.me/(\d{9,15})", re.I)
_IG_URL_RE = re.compile(r"(?<![\w.-])(?:https?://)?(?:www\.)?instagram\.com/([A-Za-z0-9_.]+)", re.I)
_TG_URL_RE = re.compile(r"(?<![\w.-])(?:https?://)?(?:www\.)?(?:t\.me|telegram\.me)/([A-Za-z0-9_]{3,40})", re.I)
_MENTION_RE = re.compile(r"(?<![\w@])@([A-Za-z0-9_]{3,30})")
_URL_RE = re.compile(r"https?://[^\s<>\"')\]]+", re.I)

_IG_PATH_SKIP = {
    "p", "reel", "reels", "tv", "stories", "explore", "share", "direct",
    "about", "developer", "directory", "legal", "developers",
}
_TG_PATH_SKIP = {
    "joinchat", "share", "addstickers", "addemoji", "addtheme", "proxy",
    "setlanguage", "socks", "login", "join", "addlist", "boost",
}
_SKIP_HANDLES = {"admin", "support", "bot", "me", "username", "share", "joinchat", "self"}

_SOCIAL_DOMAINS = (
    "instagram.com", "t.me", "telegram.me", "telegram.org", "wa.me",
    "twitter.com", "x.com", "facebook.com", "youtube.com", "youtu.be",
    "linkedin.com", "aparat.com", "eitaa.com", "rubika.ir", "bale.ir",
    "gap.im", "my.ir", "tokigram.com",
)

CITIES = [
    "تهران", "اصفهان", "شیراز", "مشهد", "تبریز", "کرج", "اهواز", "قم",
    "ارومیه", "رشت", "زاهدان", "همدان", "کرمان", "یزد", "اردبیل",
    "بندرعباس", "بوشهر", "سنندج", "کرمانشاه", "بیرجند", "یاسوج",
    "زنجان", "ساری", "بابل", "گرگان", "دزفول", "نیشابور", "خرم‌آباد",
    "خوی", "میانه", "ساوه", "ملارد", "پاکدشت", "ورامین", "رودسر",
]

CATEGORY_KEYWORDS = [
    "پوشاک", "لباس", "بوتیک", "فروشگاه", "مانتو", "پیراهن", "شلوار",
    "کفش", "کیف", "مجلسی", "بچگانه", "زنانه", "مردانه", "تیشرت", "جین",
    "چرم", "حجاب", "چادر", "دامن", "ژاکت", "کاپشن", "پالتو", "کراوات",
    "جوراب", "کلاه", "عمده", "حراج", "clothing", "boutique",
    "fashion", "apparel", "shop", "store",
]


def normalize_phone(raw: str | None) -> str | None:
    """نرمال‌سازی شماره تلفن ایران به فرمت 09xxxxxxxxx (یا 021...)."""
    if not raw:
        return None
    d = re.sub(r"\D", "", fold_digits(str(raw)))
    if not d:
        return None
    if d.startswith("0098"):
        d = "0" + d[4:]
    if d.startswith("98") and len(d) == 12:
        d = "0" + d[2:]
    if re.fullmatch(r"9\d{9}", d):
        d = "0" + d
    if re.fullmatch(r"09\d{9}", d) or re.fullmatch(r"0\d{9,10}", d):
        return d
    return None


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out = []
    for x in items:
        if x and x not in seen:
            seen.add(x)
            out.append(x)
    return out


def _has_category(keyword: str, norm: str) -> bool:
    """کلیدواژه لاتین با مرز کلمه، فارسی با تطبیق زیررشته."""
    if keyword.isascii():
        return re.search(rf"\b{re.escape(keyword)}\b", norm) is not None
    return keyword in norm


def _source_key(source: str, username: str, url: str, text: str) -> str:
    if username:
        return username.lower().lstrip("@")
    if url:
        return url.lower()
    return "h" + hashlib.sha1((text or "").encode("utf-8", "ignore")).hexdigest()[:16]


def _classify_mention(handle: str, raw: str, source: str) -> str:
    """طبقه‌بندی @یوزرنیم خالی: تلگرام یا اینستاگرام؟ (بر اساس نزدیک‌ترین راهنما)"""
    norm_raw = normalize(raw)
    low = handle.lower()
    if re.search(rf"t\.me/{re.escape(low)}", norm_raw, re.I) or re.search(
        rf"telegram\.me/{re.escape(low)}", norm_raw, re.I
    ):
        return "telegram"
    if re.search(rf"instagram\.com/{re.escape(low)}", norm_raw, re.I):
        return "instagram"
    m = re.search(rf"@{re.escape(low)}", norm_raw, re.I)
    pos = m.start() if m else len(norm_raw)

    def nearest(pattern: str) -> int | None:
        dists = [abs(mm.start() - pos) for mm in re.finditer(pattern, norm_raw)]
        return min(dists) if dists else None

    ig = nearest(r"اینستا|پیج")
    tg = nearest(r"تلگرام|کانال")
    if ig is not None and (tg is None or ig < tg):
        return "instagram"
    if tg is not None and (ig is None or tg <= ig):
        return "telegram"
    return source


def extract_stores(
    text: str | None,
    *,
    source: str,
    username: str = "",
    title: str = "",
    url: str = "",
) -> list[Store]:
    """استخراج فروشگاه(ها) از یک متن. خروجی: صفر یا چند Store."""
    raw = text or ""
    username = (username or "").lstrip("@")
    body = fold_digits(raw)
    norm = normalize(f"{raw} {title}")

    # ——— تلفن‌ها ———
    phones: list[str] = []
    for m in _MOBILE_RE.finditer(body):
        p = normalize_phone(m.group(0))
        if p:
            phones.append(p)
    for m in _WA_RE.finditer(body):
        p = normalize_phone(m.group(1))
        if p:
            phones.append(p)
    for m in _LANDLINE_RE.finditer(body):
        p = normalize_phone(m.group(0))
        if p:
            phones.append(p)
    phones = _dedupe(phones)

    # ——— هندل‌ها ———
    ig_handles: list[str] = []
    tg_handles: list[str] = []
    for m in _IG_URL_RE.finditer(raw):
        h = m.group(1)
        if h.lower() in _IG_PATH_SKIP or h.lower().startswith("explore"):
            continue
        ig_handles.append(h)
    for m in _TG_URL_RE.finditer(raw):
        h = m.group(1)
        if h.lower() in _TG_PATH_SKIP:
            continue
        tg_handles.append(h)
    for m in _MENTION_RE.finditer(raw):
        h = m.group(1)
        low = h.lower()
        if low in _IG_PATH_SKIP or low in _TG_PATH_SKIP or low in _SKIP_HANDLES:
            continue
        if any(h.lower() == x.lower() for x in ig_handles + tg_handles):
            continue
        if _classify_mention(h, raw, source) == "telegram":
            tg_handles.append(h)
        else:
            ig_handles.append(h)
    ig_handles = _dedupe(ig_handles)
    tg_handles = _dedupe(tg_handles)

    # ——— وب‌سایت ———
    websites: list[str] = []
    for m in _URL_RE.finditer(raw):
        u = m.group(0).rstrip(".,؛!?)»]")
        low = u.lower()
        if any(d in low for d in _SOCIAL_DOMAINS):
            continue
        websites.append(u)
    websites = _dedupe(websites)

    # ——— شهر و دسته‌بندی ———
    city = next((c for c in CITIES if normalize(c) in norm), "")
    categories = _dedupe([k for k in CATEGORY_KEYWORDS if _has_category(k, norm)])

    # ——— سیگنال فروشگاه بودن ———
    has_contact = bool(phones or websites)
    main_ok = has_contact or len(categories) >= 2 or (bool(username) and len(categories) >= 1)

    mentions = [h for h in ig_handles if h.lower() != username.lower()] + [
        h for h in tg_handles if h.lower() != username.lower()
    ]
    mentions = _dedupe(mentions)
    mention_ok = len(categories) >= 1
    # اگر فقط یک هندل غیرنویسنده دارد، تلفن‌ها احتمالاً متعلق به اوست
    mention_phones = phones if len(mentions) == 1 else []

    if not main_ok and not (mentions and mention_ok):
        return []

    first_line = next((ln.strip() for ln in raw.splitlines() if ln.strip()), "")
    if len(first_line) > 70:
        first_line = first_line[:70] + "…"

    stores: list[Store] = []

    if main_ok:
        stores.append(
            Store(
                source=source,
                source_key=_source_key(source, username, url, raw),
                title=(title or username or first_line).strip(),
                username=username,
                url=url,
                text=raw.strip(),
                phones=list(phones),
                instagram=username if source == "instagram" else (ig_handles[0] if ig_handles else ""),
                telegram=username if source == "telegram" else (tg_handles[0] if tg_handles else ""),
                website=websites[0] if websites else "",
                city=city,
                categories=list(categories),
            )
        )

    if mentions and mention_ok:
        for h in mentions:
            src = "telegram" if any(h.lower() == x.lower() for x in tg_handles) else "instagram"
            m_url = f"https://t.me/{h}" if src == "telegram" else f"https://www.instagram.com/{h}/"
            stores.append(
                Store(
                    source=src,
                    source_key=_source_key(src, h, m_url, ""),
                    title=h,
                    username=h,
                    url=m_url,
                    text=raw.strip(),
                    phones=list(mention_phones),
                    instagram=h if src == "instagram" else "",
                    telegram=h if src == "telegram" else "",
                    website="",
                    city=city,
                    categories=list(categories),
                )
            )

    # حذف کلیدهای تکراری داخل همین خروجی
    out: list[Store] = []
    seen: set[tuple[str, str]] = set()
    for s in stores:
        key = (s.source, s.source_key)
        if key in seen:
            continue
        seen.add(key)
        out.append(s)
    return out
