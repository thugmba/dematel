import numpy as np
import pytest

from dematel import core, llm, threshold

FACTORS = ["Leadership", "Strategy", "F3 Tech", "Culture"]  # 숫자가 든 요인명도 허용돼야 한다


@pytest.fixture
def ctx():
    res = core.analyze([
        np.array([[0, 3, 2, 1], [1, 0, 4, 2], [2, 1, 0, 3], [0, 2, 1, 0]], dtype=float),
        np.array([[0, 4, 2, 1], [1, 0, 3, 2], [2, 1, 0, 3], [1, 2, 1, 0]], dtype=float),
    ])
    theta = threshold.compute(res.T, "mean")
    return llm.build_context(
        FACTORS, res, threshold.relations(res.T, theta), theta=theta, threshold_method="mean",
        n_experts=2, scale_max=4, gaps=core.consensus_gaps([res.A, res.A]), gap_limit=5, decimals=3,
    ), res, theta


def fake_llm(*answers):
    """정해진 답을 차례로 돌려주는 가짜 LLM. 받은 메시지를 calls에 기록한다."""
    calls = []

    def complete(messages):
        calls.append(messages)
        return answers[len(calls) - 1]

    return complete, calls


def test_load_config(monkeypatch):
    for key in ("LLM_API_KEY", "LLM_MODEL", "LLM_BASE_URL"):
        monkeypatch.delenv(key, raising=False)
    assert llm.load_config() is None
    monkeypatch.setenv("LLM_API_KEY", "k")
    monkeypatch.setenv("LLM_MODEL", "m")
    assert llm.load_config() == llm.LLMConfig("k", "m", llm.DEFAULT_BASE_URL)
    monkeypatch.setenv("LLM_BASE_URL", "https://example.org/v1")
    assert llm.load_config().base_url == "https://example.org/v1"


def test_placeholders_resolve_to_python_values(ctx):
    c, res, theta = ctx
    assert c.resolve("F1", None) == "Leadership"
    assert c.resolve("F3", None) == "F3 Tech"
    assert c.resolve("P", "F2") == f"{res.prominence[1]:,.3f}"
    assert c.resolve("D", "F4") == f"{res.relation[3]:,.3f}"
    assert c.resolve("t", "F1>F3") == f"{res.T[0, 2]:,.3f}"
    assert c.resolve("a", "F2 > F1") == f"{res.A[1, 0]:,.3f}"
    assert c.resolve("theta", None) == f"{theta:,.3f}"
    assert c.resolve("n_experts", None) == "2"
    assert c.resolve("gap_at", "2") == "0.00"
    assert c.resolve("experts_at", "2") == "2"
    assert c.resolve("scale_points", None) == "5"


@pytest.mark.parametrize("key, arg", [
    ("F9", None), ("F0", None), ("P", "F9"), ("t", "F1>F1"), ("t", "F1>F9"),
    ("unknown", None), ("P", None), ("gap_at", "7"),
])
def test_undefined_placeholders(ctx, key, arg):
    assert ctx[0].resolve(key, arg) is None


def test_render_substitutes_and_counts_only_numbers(ctx):
    c, res, _ = ctx
    text, numbers = llm.render("{F1} had the highest prominence ({P:F1}) among {n_factors} factors.", c)
    assert text == f"Leadership had the highest prominence ({res.prominence[0]:,.3f}) among 4 factors."
    assert numbers == 2


@pytest.mark.parametrize("text, expected", [
    ("{F1} scored {P:F1}.", []),
    ("{F1} scored 5.837.", ['digit written directly: "5.837"']),
    ("{F1} scored ５.", ["digit written directly"]),
    ("T = X(I − X)⁻¹", ["digit written directly"]),          # 위첨자 숫자
    ("with {experts_at:2} experts the gap was {gap_at:2}%.", []),
    ("F1 was first.", ["digit written directly"]),           # 요인 ID를 중괄호 없이 씀
    ("{F1} ranked {rank:F9}.", ["undefined placeholder"]),
    ("{F1} scored {P:F1.", ["malformed placeholder"]),
    ("   ", ["empty answer"]),
])
def test_violations(ctx, text, expected):
    found = llm.find_violations(text, ctx[0])
    assert bool(found) == bool(expected)
    for e in expected:
        assert any(e in f for f in found), (e, found)


def test_generate_passes_first_time(ctx):
    complete, calls = fake_llm("{F2} had a relation of {D:F2}.")
    g = llm.generate(complete, [{"role": "user", "content": "x"}], ctx[0])
    assert g.attempts == 1 and g.numbers == 1
    assert "{" not in g.text and "Strategy" in g.text
    assert len(calls) == 1


def test_generate_retries_with_feedback_then_passes(ctx):
    complete, calls = fake_llm("Leadership scored 5.8.", "{F1} scored {P:F1}.")
    g = llm.generate(complete, [{"role": "user", "content": "x"}], ctx[0])
    assert g.attempts == 2
    feedback = calls[1][-1]
    assert feedback["role"] == "user" and "digit written directly" in feedback["content"]
    assert calls[1][-2] == {"role": "assistant", "content": "Leadership scored 5.8."}


def test_generate_blocks_after_retries(ctx):
    complete, calls = fake_llm("It was 1.", "It was 2.", "It was 3.", "{F1}")
    with pytest.raises(llm.GenerationFailed) as e:
        llm.generate(complete, [{"role": "user", "content": "x"}], ctx[0])
    assert len(calls) == llm.MAX_RETRIES + 1
    assert e.value.violations


@pytest.mark.parametrize("kind", llm.KINDS)
@pytest.mark.parametrize("lang", ["en", "ko", "zh-TW"])
def test_messages(ctx, kind, lang):
    msgs = llm.build_messages(ctx[0], kind, lang, "  SME digital transformation ")
    user = msgs[1]["content"]
    assert msgs[0]["role"] == "system" and "must NOT write any digit" in msgs[0]["content"]
    assert llm.LANGUAGE_INSTRUCTIONS[lang] in user and llm.TERMINOLOGY[lang] in user
    assert "SME digital transformation" in user
    assert "{F1} = Leadership" in user and "{theta} =" in user


def test_facts_list_every_placeholder_they_mention(ctx):
    # 사실 목록에 등장하는 자리표시자는 모두 해석 가능해야 한다 (예시용 Fk·Fi>Fj 패턴 제외)
    c = ctx[0]
    for m in llm.PLACEHOLDER.finditer(c.facts):
        if m.group(2) in ("Fk", "Fi>Fj"):
            continue
        assert c.resolve(m.group(1), m.group(2)) is not None, m.group(0)


def test_with_request_id_makes_each_request_unique():
    base = [{"role": "user", "content": "x"}]
    a, b = llm.with_request_id(base), llm.with_request_id(base)
    assert a[:1] == base and b[:1] == base and a != b
    assert base == [{"role": "user", "content": "x"}]  # 원본은 바뀌지 않는다
