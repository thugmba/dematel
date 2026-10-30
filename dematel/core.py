"""DEMATEL 핵심 계산: 평균 A, 합의도 Gap, 정규화 X, 총영향 T, 지표."""

from dataclasses import dataclass

import numpy as np

TOL = 1e-12
MAX_CONDITION = 1e12


class DematelError(Exception):
    """분석을 진행할 수 없는 입력. `code`는 번역 키(error.<code>)로 사용한다."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class DematelResult:
    A: np.ndarray           # 평균 직접영향행렬
    X: np.ndarray           # 정규화 직접영향행렬
    T: np.ndarray           # 총영향행렬
    s: float                # 정규화 계수
    R: np.ndarray           # 행 합 (주는 영향)
    C: np.ndarray           # 열 합 (받는 영향)
    prominence: np.ndarray  # R+C
    relation: np.ndarray    # R−C
    weight: np.ndarray      # 정규화 가중치
    group: tuple[str, ...]  # "cause" | "effect" | "neutral"
    quadrant: tuple[int, ...]  # 1~4, R−C = 0이면 0


def average(matrices: list[np.ndarray]) -> np.ndarray:
    return np.mean(np.stack(matrices), axis=0)


def consensus_gaps(matrices: list[np.ndarray]) -> list[tuple[int, float | None]]:
    """전문가 수를 p−1 → p로 늘릴 때의 평균 격차 비율(%)을 p = 2..H에 대해 계산한다.

    p명 평균이 0인 셀과 대각 원소는 제외하며, 계산할 셀이 없으면 None.
    """
    gaps = []
    off_diag = ~np.eye(len(matrices[0]), dtype=bool)
    for p in range(2, len(matrices) + 1):
        cur = average(matrices[:p])
        prev = average(matrices[: p - 1])
        mask = off_diag & (cur != 0)
        if not mask.any():
            gaps.append((p, None))
            continue
        gap = np.abs(cur[mask] - prev[mask]) / cur[mask]
        gaps.append((p, float(gap.mean() * 100)))
    return gaps


def normalize(A: np.ndarray) -> tuple[np.ndarray, float]:
    s = float(max(A.sum(axis=1).max(), A.sum(axis=0).max()))
    if s <= 0:
        raise DematelError("all_zero")
    return A / s, s


def total_relation(X: np.ndarray) -> np.ndarray:
    """T = X(I − X)⁻¹ 을 역행렬 없이 T(I − X) = X 를 풀어 계산한다."""
    M = np.eye(len(X)) - X
    if np.linalg.cond(M) > MAX_CONDITION:
        raise DematelError("singular")
    try:
        T = np.linalg.solve(M.T, X.T).T
    except np.linalg.LinAlgError:
        raise DematelError("singular") from None
    if not np.all(np.isfinite(T)):
        raise DematelError("singular")
    return T


def analyze(matrices: list[np.ndarray]) -> DematelResult:
    A = average(matrices)
    X, s = normalize(A)
    T = total_relation(X)

    R = T.sum(axis=1)
    C = T.sum(axis=0)
    prominence = R + C
    relation = R - C
    raw_weight = np.sqrt(prominence**2 + relation**2)
    weight = raw_weight / raw_weight.sum()

    group = tuple(
        "cause" if r > TOL else "effect" if r < -TOL else "neutral" for r in relation
    )
    high = prominence >= prominence.mean()
    quadrant = tuple(
        (1 if h else 2) if r > TOL else (4 if h else 3) if r < -TOL else 0
        for h, r in zip(high, relation)
    )
    return DematelResult(A, X, T, s, R, C, prominence, relation, weight, group, quadrant)
