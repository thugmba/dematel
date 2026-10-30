"""INRM에 표시할 영향 관계를 고르는 임계값 θ."""

import numpy as np

METHODS = ("mean", "mean_std", "custom")


def compute(T: np.ndarray, method: str, custom: float | None = None) -> float:
    """θ를 계산한다. mean·mean_std는 T 전체 원소(대각 포함) 기준."""
    if method == "mean":
        return float(T.mean())
    if method == "mean_std":
        return float(T.mean() + T.std())
    if method == "custom":
        if custom is None:
            raise ValueError("custom threshold requires a value")
        return float(custom)
    raise ValueError(f"unknown method: {method}")


def off_diagonal_range(T: np.ndarray) -> tuple[float, float]:
    values = T[~np.eye(len(T), dtype=bool)]
    return float(values.min()), float(values.max())


def relations(T: np.ndarray, theta: float) -> list[tuple[int, int, float]]:
    """tᵢⱼ ≥ θ 인 (i, j, tᵢⱼ) 목록 (i ≠ j), tᵢⱼ 내림차순."""
    n = len(T)
    found = [
        (i, j, float(T[i, j]))
        for i in range(n)
        for j in range(n)
        if i != j and T[i, j] >= theta
    ]
    return sorted(found, key=lambda r: -r[2])
