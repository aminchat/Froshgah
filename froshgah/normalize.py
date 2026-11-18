"""نرمال‌سازی متن فارسی/عربی برای جستجوی دقیق."""
from __future__ import annotations

import re

# حروف عربی → فارسی + ارقام عربی/فارسی → لاتین
_CHAR_MAP: dict[int, str] = {
    ord("ي"): "ی",  # ي
    ord("ى"): "ی",  # ى
    ord("ک"): "ک",  # ك
    ord("ة"): "ه",  # ة
    ord("ۀ"): "ه",  # ۀ
    ord("أ"): "ا",  # أ
    ord("إ"): "ا",  # إ
    ord("ٱ"): "ا",  # ٱ
    ord("ؤ"): "و",  # ؤ
    ord("ئ"): "ی",  # ئ
    ord("ـ"): "",  # تطويل
}
for _i in range(10):
    _CHAR_MAP[0x0660 + _i] = str(_i)  # ٠-٩
    _CHAR_MAP[0x06F0 + _i] = str(_i)  # ۰-۹

_DIGIT_MAP: dict[int, str] = {}
for _i in range(10):
    _DIGIT_MAP[0x0660 + _i] = str(_i)
    _DIGIT_MAP[0x06F0 + _i] = str(_i)

_DIACRITICS = re.compile(r"[ً-ْٰـ]")  # اعراب + کشیده
_WS = re.compile(r"\s+")

# نیم‌فاصله و فاصله‌های جدای
_ZW = ("\u200c", "\u200d", "\ufeff")


def fold_digits(text: str | None) -> str:
    """تبدیل ارقام فارسی/عربی به لاتین (بدون تغییر بقیه متن)."""
    if not text:
        return ""
    return str(text).translate(_DIGIT_MAP)


def normalize(text: str | None) -> str:
    """نرمال‌سازی متن برای مقایسه: حروف فارسی، حذف نیم‌فاصله/اعراب، حروف کوچک."""
    if not text:
        return ""
    s = str(text)
    s = s.translate(_CHAR_MAP)
    s = _DIACRITICS.sub("", s)
    for z in _ZW:
        s = s.replace(z, "")
    s = s.lower()
    s = _WS.sub(" ", s).strip()
    return s
