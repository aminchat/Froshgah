"""رمزنگاری بارِ ارسالی پنل وب (AES-256-GCM) و بازگشت اطلاعات به سرویس وب.

جریان کار: فرمِ روی سایت → سرور Vercel مقدارها را با کلید APP_SECRET رمزنگاری می‌کند
و به‌عنوان `inputs.payload` به GitHub Actions می‌دهد → همین‌جا باز می‌شوند.
رمزها هیچ‌جا ذخیره نمی‌شوند و در لاگ هم چاپ نمی‌شوند.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import urllib.error
import urllib.request

MAX_BYTES = 24 * 1024


def _key(secret: str | bytes) -> bytes:
    if isinstance(secret, bytes):
        raw = secret
    else:
        raw = str(secret).encode("utf-8")
    if not raw:
        raise ValueError("کلید خالی است؛ APP_SECRET را تنظیم کنید.")
    return hashlib.sha256(raw).digest()


def encrypt(data: dict, secret: str | bytes) -> str:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    iv = os.urandom(12)
    ct = AESGCM(_key(secret)).encrypt(iv, json.dumps(data, ensure_ascii=False).encode("utf-8"), None)
    return base64.b64encode(iv + ct).decode("ascii")


def decrypt(token: str, secret: str | bytes) -> dict:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    raw = base64.b64decode(str(token).strip().encode("ascii"))
    if len(raw) < 28:
        raise ValueError("بار ارسالی کوتاه/خراب است.")
    iv, blob = raw[:12], raw[12:]
    plain = AESGCM(_key(secret)).decrypt(iv, blob, None)
    out = json.loads(plain.decode("utf-8"))
    if not isinstance(out, dict):
        raise ValueError("ساختار بار ارسالی نامعتبر است.")
    return out


def load_payload(value: str) -> str:
    """مقدار گزینه --payload را می‌خواند: یا خودِ متن base64، یا @path."""
    value = (value or "").strip()
    if value.startswith("@"):
        with open(value[1:], "rb") as fh:
            return fh.read().decode("ascii").strip()
    return value


def post_json(url: str, token: str, data: dict, timeout: int = 60, opener=None) -> tuple[bool, str]:
    """نتیجه را به سرویس وب برمی‌گرداند (برای نصب‌هایی که داده‌شان در گیت‌هاب نیست)."""
    body = json.dumps(data, ensure_ascii=False).encode("utf-8")
    if len(body) > MAX_BYTES * 8:
        return False, "خروجی برای ارسال خیلی بزرگ است"
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "content-type": "application/json",
            "user-agent": "froshgah-runner",
            **({"x-froshgah-token": token} if token else {}),
        },
    )
    try:
        resp = (opener or urllib.request.urlopen)(req, timeout=timeout)
        code = getattr(resp, "status", None) or resp.getcode()
        return 200 <= code < 300, f"HTTP {code}"
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code}"
    except Exception as e:  # noqa: BLE001
        return False, str(e)
