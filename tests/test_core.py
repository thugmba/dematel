import numpy as np
import pytest

from dematel import core, threshold


def test_two_factor_example_matches_hand_calculation():
    # A = [[0,2],[1,0]] → s = 2, X = [[0,1],[.5,0]], (I−X)⁻¹ = [[2,2],[1,2]], T = [[1,2],[1,1]]
    res = core.analyze([np.array([[0.0, 2.0], [1.0, 0.0]])])
    assert res.s == 2
    np.testing.assert_allclose(res.T, [[1, 2], [1, 1]])
    np.testing.assert_allclose(res.R, [3, 2])
    np.testing.assert_allclose(res.C, [2, 3])
    np.testing.assert_allclose(res.prominence, [5, 5])
    np.testing.assert_allclose(res.relation, [1, -1])
    assert res.group == ("cause", "effect")
    assert res.quadrant == (1, 4)


def test_total_relation_equals_neumann_series():
    rng = np.random.default_rng(0)
    A = rng.integers(0, 5, size=(6, 6)).astype(float)
    np.fill_diagonal(A, 0)
    X, _ = core.normalize(A)
    series = sum(np.linalg.matrix_power(X, k) for k in range(1, 400))
    np.testing.assert_allclose(core.total_relation(X), series, atol=1e-9)


def test_average_of_experts():
    a = np.array([[0.0, 4.0], [2.0, 0.0]])
    b = np.array([[0.0, 2.0], [0.0, 0.0]])
    np.testing.assert_allclose(core.average([a, b]), [[0, 3], [1, 0]])


def test_normalization_uses_max_of_row_and_column_sums():
    A = np.array([[0.0, 1.0, 1.0], [3.0, 0.0, 0.0], [3.0, 0.0, 0.0]])
    # 최대 행 합 3, 최대 열 합 6 → s = 6
    _, s = core.normalize(A)
    assert s == 6


def test_weights_sum_to_one_and_are_positive():
    res = core.analyze([np.array([[0, 3, 2], [1, 0, 4], [2, 1, 0]], dtype=float)])
    assert res.weight.sum() == pytest.approx(1)
    assert (res.weight > 0).all()


def test_all_zero_raises():
    with pytest.raises(core.DematelError) as e:
        core.analyze([np.zeros((3, 3))])
    assert e.value.code == "all_zero"


def test_singular_raises():
    # 모든 행·열 합이 같으면 X의 고유값 1 → (I − X) 특이
    with pytest.raises(core.DematelError) as e:
        core.analyze([np.array([[0.0, 1.0], [1.0, 0.0]])])
    assert e.value.code == "singular"


def test_consensus_gap():
    a = np.array([[0.0, 2.0], [2.0, 0.0]])
    b = np.array([[0.0, 4.0], [2.0, 0.0]])
    gaps = core.consensus_gaps([a, a, b])
    assert gaps[0] == (2, 0.0)
    # p=3 평균 [[0, 8/3],[2,0]], p=2 평균 [[0,2],[2,0]] → (|8/3−2|/(8/3) + 0)/2 = 12.5%
    assert gaps[1][0] == 3
    assert gaps[1][1] == pytest.approx(12.5)


def test_consensus_gap_single_expert_is_empty():
    assert core.consensus_gaps([np.ones((2, 2))]) == []


def test_threshold_methods_and_relations():
    T = np.array([[0.1, 0.5], [0.3, 0.1]])
    assert threshold.compute(T, "mean") == pytest.approx(0.25)
    assert threshold.compute(T, "mean_std") == pytest.approx(0.25 + T.std())
    assert threshold.compute(T, "custom", 0.4) == 0.4
    assert threshold.relations(T, 0.25) == [(0, 1, 0.5), (1, 0, 0.3)]
    assert threshold.relations(T, 0.05) == [(0, 1, 0.5), (1, 0, 0.3)]  # 대각 제외
