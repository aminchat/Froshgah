from froshgah.extract import extract_stores, normalize_phone


def test_normalize_phone_variants():
    assert normalize_phone("09121234567") == "09121234567"
    assert normalize_phone("+989121234567") == "09121234567"
    assert normalize_phone("00989121234567") == "09121234567"
    assert normalize_phone("989121234567") == "09121234567"
    assert normalize_phone("9121234567") == "09121234567"
    assert normalize_phone("۰۹۱۲۱۲۳۴۵۶۷") == "09121234567"
    assert normalize_phone("02188776655") == "02188776655"
    assert normalize_phone("abc") is None


def test_no_signal_returns_empty():
    assert extract_stores("سلام، حالت چطوره؟", source="instagram", username="someone") == []
    assert extract_stores("", source="telegram") == []


def test_phone_and_city_and_categories():
    stores = extract_stores(
        "فروشگاه پوشاک زنانه - مانتو و شلوار\nتماس: ۰۹۱۲۱۲۳۴۵۶۷ - تهران",
        source="telegram",
        username="shop_teh",
        title="فروشگاه پوشاک شاپ تهران",
        url="https://t.me/shop_teh/12",
    )
    assert stores, "باید حداقل یک فروشگاه استخراج شود"
    s = stores[0]
    assert "09121234567" in s.phones
    assert s.city == "تهران"
    assert "پوشاک" in s.categories
    assert "مانتو" in s.categories
    assert s.source_key == "shop_teh"


def test_instagram_url_handle():
    stores = extract_stores(
        "پوشاک مردانه اینجا: instagram.com/mens_shop90 جدیدترین‌ها",
        source="instagram",
        username="author_page",
        url="https://www.instagram.com/p/ABC/",
    )
    keys = {(s.source, s.source_key) for s in stores}
    assert ("instagram", "mens_shop90") in keys
    assert ("instagram", "author_page") in keys


def test_wa_me_phone():
    stores = extract_stores(
        "فروشگاه کفش و کیف - سفارش در واتساپ wa.me/989121234567",
        source="telegram",
        username="shoes_shop",
    )
    assert stores[0].phones == ["09121234567"]


def test_tg_link_and_bare_mention_defaults_to_source():
    stores = extract_stores(
        "پوشاک بچگانه، کانال ما t.me/kids_cloth و پیج اینستا @kids_ig",
        source="telegram",
        username="main_ch",
    )
    keys = {(s.source, s.source_key) for s in stores}
    assert ("telegram", "kids_cloth") in keys
    assert ("instagram", "kids_ig") in keys


def test_category_only_signal_without_username():
    stores = extract_stores("فروشگاه اینترنتی پوشاک مجلسی زنانه", source="instagram")
    assert len(stores) == 1
    assert stores[0].source_key  # کلید یکتا از متن ساخته می‌شود


def test_single_mention_gets_phones():
    stores = extract_stores(
        "مانتو شیک، سفارش: 09351112233 - پیج: @manto_shop",
        source="instagram",
        username="blogger1",
    )
    mention = next(s for s in stores if s.username == "manto_shop")
    assert mention.phones == ["09351112233"]
