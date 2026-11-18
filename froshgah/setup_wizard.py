"""راهنمای تعاملی ساخت فایل .env — رمزها در همین رایانه می‌مانند."""
from __future__ import annotations

import getpass
import os
import re
import sys
from pathlib import Path

from .config import ROOT_DIR

# (کلید، متن سؤال، راهنما، مخفی‌بودن)
FIELDS: tuple[tuple[str, str, str, bool], ...] = (
    ("IG_USERNAME", "نام کاربری اینستاگرام", "اختیاری؛ بدون آن ناشناس و با نتایج کمتر کار می‌کند", False),
    ("IG_PASSWORD", "رمز اینستاگرام", "اختیاری", True),
    ("TG_API_ID", "TG_API_ID تلگرام", "از my.telegram.org → API development tools (یک عدد است)", False),
    ("TG_API_HASH", "TG_API_HASH تلگرام", "از همان صفحه (شناسه برنامه است، رمز حساب شما نیست)", True),
    ("TELEGRAM_BOT_TOKEN", "توکن ربات تلگرام", "اختیاری؛ فقط برای اجرای ربات، از @BotFather", True),
    ("TELEGRAM_OWNER_ID", "شناسه عددی تلگرام شما", "اختیاری؛ از @userinfobot (فقط عدد)", False),
    ("REQUEST_DELAY", "فاصله بین درخواست‌ها (ثانیه)", "پیش‌فرض 2؛ روی سرور ابری 3 یا بیشتر بهتر است", False),
)

_INT_KEYS = {"TG_API_ID", "TELEGRAM_OWNER_ID"}
_KEYS = {k for k, *_ in FIELDS}


def read_env_file(path: Path) -> dict[str, str]:
    """مقادیر فایل .env را می‌خواند (برای اینکه مقدار قبلی به‌عنوان پیش‌فرض پیشنهاد شود)."""
    out: dict[str, str] = {}
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        out[key.strip()] = val.strip().strip('"').strip("'")
    return out


def ask(prompt: str, hint: str, default: str, secret: bool, input_fn=None) -> str:
    label = prompt + (f" [{default}]" if default else "")
    if hint:
        label += f" — {hint}"
    label += ": "
    if secret and default:
        label += "(Enter = بدون تغییر) "
    if secret and sys.stdin.isatty():
        raw = getpass.getpass(label)
    elif input_fn is not None:
        raw = input_fn(label)
    else:
        raw = input(label)
    return (raw or "").strip() or default


def build_env(existing: dict[str, str], answers: dict[str, str]) -> str:
    merged = dict(existing)
    for key, value in answers.items():
        if value:
            merged[key] = value
    lines = ["# ساخته‌شده با `python -m froshgah setup` — این فایل به گیت اضافه نمی‌شود."]
    for key, *_ in FIELDS:
        if key in merged:
            lines.append(f"{key}={merged[key]}")
    for key in sorted(set(merged) - _KEYS):
        lines.append(f"{key}={merged[key]}")
    return "\n".join(lines) + "\n"


def mask(value: str) -> str:
    if not value:
        return "(تنظیم نشده)"
    if len(value) <= 4:
        return "•" * len(value)
    return f"{value[:2]}{'•' * 4}{value[-2:]}"


def status(path: Path | None = None, out=None) -> None:
    out = out or sys.stdout
    path = path or (ROOT_DIR / ".env")
    values = read_env_file(path)
    for key, prompt, _hint, secret in FIELDS:
        val = values.get(key) or os.getenv(key, "")
        shown = mask(val) if (secret or key == "TELEGRAM_BOT_TOKEN") else (val or "(تنظیم نشده)")
        print(f"  {prompt:<28} {shown}", file=out)
    print(f"  فایل: {path} ({'وجود دارد' if path.exists() else 'ساخته نشده'})", file=out)


def run_setup(path: Path | None = None, input_fn=None, out=None, use_env: bool = False) -> dict:
    """سؤال‌ها را می‌پرسد و .env را می‌سازد. خروجی: کلیدهایی که مقدار گرفتند (بدون مقدار)."""
    out = out or sys.stdout
    path = path or (ROOT_DIR / ".env")
    existing = read_env_file(path)
    answers: dict[str, str] = {}
    for key, prompt, hint, secret in FIELDS:
        default = existing.get(key, "") or (os.getenv(key, "") if use_env else "")
        if use_env:
            value = default
        else:
            value = ask(prompt, hint, default, secret, input_fn=input_fn)
        if value and key in _INT_KEYS:
            value = re.sub(r"\D", "", value)
        if value:
            answers[key] = value

    path.write_text(build_env(existing, answers), encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass
    print(f"\n✅ نوشته شد: {path}", file=out)
    print("   تنظیم‌شده: " + ("، ".join(sorted(answers)) or "هیچ‌کدام"), file=out)
    print("   از این لحاظ لازم نیست کاری بکنید؛ هر فرمان بعدی خودش از همین فایل می‌خواند.", file=out)
    return answers
