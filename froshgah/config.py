"""پیکربندی پروژه از طریق فایل .env."""
from __future__ import annotations

import os
from dataclasses import dataclass, fields, replace
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent


def _load_dotenv(path: Path) -> None:
    try:
        from dotenv import load_dotenv

        load_dotenv(path)
        return
    except ImportError:
        pass
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        os.environ.setdefault(key, val)


_load_dotenv(ROOT_DIR / ".env")


def _env_int(name: str, default: int = 0) -> int:
    try:
        return int(os.getenv(name, "") or default)
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, "") or default)
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str
    owner_id: int
    db_path: Path
    tg_api_id: int
    tg_api_hash: str
    tg_session_path: str
    ig_username: str
    ig_password: str
    request_delay: float


def get_settings() -> Settings:
    return Settings(
        telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", "").strip(),
        owner_id=_env_int("TELEGRAM_OWNER_ID"),
        db_path=Path(os.getenv("DB_PATH", "") or (ROOT_DIR / "froshgah.db")),
        tg_api_id=_env_int("TG_API_ID"),
        tg_api_hash=os.getenv("TG_API_HASH", "").strip(),
        tg_session_path=os.getenv("TG_SESSION_PATH", "") or str(ROOT_DIR / "froshgah"),
        ig_username=os.getenv("IG_USERNAME", "").strip(),
        ig_password=os.getenv("IG_PASSWORD", "").strip(),
        request_delay=_env_float("REQUEST_DELAY", 1.5),
    )


_INT_FIELDS = {"owner_id", "tg_api_id"}
_FLOAT_FIELDS = {"request_delay"}


def apply_overrides(**values) -> Settings:
    """در زمان اجرا چند کلید را عوض می‌کند (برای باری که پنل web می‌فرستد).

    فقط در همین پروسه و همین حافظه می‌ماند؛ فایل .env دست‌نخورده است.
    """
    global settings
    data = {}
    for f in fields(Settings):
        new = values.get(f.name)
        current = getattr(settings, f.name)
        if new in (None, "", b""):
            data[f.name] = current
            continue
        if f.name in _INT_FIELDS:
            digits = "".join(ch for ch in str(new) if ch.isdigit())
            data[f.name] = int(digits) if digits else current
        elif f.name in _FLOAT_FIELDS:
            try:
                data[f.name] = float(new)
            except (TypeError, ValueError):
                data[f.name] = current
        elif f.name == "db_path":
            data[f.name] = Path(str(new))
        else:
            data[f.name] = str(new)
    settings = Settings(**data)
    return settings


settings = get_settings()
