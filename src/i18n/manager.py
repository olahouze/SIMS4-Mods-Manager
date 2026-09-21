import json
import threading
from pathlib import Path
from typing import Dict, Any, Optional

try:
    from PySide6.QtCore import QObject, Signal

    HAS_PYSIDE = True
except ImportError:
    HAS_PYSIDE = False
    QObject = object

    def Signal(*args):  # type: ignore
        return None


SUPPORTED_LANGUAGES = {
    "fr": {"name": "Français", "flag": "🇫🇷", "code": "fr"},
    "en": {"name": "English", "flag": "🇬🇧", "code": "en"},
    "es": {"name": "Español", "flag": "🇪🇸", "code": "es"},
}

DEFAULT_LANGUAGE = "fr"


class _BaseI18nManager(QObject if HAS_PYSIDE else object):  # type: ignore
    if HAS_PYSIDE:
        language_changed = Signal(str)

    _instance: Optional["I18nManager"] = None
    _lock = threading.Lock()

    def __init__(self):
        if HAS_PYSIDE:
            super().__init__()
        self._current_language = DEFAULT_LANGUAGE
        self._translations: Dict[str, Dict[str, Any]] = {}
        self._locales_dir = Path(__file__).parent / "locales"
        self._callbacks = []
        self._load_all_locales()

    def _load_all_locales(self):
        for lang_code in SUPPORTED_LANGUAGES:
            file_path = self._locales_dir / f"{lang_code}.json"
            if file_path.exists():
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        self._translations[lang_code] = json.load(f)
                except Exception:
                    self._translations[lang_code] = {}
            else:
                self._translations[lang_code] = {}

    def get_supported_languages(self) -> Dict[str, Dict[str, str]]:
        return SUPPORTED_LANGUAGES

    def get_language(self) -> str:
        return self._current_language

    def set_language(self, lang_code: str) -> bool:
        if lang_code not in SUPPORTED_LANGUAGES:
            return False
        if lang_code == self._current_language:
            return True

        self._current_language = lang_code

        # Emit PySide6 signal if available
        if HAS_PYSIDE and hasattr(self, "language_changed"):
            self.language_changed.emit(lang_code)

        # Notify any non-Qt listeners
        for cb in self._callbacks:
            try:
                cb(lang_code)
            except Exception:
                pass

        return True

    def register_callback(self, cb):
        if cb not in self._callbacks:
            self._callbacks.append(cb)

    def unregister_callback(self, cb):
        if cb in self._callbacks:
            self._callbacks.remove(cb)

    def tr(self, key: str, default: Optional[str] = None, **kwargs) -> str:
        """
        Retrieves translation for a dot-separated key (e.g. 'nav.catalog').
        Fallback order: current_language -> fr -> en -> default -> key
        Supports formatting variables: {name}, {count}, etc.
        """
        keys = key.split(".")

        # 1. Try current language
        val = self._lookup_key(self._translations.get(self._current_language, {}), keys)
        if val is not None:
            return self._format(str(val), kwargs)

        # 2. Try default language (French)
        if self._current_language != DEFAULT_LANGUAGE:
            val = self._lookup_key(self._translations.get(DEFAULT_LANGUAGE, {}), keys)
            if val is not None:
                return self._format(str(val), kwargs)

        # 3. Try English as secondary fallback
        if self._current_language != "en" and DEFAULT_LANGUAGE != "en":
            val = self._lookup_key(self._translations.get("en", {}), keys)
            if val is not None:
                return self._format(str(val), kwargs)

        # 4. Fallback to default arg or raw key
        fallback_str = default if default is not None else key
        return self._format(fallback_str, kwargs)

    def _lookup_key(self, root: dict, keys: list) -> Optional[Any]:
        curr = root
        for k in keys:
            if isinstance(curr, dict) and k in curr:
                curr = curr[k]
            else:
                return None
        return curr

    def _format(self, template: str, kwargs: dict) -> str:
        if not kwargs:
            return template
        try:
            return template.format(**kwargs)
        except Exception:
            return template


class I18nManager(_BaseI18nManager):
    @classmethod
    def instance(cls) -> "I18nManager":
        with cls._lock:
            if cls._instance is None:
                cls._instance = I18nManager()
            return cls._instance


def tr(key: str, default: Optional[str] = None, **kwargs) -> str:
    """Convenience helper for translation."""
    return I18nManager.instance().tr(key, default=default, **kwargs)
