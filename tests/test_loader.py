import numpy as np

from dematel import loader

VALID = ",A,B,C\nA,0,3,2\nB,1,0,4\nC,2,1,0\n"


def load(text: str, encoding: str = "utf-8", scale_max: float = 4) -> loader.LoadResult:
    return loader.load_matrix("expert.csv", text.encode(encoding), scale_max)


def codes(result: loader.LoadResult, level: str = "error") -> list[str]:
    return [i.code for i in result.issues if i.level == level]


def test_valid_matrix():
    r = load(VALID)
    assert r.ok and not r.issues
    assert r.matrix.factors == ["A", "B", "C"]
    np.testing.assert_array_equal(r.matrix.values, [[0, 3, 2], [1, 0, 4], [2, 1, 0]])


def test_korean_names_in_utf8_bom_and_cp949():
    text = ",환경,기술\n환경,0,3\n기술,1,0\n"
    for enc in ("utf-8-sig", "cp949"):
        r = load(text, enc)
        assert r.ok, enc
        assert r.matrix.factors == ["환경", "기술"]


def test_semicolon_delimiter_and_trailing_blank_cells():
    r = load(";A;B;\nA;0;3;\nB;1;0;\n;;;\n")
    assert r.ok
    assert r.matrix.factors == ["A", "B"]


def test_not_square():
    assert codes(load(",A,B,C\nA,0,1,2\nB,1,0,2\n")) == ["not_square"]


def test_too_small():
    assert codes(load(",A\nA,0\n")) == ["too_small"]


def test_name_mismatch_and_duplicate():
    assert "name_mismatch" in codes(load(",A,B\nA,0,1\nX,1,0\n"))
    assert "duplicate_name" in codes(load(",A,A\nA,0,1\nA,1,0\n"))


def test_empty_and_non_numeric_cells():
    r = load(",A,B\nA,0,\nB,x,0\n")
    assert codes(r) == ["empty_cell", "not_numeric"]
    assert r.issues[1].params == {"row": "B", "col": "A", "value": "x"}


def test_out_of_range_uses_scale_max():
    assert codes(load(",A,B\nA,0,5\nB,1,0\n")) == ["out_of_range"]
    assert load(",A,B\nA,0,5\nB,1,0\n", scale_max=5).ok
    assert codes(load(",A,B\nA,0,-1\nB,1,0\n")) == ["out_of_range"]


def test_diagonal_nonzero_is_warning_and_replaced():
    r = load(",A,B\nA,2,1\nB,1,0\n")
    assert r.ok
    assert codes(r, "warning") == ["diagonal_nonzero"]
    assert r.matrix.values[0, 0] == 0


def test_non_integer_is_warning():
    r = load(",A,B\nA,0,1.5\nB,2.5,0\n")
    assert r.ok
    assert r.issues[0].code == "non_integer" and r.issues[0].params == {"count": 2}


def test_undecodable_file():
    r = loader.load_matrix("bad.csv", b"\xff\xfe\x00\x81\x00", 4)
    assert codes(r) == ["decode_failed"]


def test_consistency_across_experts():
    a = load(VALID).matrix
    b = loader.load_matrix("other.csv", ",A,C,B\nA,0,3,2\nC,1,0,4\nB,2,1,0\n".encode(), 4).matrix
    found = loader.check_consistency([a, b])
    assert [(name, i.code) for name, i in found] == [("other.csv", "factor_mismatch")]
    assert loader.check_consistency([a, a]) == []
