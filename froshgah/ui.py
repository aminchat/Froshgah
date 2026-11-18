"""نمایش نتایج فروشگاه (مشترک بین CLI و ربات)."""
from __future__ import annotations

import html


def format_store(d: dict, index: int | None = None, as_html: bool = False) -> str:
    esc = html.escape if as_html else (lambda s: str(s))
    lines: list[str] = []
    head = f"{index}. " if index is not None else ""
    title = d.get("title") or d.get("username") or "فروشگاه بدون نام"
    lines.append(f"{head}🏪 {esc(title)}")
    if d.get("city"):
        lines.append(f"  📍 {esc(d['city'])}")
    if d.get("phones"):
        lines.append(f"  📱 {' · '.join(d['phones'])}")
    if d.get("instagram"):
        lines.append(f"  📸 @{esc(d['instagram'])}")
    if d.get("telegram"):
        lines.append(f"  ✈️ @{esc(d['telegram'])}")
    if d.get("website"):
        lines.append(f"  🌐 {esc(d['website'])}")
    if d.get("url"):
        lines.append(f"  🔗 {esc(d['url'])}")
    if d.get("categories"):
        lines.append(f"  🏷 {esc('، '.join(d['categories'][:8]))}")
    meta = " · ".join(x for x in [d.get("source", ""), d.get("last_seen", "")] if x)
    if meta:
        lines.append(f"  ⏱ {esc(meta)}")
    return "\n".join(lines)
