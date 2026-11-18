"""مدل داده فروشگاه."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Store:
    """یک فروشگاه (یا حساب مرتبط با پوشاک) استخراج‌شده از اینستاگرام/تلگرام."""

    source: str  # 'instagram' | 'telegram'
    source_key: str  # کلید یکتا داخل همان منبع (یوزرنیم یا لینک پست)
    title: str = ""
    username: str = ""
    url: str = ""
    text: str = ""
    phones: list[str] = field(default_factory=list)
    instagram: str = ""
    telegram: str = ""
    website: str = ""
    city: str = ""
    categories: list[str] = field(default_factory=list)
