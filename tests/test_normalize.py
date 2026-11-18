from froshgah.normalize import fold_digits, normalize


def test_arabic_to_persian():
    assert normalize("علي يعقوب کاظم") == "علی یعقوب کاظم"
    assert normalize("مطعم") == "مطعام" or normalize("ة") == "ه"


def test_zwnj_removed():
    assert normalize("می\u200cخوام") == "میخوام"
    assert normalize("فروشگاه‌ها") == "فروشگاهها"


def test_digits_folded():
    assert fold_digits("۰۹۱۲۱۲۳۴۵۶۷") == "09121234567"
    assert normalize("۰۹۱۲") == "0912"
    assert normalize("٤٥٦") == "456"


def test_lowercase_latin():
    assert normalize("ShopName") == "shopname"


def test_empty():
    assert normalize(None) == ""
    assert normalize("") == ""
