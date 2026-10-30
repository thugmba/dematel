"""CSV 읽기, 인코딩 인식, 입력 검증.

오류·경고는 번역 키(issue.<code>)와 파라미터로 돌려주고, 문장은 UI에서 만든다.
"""

import csv
import io
import math
from dataclasses import dataclass, field

import numpy as np

ENCODINGS = ("utf-8-sig", "cp949")


@dataclass
class Issue:
    level: str  # "error" | "warning"
    code: str
    params: dict = field(default_factory=dict)


@dataclass
class ExpertMatrix:
    name: str
    factors: list[str]
    values: np.ndarray


@dataclass
class LoadResult:
    name: str
    matrix: ExpertMatrix | None
    issues: list[Issue]

    @property
    def ok(self) -> bool:
        return self.matrix is not None


def decode(raw: bytes) -> tuple[str, str] | None:
    for enc in ENCODINGS:
        try:
            return raw.decode(enc), enc
        except UnicodeDecodeError:
            continue
    return None


def _read_grid(text: str) -> list[list[str]]:
    """CSV를 문자열 격자로 읽고, Excel이 남기는 빈 끝 행·열을 제거한다."""
    first_line = text.split("\n", 1)[0]
    delimiter = ";" if first_line.count(";") > first_line.count(",") else ","
    rows = [[cell.strip() for cell in row] for row in csv.reader(io.StringIO(text), delimiter=delimiter)]
    while rows and not any(rows[-1]):
        rows.pop()
    if not rows:
        return []
    width = max(len(r) for r in rows)
    rows = [r + [""] * (width - len(r)) for r in rows]
    while width > 0 and not any(r[width - 1] for r in rows):
        width -= 1
    return [r[:width] for r in rows]


def load_matrix(name: str, raw: bytes, scale_max: float) -> LoadResult:
    issues: list[Issue] = []

    def fail(code: str, **params) -> LoadResult:
        issues.append(Issue("error", code, params))
        return LoadResult(name, None, issues)

    decoded = decode(raw)
    if decoded is None:
        return fail("decode_failed")
    grid = _read_grid(decoded[0])
    if not grid:
        return fail("empty_file")

    n_rows, n_cols = len(grid) - 1, len(grid[0]) - 1
    if n_rows != n_cols:
        return fail("not_square", rows=n_rows, cols=n_cols)
    n = n_rows
    if n < 2:
        return fail("too_small", n=n)

    col_names = grid[0][1:]
    row_names = [r[0] for r in grid[1:]]
    for pos, (r, c) in enumerate(zip(row_names, col_names), start=1):
        if not r or not c:
            issues.append(Issue("error", "empty_name", {"pos": pos}))
        elif r != c:
            issues.append(Issue("error", "name_mismatch", {"pos": pos, "row": r, "col": c}))
    duplicates = sorted({c for c in col_names if c and col_names.count(c) > 1})
    for d in duplicates:
        issues.append(Issue("error", "duplicate_name", {"name": d}))

    values = np.zeros((n, n))
    for i in range(n):
        for j in range(n):
            cell = grid[i + 1][j + 1]
            where = {"row": row_names[i] or i + 1, "col": col_names[j] or j + 1}
            if cell == "":
                issues.append(Issue("error", "empty_cell", where))
                continue
            try:
                v = float(cell)
            except ValueError:
                v = math.nan
            if not math.isfinite(v):
                issues.append(Issue("error", "not_numeric", {**where, "value": cell}))
                continue
            if i != j and not 0 <= v <= scale_max:
                issues.append(Issue("error", "out_of_range", {**where, "value": cell, "max": scale_max}))
                continue
            values[i, j] = v

    if any(issue.level == "error" for issue in issues):
        return LoadResult(name, None, issues)

    for i in range(n):
        if values[i, i] != 0:
            issues.append(Issue("warning", "diagonal_nonzero", {"factor": row_names[i], "value": f"{values[i, i]:g}"}))
            values[i, i] = 0
    off_diag = values[~np.eye(n, dtype=bool)]
    non_integer = int(np.count_nonzero(off_diag != np.round(off_diag)))
    if non_integer:
        issues.append(Issue("warning", "non_integer", {"count": non_integer}))

    return LoadResult(name, ExpertMatrix(name, col_names, values), issues)


def check_consistency(matrices: list[ExpertMatrix]) -> list[tuple[str, Issue]]:
    """모든 전문가 파일의 요인 수·요인명·순서가 첫 파일과 같은지 검사한다."""
    if not matrices:
        return []
    ref = matrices[0]
    return [
        (m.name, Issue("error", "factor_mismatch", {"ref": ref.name}))
        for m in matrices[1:]
        if m.factors != ref.factors
    ]
