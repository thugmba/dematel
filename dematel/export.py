"""지표 테이블 구성과 CSV / Excel 내보내기."""

import io
import re
import zipfile
from collections.abc import Callable

import numpy as np
import pandas as pd

from .core import DematelResult

SHEET_NAME_MAX = 31
_INVALID_SHEET_CHARS = re.compile(r"[\[\]:*?/\\]")


def indicator_frame(factors: list[str], res: DematelResult, t: Callable[..., str]) -> pd.DataFrame:
    """요인별 지표 테이블 (머리글·구분값 번역, R+C 내림차순)."""
    rank = pd.Series(res.weight).rank(ascending=False, method="min").astype(int)
    df = pd.DataFrame({
        t("col.factor"): factors,
        t("col.R"): res.R,
        t("col.C"): res.C,
        t("col.prominence"): res.prominence,
        t("col.relation"): res.relation,
        t("col.weight"): res.weight,
        t("col.rank"): rank.to_numpy(),
        t("col.group"): [t(f"group.{g}") for g in res.group],
    })
    order = np.argsort(-res.prominence, kind="stable")
    return df.iloc[order].reset_index(drop=True)


def matrix_frame(matrix: np.ndarray, factors: list[str]) -> pd.DataFrame:
    return pd.DataFrame(matrix, index=factors, columns=factors)


def to_csv_bytes(df: pd.DataFrame, index: bool = True) -> bytes:
    # BOM을 붙여 Excel에서 한글·중국어가 깨지지 않게 한다.
    return df.to_csv(index=index).encode("utf-8-sig")


def to_zip_bytes(files: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in files.items():
            zf.writestr(name, data)
    return buf.getvalue()


def _sheet_names(names: list[str]) -> list[str]:
    result, used = [], set()
    for name in names:
        base = _INVALID_SHEET_CHARS.sub("_", name).strip("'") or "Sheet"
        base = base[:SHEET_NAME_MAX]
        candidate, k = base, 2
        while candidate.lower() in used:
            suffix = f" ({k})"
            candidate = base[: SHEET_NAME_MAX - len(suffix)] + suffix
            k += 1
        used.add(candidate.lower())
        result.append(candidate)
    return result


def to_excel_bytes(sheets: list[tuple[str, pd.DataFrame, bool]]) -> bytes:
    """(시트명, DataFrame, index 포함 여부) 목록을 시트별로 저장한 .xlsx 바이트."""
    buf = io.BytesIO()
    names = _sheet_names([name for name, _, _ in sheets])
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        for name, (_, df, index) in zip(names, sheets):
            df.to_excel(writer, sheet_name=name, index=index)
    return buf.getvalue()
