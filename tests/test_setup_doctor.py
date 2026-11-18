import io
from pathlib import Path

from froshgah import doctor
from froshgah.setup_wizard import build_env, mask, read_env_file, run_setup


def test_read_env_file(tmp_path: Path):
    f = tmp_path / ".env"
    f.write_text('# کامنت\nIG_USERNAME="nika_shop"\nREQUEST_DELAY=3\nخط بدون مساوی\n', encoding="utf-8")
    assert read_env_file(f) == {"IG_USERNAME": "nika_shop", "REQUEST_DELAY": "3"}
    assert read_env_file(tmp_path / "nope") == {}


def test_build_env_keeps_unknown_keys():
    out = build_env({"DB_PATH": "x.db", "IG_USERNAME": "old"}, {"IG_USERNAME": "new"})
    assert "IG_USERNAME=new" in out
    assert "DB_PATH=x.db" in out
    assert out.splitlines()[0].startswith("#")


def test_mask_hides_secrets():
    assert mask("") == "(تنظیم نشده)"
    assert mask("abc") == "•••"
    assert mask("1234567890") == "12••••90"


def test_run_setup_writes_and_keeps_previous(tmp_path: Path):
    env_file = tmp_path / ".env"
    answers = iter(["nika_shop", "secret-pass", "1234567", "abc123hash", "", "", "3"])
    out = io.StringIO()
    got = run_setup(path=env_file, input_fn=lambda _p: next(answers), out=out)
    assert set(got) == {"IG_USERNAME", "IG_PASSWORD", "TG_API_ID", "TG_API_HASH", "REQUEST_DELAY"}
    values = read_env_file(env_file)
    assert values["IG_USERNAME"] == "nika_shop"
    assert values["TG_API_ID"] == "1234567"  # فقط رقم نگه داشته می‌شود
    assert values["REQUEST_DELAY"] == "3"
    assert "ربات" not in out.getvalue()  # پیام‌ها لو ندهند
    assert "secret-pass" not in out.getvalue()

    # اجرای دوم: فقط نام کاربری عوض می‌شود، بقیه از قبل می‌مانند
    answers2 = iter(["new_shop", "", "", "", "", "", ""])
    run_setup(path=env_file, input_fn=lambda _p: next(answers2), out=io.StringIO())
    again = read_env_file(env_file)
    assert again["IG_USERNAME"] == "new_shop"
    assert again["IG_PASSWORD"] == "secret-pass"
    assert again["TG_API_HASH"] == "abc123hash"


def test_run_setup_from_env_no_prompts(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("IG_USERNAME", "env_shop")
    got = run_setup(path=tmp_path / ".env", out=io.StringIO(), use_env=True)
    assert got.get("IG_USERNAME") == "env_shop"


def test_doctor_report(tmp_path: Path, monkeypatch, capsys):
    rows = doctor.check()
    marks = {r[0] for r in rows}
    assert marks <= {doctor.OK, doctor.WARN, doctor.FAIL}
    titles = " ".join(r[1] for r in rows)
    for needed in ("پایتون", "اینستاگرام", "تلگرام", "دیتابیس", "سایت"):
        assert needed in titles
    out = io.StringIO()
    assert doctor.report(out) in (True, False)
    assert "بررسی" not in out.getvalue()  # report فقط جدول را چاپ می‌کند
    capsys.readouterr()
