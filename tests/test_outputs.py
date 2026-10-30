import io
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from dematel import core, export, i18n, inrm, interpret, threshold

LOCALES = Path(__file__).resolve().parent.parent / "locales"


@pytest.fixture
def result():
    return core.analyze([np.array([[0, 3, 2, 1], [1, 0, 4, 2], [2, 1, 0, 3], [0, 2, 1, 0]], dtype=float)])


def test_locales_have_identical_keys():
    keys = {lang: set(json.loads((LOCALES / f"{lang}.json").read_text("utf-8"))) for lang in i18n.LANGS}
    assert keys["ko"] == keys["en"]
    assert keys["zh-TW"] == keys["en"]


@pytest.mark.parametrize(
    "query, locale, expected",
    [
        ("ko", "en-US", "ko"),
        (None, "ko-KR", "ko"),
        (None, "zh-Hant-TW", "zh-TW"),
        (None, "zh-CN", "zh-TW"),
        (None, "ja-JP", "en"),
        ("fr", None, "en"),
        (None, None, "en"),
    ],
)
def test_language_detection(query, locale, expected):
    assert i18n.detect(query, locale) == expected


@pytest.mark.parametrize("lang", list(i18n.LANGS))
def test_all_outputs_render_in_every_language(result, lang):
    t = i18n.translator(lang)
    factors = ["A", "B", "C", "D"]
    theta = threshold.compute(result.T, "mean")
    rels = threshold.relations(result.T, theta)

    lines = interpret.generate(factors, result, rels, theta, t)
    assert lines and all("{" not in line for line in lines)

    fig = inrm.build_figure(factors, result, rels, theta, t)
    arrows = [a for a in fig.layout.annotations if a.showarrow]
    pairs = {frozenset((i, j)) for i, j, _ in rels}
    assert len(arrows) == len(pairs)

    df = export.indicator_frame(factors, result, t)
    assert list(df[t("col.prominence")]) == sorted(result.prominence, reverse=True)

    data = export.to_excel_bytes([("expert", export.matrix_frame(result.A, factors), True), (t("sheet.indicators"), df, False)])
    assert pd.ExcelFile(io.BytesIO(data)).sheet_names == ["expert", t("sheet.indicators")]


def test_excel_sheet_names_are_sanitized_and_unique():
    df = pd.DataFrame({"x": [1]})
    data = export.to_excel_bytes([("a/b", df, False), ("a/b", df, False), ("x" * 40, df, False)])
    names = pd.ExcelFile(io.BytesIO(data)).sheet_names
    assert names[0] == "a_b" and names[1] == "a_b (2)" and len(names[2]) == 31


def test_csv_has_bom_for_excel():
    assert export.to_csv_bytes(pd.DataFrame({"요인": [1]})).startswith(b"\xef\xbb\xbf")


def test_zip_contains_files():
    import zipfile

    data = export.to_zip_bytes({"a.csv": b"1", "b.csv": b"2"})
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        assert zf.namelist() == ["a.csv", "b.csv"]
        assert zf.read("b.csv") == b"2"
