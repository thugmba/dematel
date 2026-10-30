"""언어 감지와 번역 함수 t(key, **params)."""

import json
from collections.abc import Callable
from functools import cache
from pathlib import Path

LOCALES_DIR = Path(__file__).resolve().parent.parent / "locales"
LANGS = {"en": "English", "zh-TW": "繁體中文", "ko": "한국어"}
DEFAULT = "en"


def normalize(code: str | None) -> str | None:
    """'ko-KR', 'zh-Hant-TW', 'zh_TW' 같은 값을 지원 언어 코드로 바꾼다. 미지원이면 None."""
    if not code:
        return None
    code = code.replace("_", "-").lower()
    if code in ("zh-tw", "zh") or code.startswith("zh-"):
        return "zh-TW"
    base = code.split("-")[0]
    return base if base in LANGS else None


def detect(query_lang: str | None, browser_locale: str | None) -> str:
    """URL 파라미터 → 브라우저 언어 → 기본값(English) 순서로 결정한다."""
    if query_lang in LANGS:
        return query_lang
    return normalize(query_lang) or normalize(browser_locale) or DEFAULT


@cache
def _load(lang: str) -> dict[str, str]:
    return json.loads((LOCALES_DIR / f"{lang}.json").read_text(encoding="utf-8"))


def translator(lang: str) -> Callable[..., str]:
    strings = _load(lang)
    fallback = _load(DEFAULT)

    def t(key: str, **params) -> str:
        text = strings.get(key) or fallback.get(key) or key
        return text.format(**params) if params else text

    return t
