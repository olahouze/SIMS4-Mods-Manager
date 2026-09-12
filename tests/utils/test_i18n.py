import json
from pathlib import Path
from src.i18n import I18nManager, tr, SUPPORTED_LANGUAGES, DEFAULT_LANGUAGE


def test_supported_languages():
    assert "fr" in SUPPORTED_LANGUAGES
    assert "en" in SUPPORTED_LANGUAGES
    assert "es" in SUPPORTED_LANGUAGES
    assert DEFAULT_LANGUAGE == "fr"
    assert SUPPORTED_LANGUAGES["fr"]["flag"] == "🇫🇷"
    assert SUPPORTED_LANGUAGES["en"]["flag"] == "🇬🇧"
    assert SUPPORTED_LANGUAGES["es"]["flag"] == "🇪🇸"


def test_locale_files_valid_and_parity():
    locales_dir = Path(__file__).parents[2] / "src" / "i18n" / "locales"

    # Load all three json files
    with open(locales_dir / "fr.json", "r", encoding="utf-8") as f:
        fr_data = json.load(f)
    with open(locales_dir / "en.json", "r", encoding="utf-8") as f:
        en_data = json.load(f)
    with open(locales_dir / "es.json", "r", encoding="utf-8") as f:
        es_data = json.load(f)

    def get_all_keys(data, prefix=""):
        keys = set()
        for k, v in data.items():
            full_key = f"{prefix}.{k}" if prefix else k
            if isinstance(v, dict):
                keys.update(get_all_keys(v, full_key))
            else:
                keys.add(full_key)
        return keys

    fr_keys = get_all_keys(fr_data)
    en_keys = get_all_keys(en_data)
    es_keys = get_all_keys(es_data)

    assert len(fr_keys) > 0

    # Ensure key parity across languages
    missing_in_en = fr_keys - en_keys
    missing_in_es = fr_keys - es_keys

    assert not missing_in_en, f"Keys present in fr.json but missing in en.json: {missing_in_en}"
    assert not missing_in_es, f"Keys present in fr.json but missing in es.json: {missing_in_es}"


def test_translation_lookup_and_interpolation():
    mgr = I18nManager.instance()

    # Test French
    mgr.set_language("fr")
    assert mgr.get_language() == "fr"
    assert "Catalogue" in tr("catalog.title")
    assert tr("installed.badge_count", count=5) == "5 mod(s)"

    # Test English
    mgr.set_language("en")
    assert mgr.get_language() == "en"
    assert "Catalog" in tr("catalog.title")
    assert tr("installed.badge_count", count=5) == "5 mod(s)"

    # Test Spanish
    mgr.set_language("es")
    assert mgr.get_language() == "es"
    assert "Catálogo" in tr("catalog.title")
    assert tr("installed.badge_count", count=5) == "5 mod(s)"

    # Reset to default
    mgr.set_language("fr")


def test_translation_fallback():
    mgr = I18nManager.instance()
    mgr.set_language("es")

    # Non-existent key falls back to key itself or default argument
    assert tr("non.existent.key") == "non.existent.key"
    assert tr("non.existent.key", default="Default Text") == "Default Text"

    mgr.set_language("fr")


def test_language_callback_notification():
    mgr = I18nManager.instance()
    notifications = []

    def on_lang_change(lang):
        notifications.append(lang)

    mgr.register_callback(on_lang_change)
    mgr.set_language("en")
    assert "en" in notifications

    mgr.unregister_callback(on_lang_change)
    mgr.set_language("fr")
