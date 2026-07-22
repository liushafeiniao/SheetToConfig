"""Runtime translations and persisted locale selection for SheetToConfig."""

from __future__ import annotations

import json
import locale as _locale
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

from PyQt5.QtCore import QLocale

from sheet_to_config.app_paths import local_data_path


SUPPORTED_LOCALES = ("en", "zh-CN", "ja", "ko", "es", "zh-TW")
LANGUAGE_NAMES = {
    "en": "English",
    "zh-CN": "简体中文",
    "ja": "日本語",
    "ko": "한국어",
    "es": "Español",
    "zh-TW": "繁體中文",
}

if getattr(sys, "_MEIPASS", None):
    _PACKAGE_ROOT = Path(sys._MEIPASS) / "sheet_to_config"
else:
    _PACKAGE_ROOT = Path(__file__).resolve().parent.parent
_CATALOG_DIR = _PACKAGE_ROOT / "i18n" / "catalogs"
_settings_path = None
_catalogs: dict[str, dict[str, str]] = {}
_current_locale = "en"


def _normalize_system_locale(name: str) -> str:
    value = (name or "").replace("_", "-").lower()
    if value.startswith("zh-tw") or value.startswith("zh-hk") or value.startswith("zh-hant"):
        return "zh-TW"
    if value.startswith("zh"):
        return "zh-CN"
    for supported in ("ja", "ko", "es", "en"):
        if value.startswith(supported):
            return supported
    return "en"


def _system_locale() -> str:
    try:
        return _normalize_system_locale(QLocale.system().name())
    except Exception:
        try:
            return _normalize_system_locale(_locale.getdefaultlocale()[0] or "")
        except Exception:
            return "en"


def _load_catalogs() -> None:
    if _catalogs:
        return
    for locale_id in SUPPORTED_LOCALES:
        path = _CATALOG_DIR / f"{locale_id}.json"
        try:
            _catalogs[locale_id] = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            _catalogs[locale_id] = {}


def _read_settings() -> dict[str, Any]:
    global _settings_path
    if _settings_path is None:
        _settings_path = local_data_path("config.json")
    try:
        return json.loads(Path(_settings_path).read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {}


def _write_settings(data: dict[str, Any]) -> None:
    global _settings_path
    if _settings_path is None:
        _settings_path = local_data_path("config.json")
    target = Path(_settings_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=".sheet-to-config-", suffix=".json", dir=target.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, target)
    finally:
        if os.path.exists(temp_name):
            try:
                os.unlink(temp_name)
            except OSError:
                pass


def get_locale() -> str:
    """Return the persisted locale, initializing it from the system locale."""
    global _current_locale
    settings = _read_settings()
    selected = settings.get("locale")
    _current_locale = selected if selected in SUPPORTED_LOCALES else _system_locale()
    _load_catalogs()
    return _current_locale


def set_locale(locale_id: str) -> str:
    """Persist and activate a supported locale."""
    global _current_locale
    if locale_id not in SUPPORTED_LOCALES:
        raise ValueError(f"Unsupported locale: {locale_id}")
    settings = _read_settings()
    settings["locale"] = locale_id
    _write_settings(settings)
    _current_locale = locale_id
    _load_catalogs()
    return _current_locale


def tr(key: str, **params: Any) -> str:
    """Translate a key and format named parameters, falling back to English."""
    _load_catalogs()
    locale_id = _current_locale if _current_locale in SUPPORTED_LOCALES else get_locale()
    value = _catalogs.get(locale_id, {}).get(key)
    if value is None:
        value = _catalogs.get("en", {}).get(key, key)
    try:
        return value.format(**params)
    except (KeyError, ValueError):
        return value


def language_name(locale_id: str) -> str:
    return LANGUAGE_NAMES.get(locale_id, locale_id)


get_locale()

__all__ = [
    "LANGUAGE_NAMES",
    "SUPPORTED_LOCALES",
    "get_locale",
    "language_name",
    "set_locale",
    "tr",
]
