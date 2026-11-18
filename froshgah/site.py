"""ساخت سایت ایستا (HTML/JS خالص) از روی فایل داده‌ها — برای GitHub Pages."""
from __future__ import annotations

import shutil
from pathlib import Path

from .config import ROOT_DIR
from .export import export_json

WEB_DIR = ROOT_DIR / "web"


def build_site(db, data_file: str | Path, out_dir: str | Path = "docs") -> Path:
    """پوشه `web/` را در `out_dir` کپی و فایل داده را کنارش می‌گذارد."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    src = Path(WEB_DIR)
    if not src.exists():
        raise SystemExit(f"پوشه وب پیدا نشد: {src}")
    for name in sorted(p.name for p in src.iterdir()):
        if name in {"data"}:
            continue
        item = src / name
        target = out / name
        if item.is_dir():
            shutil.copytree(item, target, dirs_exist_ok=True)
        else:
            shutil.copy2(item, target)
    data_dir = out / "data"
    data_dir.mkdir(exist_ok=True)
    export_json(db, data_dir / "stores.json")
    # تا Jekyll فایل‌ها را دست نزند
    (out / ".nojekyll").write_text("", encoding="utf-8")
    site_json = (data_dir / "stores.json").resolve()
    target = Path(data_file).resolve()
    if target != site_json:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(site_json, target)
    return out
