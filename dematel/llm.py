"""학교 제공 LLM(OpenAI 호환 API)으로 분석 결과를 논문용 문장으로 옮긴다.

수치는 모두 Python이 계산한다. LLM에는 숫자를 쓰지 못하게 하고 `{P:F1}` 같은 자리표시자만
쓰게 한 뒤, Python이 자리표시자를 계산값으로 바꾼다. 응답에 자리표시자 밖의 숫자나 정의되지 않은
자리표시자가 있으면 위반 내용을 알려 주고 다시 요청하며, 끝내 통과하지 못하면 결과를 버린다.

설정은 환경 변수(.env)에서 읽는다:
    LLM_API_KEY   (필수)
    LLM_MODEL     (필수)
    LLM_BASE_URL  (선택, 기본 https://api.ithu.tw/v1)
"""

import os
import re
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field

from .core import DematelResult

DEFAULT_BASE_URL = "https://api.ithu.tw/v1"
TIMEOUT_SECONDS = 120
MAX_RETRIES = 2
MAX_RELATIONS = 15

KINDS = ("results", "indicators", "inrm", "procedure")

PLACEHOLDER = re.compile(r"\{([A-Za-z_]+\d*)(?::([^{}]+))?\}")
# 아라비아·전각·위첨자·아래첨자 숫자를 모두 금지한다.
NUMBER = re.compile(r"[0-9０-９⁰¹²³⁴-⁹₀-₉]+(?:[.,][0-9０-９⁰¹²³⁴-⁹₀-₉]+)*")
FACTOR_ID = re.compile(r"F(\d+)")
PAIR = re.compile(r"F(\d+)>F(\d+)")

LANGUAGE_INSTRUCTIONS = {
    "en": "Write in formal academic English, past tense.",
    "ko": "한국어 학술 논문 문체(‘~하였다’, ‘~으로 나타났다’ 등 평서형 과거 시제)로 작성하라.",
    "zh-TW": "請以台灣學術論文常用的正體中文（繁體中文）撰寫，使用台灣用語，避免中國大陸用語。",
}

# 앱 화면·설명서와 같은 용어를 쓰도록 지정한다 (개발자 설명서의 용어 대응표).
TERMINOLOGY = {
    "en": "direct-relation matrix, normalized direct-relation matrix, total-relation matrix, prominence (R+C), "
          "relation (R−C), weight, cause group, effect group, threshold, consensus gap, "
          "Influential Network Relation Map (INRM)",
    "ko": "직접영향행렬, 정규화 직접영향행렬, 총영향행렬, 중심도(R+C), 원인도(R−C), 가중치, 원인군, 결과군, "
          "임계값, 합의도 Gap, 인과 네트워크 지도(INRM)",
    "zh-TW": "直接影響矩陣、正規化直接影響矩陣、總影響矩陣、中心度（R+C）、原因度（R−C）、權重、原因群、結果群、"
             "門檻值、共識差距、影響網絡關係圖（INRM）",
}

LABELS = {
    "en": {"table": "Table X.", "figure": "Figure X.", "note": "Note."},
    "ko": {"table": "표 X.", "figure": "그림 X.", "note": "주."},
    "zh-TW": {"table": "表X", "figure": "圖X", "note": "註："},
}

TASKS = {
    "results": (
        "Write the results section (3–5 paragraphs) in this order: (1) data and consensus check, "
        "(2) prominence (R+C) ranking, (3) cause and effect groups by relation (R−C), (4) INRM quadrants, "
        "(5) the strongest influence relations at or above the threshold. Refer to the indicator table as "
        "\"{table}\" and the INRM as \"{figure}\"."
    ),
    "indicators": (
        "Write text to accompany the indicator table. Line 1: a table caption starting with \"{table}\". "
        "Line 2: a table note starting with \"{note}\" that defines R, C, R+C, R−C, weight, rank (by weight) and group "
        "using the symbols R, C, R+C and R−C as written but no placeholders and no values. "
        "Then 1–2 paragraphs describing only what the table shows (highest and lowest values, rankings, groups); "
        "do not describe the data collection, normalization, consensus or threshold."
    ),
    "inrm": (
        "Write text to accompany the INRM figure. Line 1: a figure caption starting with \"{figure}\". "
        "Then 1–2 paragraphs describing the figure: the horizontal axis is prominence (R+C) and the vertical axis "
        "is relation (R−C); the dashed horizontal line is R−C equal to zero and the dotted vertical line is the "
        "mean prominence {p_mean}; which factors lie in which quadrant; arrows show relations at or above the "
        "threshold, with thicker arrows for stronger relations; and the most notable relations."
    ),
    "procedure": (
        "Write 1–2 paragraphs for the methods (analysis procedure) section describing how the DEMATEL analysis "
        "was carried out on these data: experts and rating scale, averaging the experts' matrices into the "
        "direct-relation matrix, normalization by the factor s, derivation of the total-relation matrix, the "
        "consensus gap check (including how it changed as experts were added), computation of R, C, prominence "
        "and relation, and how the threshold was set. Do not write equations."
    ),
}

SYSTEM_PROMPT = """You are an expert academic writer in management science and multi-criteria decision making.
You turn DEMATEL analysis results, computed by software, into sentences for a journal article.

STRICT NUMBER RULE — the most important rule:
- You must NOT write any digit (0–9) anywhere in your answer. Every number must be written as a placeholder
  exactly as listed in the data, e.g. {P:F1}, {theta}, {n_experts}, {t:F2>F3}. The software replaces them with
  the computed values. Write the unit or symbol yourself if needed, e.g. "{gap}%".
- Do not write numbers as words either ("three", "세", "三"); use the count placeholders instead.
- Write every factor name as its placeholder, e.g. {F1}. Never write factor names directly.
- Use only placeholders that appear in the data. Do not invent new placeholders.
- Values already include their sign; never put a minus sign in front of a placeholder.
- Name quadrants with Roman numerals (I, II, III, IV), and refer to tables and figures only as given in the task.

Other rules:
- Use only the facts given. Do not invent values, factors, statistics, comparisons, or citations.
- Write flowing prose. No bullet points, no headings, no Markdown tables, no equations.
- Do not add managerial implications or speculation; if the author gives a research context, you may use it
  only to name the topic."""


@dataclass(frozen=True)
class LLMConfig:
    api_key: str
    model: str
    base_url: str = DEFAULT_BASE_URL


def load_config() -> LLMConfig | None:
    """환경 변수에서 설정을 읽는다. 필수 값이 없으면 None (기능 비활성)."""
    api_key = os.environ.get("LLM_API_KEY", "").strip()
    model = os.environ.get("LLM_MODEL", "").strip()
    if not api_key or not model:
        return None
    base_url = os.environ.get("LLM_BASE_URL", "").strip() or DEFAULT_BASE_URL
    return LLMConfig(api_key, model, base_url)


# ---------------------------------------------------------------------- 자리표시자


@dataclass
class PaperContext:
    """자리표시자 → 계산값 사전과, LLM에게 보여 줄 사실 목록."""

    factors: list[str]
    scalars: dict[str, str]
    per_factor: dict[str, list[str]]  # key → 요인별 값 (요인 순서)
    pairs: dict[str, list[list[str]]]  # key → n×n 값
    facts: str = ""

    def resolve(self, key: str, arg: str | None) -> str | None:
        """자리표시자 하나를 값으로 바꾼다. 정의되지 않았으면 None."""
        n = len(self.factors)
        if arg is None:
            if m := FACTOR_ID.fullmatch(key):
                k = int(m.group(1)) - 1
                return self.factors[k] if 0 <= k < n else None
            return self.scalars.get(key)
        arg = arg.strip()
        if key in self.per_factor and (m := FACTOR_ID.fullmatch(arg)):
            k = int(m.group(1)) - 1
            return self.per_factor[key][k] if 0 <= k < n else None
        if key in self.pairs and (m := PAIR.fullmatch(arg.replace(" ", ""))):
            i, j = int(m.group(1)) - 1, int(m.group(2)) - 1
            if 0 <= i < n and 0 <= j < n and i != j:
                return self.pairs[key][i][j]
        if key in ("gap_at", "experts_at"):
            return self.scalars.get(f"{key}:{arg}")
        return None


def build_context(
    factors: list[str],
    res: DematelResult,
    rels: list[tuple[int, int, float]],
    *,
    theta: float,
    threshold_method: str,
    n_experts: int,
    scale_max: int,
    gaps: list[tuple[int, float | None]],
    gap_limit: float,
    decimals: int = 3,
) -> PaperContext:
    def num(v: float) -> str:
        return f"{v:,.{decimals}f}"

    n = len(factors)
    final_gap = gaps[-1][1] if gaps else None
    rank = {i: r for r, i in enumerate(sorted(range(n), key=lambda i: -res.weight[i]), start=1)}

    scalars = {
        "n_experts": str(n_experts),
        "n_factors": str(n),
        "scale_max": str(scale_max),
        "scale_points": str(scale_max + 1),
        "s": num(res.s),
        "theta": num(theta),
        "p_mean": num(float(res.prominence.mean())),
        "n_above": str(len(rels)),
        "n_pairs": str(n * (n - 1)),
        "n_cause": str(res.group.count("cause")),
        "n_effect": str(res.group.count("effect")),
        "gap_limit": f"{gap_limit:g}",
    }
    if final_gap is not None:
        scalars["gap"] = f"{final_gap:.2f}"
    for p, g in gaps:
        scalars[f"experts_at:{p}"] = str(p)
        if g is not None:
            scalars[f"gap_at:{p}"] = f"{g:.2f}"

    per_factor = {
        "R": [num(v) for v in res.R],
        "C": [num(v) for v in res.C],
        "P": [num(v) for v in res.prominence],
        "D": [num(v) for v in res.relation],
        "W": [num(v) for v in res.weight],
        "rank": [str(rank[i]) for i in range(n)],
    }
    pairs = {
        "t": [[num(v) for v in row] for row in res.T],
        "a": [[num(v) for v in row] for row in res.A],
    }
    ctx = PaperContext(factors, scalars, per_factor, pairs)
    ctx.facts = _facts_text(ctx, res, rels, threshold_method, final_gap, gap_limit, gaps)
    return ctx


def _facts_text(ctx, res, rels, threshold_method, final_gap, gap_limit, gaps) -> str:
    n = len(ctx.factors)
    fid = [f"F{k + 1}" for k in range(n)]
    method = {"mean": "mean of T", "mean_std": "mean + standard deviation of T", "custom": "set by the researcher"}
    quadrant = {1: "I (core cause)", 2: "II (independent cause)", 3: "III (independent effect)",
                4: "IV (core effect)", 0: "on the R−C = 0 axis"}
    s = ctx.scalars
    lines = ["FACTORS — write each name only as its placeholder:"]
    lines += [f"{{{fid[k]}}} = {ctx.factors[k]}" for k in range(n)]

    lines.append("\nGENERAL — placeholder = value:")
    lines += [
        f"{{n_experts}} = {s['n_experts']} (number of experts)",
        f"{{n_factors}} = {s['n_factors']} (number of factors)",
        f"{{scale_max}} = {s['scale_max']} and {{scale_points}} = {s['scale_points']}: "
        "the rating scale runs from zero to {scale_max}, i.e. a {scale_points}-point scale",
        f"{{s}} = {s['s']} (normalization factor)",
        f"{{theta}} = {s['theta']} (threshold; method: {method[threshold_method]})",
        f"{{n_above}} = {s['n_above']} relations are at or above the threshold, out of {{n_pairs}} = {s['n_pairs']}",
        f"{{p_mean}} = {s['p_mean']} (mean prominence)",
        f"{{n_cause}} = {s['n_cause']} factors in the cause group; {{n_effect}} = {s['n_effect']} in the effect group",
    ]
    if final_gap is None:
        lines.append("Consensus gap: not computed (only one expert).")
    else:
        verdict = "below" if final_gap < gap_limit else "above"
        lines.append(f"{{gap}} = {s['gap']} (consensus gap in %, {verdict} the criterion {{gap_limit}} = {s['gap_limit']} %)")
        steps = "; ".join(
            f"with {{experts_at:{p}}} = {p} experts the gap was {{gap_at:{p}}} = {g:.2f} %"
            for p, g in gaps if g is not None
        )
        lines.append(f"Consensus gap as experts were added in upload order: {steps}")

    lines.append(
        "\nPER FACTOR — placeholders {R:Fk} {C:Fk} {P:Fk} (prominence R+C) {D:Fk} (relation R−C) "
        "{W:Fk} (weight) {rank:Fk} (rank by weight). The weight is the length of the (R+C, R−C) vector, "
        "normalized so that all weights sum to one. Group: cause if R−C is positive, effect if negative. "
        "Rows sorted by prominence, descending:"
    )
    lines.append("factor | R | C | P | D | W | rank | group | INRM quadrant")
    for k in sorted(range(n), key=lambda k: -res.prominence[k]):
        v = [ctx.per_factor[key][k] for key in ("R", "C", "P", "D", "W", "rank")]
        lines.append(f"{fid[k]} | " + " | ".join(v) + f" | {res.group[k]} | {quadrant[res.quadrant[k]]}")

    lines.append(
        f"\nRELATIONS at or above the threshold (up to {MAX_RELATIONS}, strongest first). "
        "Placeholder {t:Fi>Fj} = total influence of Fi on Fj; {a:Fi>Fj} = average direct influence:"
    )
    lines += [f"{fid[i]} > {fid[j]}: {{t:{fid[i]}>{fid[j]}}} = {ctx.pairs['t'][i][j]}" for i, j, _ in rels[:MAX_RELATIONS]] or ["(none)"]
    return "\n".join(lines)


def find_violations(text: str, ctx: PaperContext) -> list[str]:
    """규칙 위반 목록. 빈 목록이면 통과."""
    if not text.strip():
        return ["empty answer"]
    problems = []
    for m in PLACEHOLDER.finditer(text):
        if ctx.resolve(m.group(1), m.group(2)) is None:
            problems.append(f"undefined placeholder {m.group(0)}")
    rest = PLACEHOLDER.sub(" ", text)
    for m in NUMBER.finditer(rest):
        snippet = rest[max(0, m.start() - 15): m.end() + 15].replace("\n", " ")
        problems.append(f"digit written directly: \"{m.group(0)}\" in …{snippet.strip()}…")
    if "{" in rest or "}" in rest:
        problems.append("malformed placeholder (unmatched brace)")
    return problems


def render(text: str, ctx: PaperContext) -> tuple[str, int]:
    """자리표시자를 값으로 바꾼다. (결과 문장, 바꾼 수치 개수 — 요인명 제외)"""
    count = 0

    def sub(m: re.Match) -> str:
        nonlocal count
        if not FACTOR_ID.fullmatch(m.group(1)) or m.group(2) is not None:
            count += 1
        return ctx.resolve(m.group(1), m.group(2))

    return PLACEHOLDER.sub(sub, text), count


# ---------------------------------------------------------------------- 생성


def build_messages(ctx: PaperContext, kind: str, lang: str, context: str = "") -> list[dict[str, str]]:
    task = TASKS[kind].format(**LABELS[lang], p_mean="({p_mean})")
    user = [LANGUAGE_INSTRUCTIONS[lang], f"Use these exact terms: {TERMINOLOGY[lang]}.", f"Task: {task}"]
    if context.strip():
        user.append(f"Research topic given by the author (use only to name the topic): {context.strip()}")
    user.append("DATA:\n" + ctx.facts)
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "\n\n".join(user)},
    ]


def with_request_id(messages: list[dict[str, str]]) -> list[dict[str, str]]:
    """같은 요청을 학교 서버가 캐시해 같은 답을 돌려주므로, 다시 생성할 때는 요청마다 고유 ID를 붙인다."""
    return messages + [{"role": "user", "content": f"(Request {uuid.uuid4().hex}: write a new draft with different wording.)"}]


class GenerationFailed(Exception):
    def __init__(self, violations: list[str]):
        super().__init__("; ".join(violations))
        self.violations = violations


@dataclass
class Generation:
    text: str            # 자리표시자를 계산값으로 바꾼 최종 문장
    numbers: int         # Python 계산값으로 채운 수치 개수
    attempts: int        # LLM 호출 횟수
    raw: str = field(repr=False, default="")


def generate(
    complete: Callable[[list[dict[str, str]]], str],
    messages: list[dict[str, str]],
    ctx: PaperContext,
    max_retries: int = MAX_RETRIES,
) -> Generation:
    """LLM을 호출하고 검증한다. 위반이 있으면 알려 주고 다시 요청하며, 끝내 실패하면 GenerationFailed."""
    history = list(messages)
    violations: list[str] = []
    for attempt in range(1, max_retries + 2):
        raw = complete(history)
        violations = find_violations(raw, ctx)
        if not violations:
            text, numbers = render(raw, ctx)
            return Generation(text, numbers, attempt, raw)
        history += [
            {"role": "assistant", "content": raw},
            {"role": "user", "content": (
                "Your answer broke the rules:\n- " + "\n- ".join(violations[:20])
                + "\nRewrite the whole answer. Write no digits at all; use only the placeholders from the data."
            )},
        ]
    raise GenerationFailed(violations)


def openai_completer(config: LLMConfig) -> Callable[[list[dict[str, str]]], str]:
    from openai import OpenAI  # 기능을 쓰지 않는 환경에서도 앱이 뜨도록 지연 import

    client = OpenAI(api_key=config.api_key, base_url=config.base_url, timeout=TIMEOUT_SECONDS)

    def complete(messages: list[dict[str, str]]) -> str:
        response = client.chat.completions.create(model=config.model, messages=messages, temperature=0.3)
        return response.choices[0].message.content or ""

    return complete
