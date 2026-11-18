"""ساخت سایت ایستا (HTML/JS خالص) از روی فایل داده‌ها.

دو مقصد:
  * `docs/`          → برای GitHub Pages (فقط فایل ایستا، بدون سرویس)
  * `vercel/public/` → برای سرویس وب روی Vercel (همان فایل‌ها + تنظیم پنل جمع‌آوری)
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from .config import ROOT_DIR
from .export import export_json

WEB_DIR = ROOT_DIR / "web"
CONFIG_MARKER = "<!--FROSHGAH_CONFIG-->"

VERCEL_CONFIG = {
    "api": True,
    "data": "/api/data",
    "login": "/login",
    "status": "/api/status",
}


def _copy_assets(out: Path) -> None:
    src = Path(WEB_DIR)
    if not src.exists():
        raise SystemExit(f"پوشه وب پیدا نشد: {src}")
    for name in sorted(p.name for p in src.iterdir()):
        if name == "data":
            continue
        item = src / name
        target = out / name
        if item.is_dir():
            shutil.copytree(item, target, dirs_exist_ok=True)
        else:
            shutil.copy2(item, target)


def build_site(db, data_file: str | Path, out_dir: str | Path = "docs", public: bool = False) -> Path:
    """فایل‌های `web/` را در مقصد می‌گذارد و داده را کنارشان می‌نویسد."""
    out = Path(out_dir) / "public" if public else Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    _copy_assets(out)

    index = out / "index.html"
    if index.exists():
        html = index.read_text(encoding="utf-8")
        if public and CONFIG_MARKER in html:
            html = html.replace(
                CONFIG_MARKER,
                "<script>window.FROSHGAH=" + json.dumps(VERCEL_CONFIG, ensure_ascii=False) + "</script>",
            )
        elif CONFIG_MARKER in html:
            html = html.replace(CONFIG_MARKER, "<!-- پنل جمع‌آوری فقط در نسخه سرویس‌دار فعال است -->")
        index.write_text(html, encoding="utf-8")

    data_dir = out / "data"
    if public:
        # در نسخه سرویس‌دار داده از /api/data (پشت قفل لاگین) خوانده می‌شود؛
        # اگر data/stores.json هم کنار فایل‌های عمومی بماند، از قفل رد می‌زند.
        shutil.rmtree(data_dir, ignore_errors=True)
        export_json(db, data_file)
    else:
        data_dir.mkdir(exist_ok=True)
        export_json(db, data_dir / "stores.json")
        site_json = (data_dir / "stores.json").resolve()
        target = Path(data_file).resolve()
        if target != site_json:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(site_json, target)
    (out / ".nojekyll").write_text("", encoding="utf-8")  # تا Jekyll فایل‌ها را دست نزند
    return out
