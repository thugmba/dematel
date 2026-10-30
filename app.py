"""DEMATEL 분석 시스템 — Streamlit 진입점 (화면 구성만 담당)."""

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from dematel import core, export, i18n, inrm, interpret, llm, loader, threshold

load_dotenv(Path(__file__).resolve().parent / ".env")
LLM_CONFIG = llm.load_config()


@st.cache_resource(show_spinner=False)
def _llm_completer(config: llm.LLMConfig):
    return llm.openai_completer(config)

SAMPLES_DIR = Path(__file__).resolve().parent / "samples"
MAX_ISSUES_SHOWN = 30
HIGHLIGHT = "background-color: rgba(255, 193, 7, 0.35)"
EXAMPLE_FACTORS = ["F1", "F2", "F3", "F4"]
EXAMPLE_MATRIX = np.array([[0, 3, 2, 1], [1, 0, 4, 2], [2, 1, 0, 3], [0, 2, 1, 0]])

st.set_page_config(page_title="DEMATEL", page_icon="🔗", layout="wide")

ss = st.session_state
ss.setdefault("files", {})  # 파일명 → bytes. 업로드 위젯이 초기화돼도 데이터는 유지된다.
ss.setdefault("uploader_key", 0)
if "lang" not in ss:
    ss.lang = i18n.detect(st.query_params.get("lang"), getattr(st.context, "locale", None))


def _sample_files() -> dict[str, bytes]:
    return {p.name: p.read_bytes() for p in sorted(SAMPLES_DIR.glob("*.csv"))}


def _on_upload(key: str) -> None:
    ss.files = {f.name: f.getvalue() for f in ss.get(key) or []}
    ss.using_sample = False


def _load_samples() -> None:
    ss.files = _sample_files()
    ss.using_sample = True
    ss.uploader_key += 1


def _clear_files() -> None:
    ss.files = {}
    ss.using_sample = False
    ss.uploader_key += 1


@st.cache_data(show_spinner=False)
def _analyze(values: tuple[np.ndarray, ...]) -> core.DematelResult:
    return core.analyze(list(values))


# ------------------------------------------------------------------ 머리글 · 언어
head, lang_col = st.columns([5, 1], vertical_alignment="center")
with lang_col:
    st.selectbox(
        "Language", list(i18n.LANGS), format_func=i18n.LANGS.get,
        key="lang", label_visibility="collapsed",
    )
st.query_params["lang"] = ss.lang
t = i18n.translator(ss.lang)

with head:
    st.title(t("app.title"))
    st.caption(t("app.subtitle"))

# ------------------------------------------------------------------ 사이드바 · 설정
with st.sidebar:
    st.header(t("settings.header"))
    scale_max = st.number_input(
        t("settings.scale_max"), min_value=1, max_value=10, value=4, step=1,
        key="scale_max", help=t("settings.scale_max_help"),
    )
    decimals = st.number_input(
        t("settings.decimals"), min_value=0, max_value=6, value=3, step=1,
        key="decimals", help=t("settings.decimals_help"),
    )
    gap_limit = st.number_input(
        t("settings.gap_limit"), min_value=0.5, max_value=50.0, value=5.0, step=0.5,
        key="gap_limit", help=t("settings.gap_limit_help"),
    )
    anonymize = st.toggle(t("settings.anonymize"), key="anonymize", help=t("settings.anonymize_help"))
    # 임계값 설정은 데이터가 있어야 그릴 수 있으므로 자리만 먼저 잡아 두고, 안내는 항상 맨 아래에 둔다.
    threshold_box = st.container()
    ai_box = st.container()
    st.divider()
    with st.expander(t("settings.guide_title")):
        st.markdown(t("settings.guide"))


def num(v: float) -> str:
    return f"{v:,.{decimals}f}"


# ------------------------------------------------------------------ 1. 데이터 입력
st.subheader(t("input.header"))
uploader_key = f"uploader_{ss.uploader_key}"
st.file_uploader(
    t("input.uploader"), type="csv", accept_multiple_files=True,
    key=uploader_key, on_change=_on_upload, args=(uploader_key,), help=t("input.uploader_help"),
)
b1, b2, b3, b4 = st.columns(4)
b1.button(
    t("input.load_sample"), on_click=_load_samples, width="stretch",
    type="secondary" if ss.files else "primary",
)
b2.download_button(
    t("input.download_template"), (SAMPLES_DIR / "expert_01.csv").read_bytes(),
    file_name="dematel_template.csv", mime="text/csv", width="stretch",
)
b3.download_button(
    t("input.download_samples"), export.to_zip_bytes(_sample_files()),
    file_name="dematel_samples.zip", mime="application/zip", width="stretch",
)
b4.button(t("input.clear"), on_click=_clear_files, disabled=not ss.files, width="stretch")

with st.expander(t("input.guide_title"), expanded=not ss.files):
    guide, example = st.columns([3, 2])
    guide.markdown(t("input.guide", max=scale_max))
    example_df = export.matrix_frame(EXAMPLE_MATRIX, EXAMPLE_FACTORS).astype(int)
    example.dataframe(
        example_df.style.apply(
            lambda df: pd.DataFrame(
                [[HIGHLIGHT if (r, c) == ("F2", "F3") else "" for c in df.columns] for r in df.index],
                index=df.index, columns=df.columns,
            ),
            axis=None,
        ),
        width="stretch",
    )
    example.caption(t("input.example_caption"))

if not ss.files:
    st.info(t("input.empty"))
    st.stop()

if ss.get("using_sample"):
    st.info(t("input.sample_active"))
st.caption(t("input.loaded", count=len(ss.files), names=t("list_sep").join(ss.files)))

# ------------------------------------------------------------------ 2. 검증
results = [loader.load_matrix(name, raw, scale_max) for name, raw in ss.files.items()]
issues = [(r.name, i) for r in results for i in r.issues]
issues += loader.check_consistency([r.matrix for r in results if r.ok])


def _issue_lines(level: str) -> list[str]:
    found = [f"- **{name}** — {t(f'issue.{i.code}', **i.params)}" for name, i in issues if i.level == level]
    if len(found) > MAX_ISSUES_SHOWN:
        found = found[:MAX_ISSUES_SHOWN] + [f"- {t('validate.more', count=len(found) - MAX_ISSUES_SHOWN)}"]
    return found


errors, warnings = _issue_lines("error"), _issue_lines("warning")
if errors:
    st.error(t("validate.has_errors") + "\n\n" + "\n".join(errors))
    st.stop()
if warnings:
    st.warning(t("validate.has_warnings") + "\n\n" + "\n".join(warnings))

# ------------------------------------------------------------------ 3. 분석
matrices = [r.matrix for r in results]
factors = matrices[0].factors
n, H = len(factors), len(matrices)
expert_names = [t("expert_n", n=k + 1) if anonymize else Path(m.name).stem for k, m in enumerate(matrices)]

try:
    res = _analyze(tuple(m.values for m in matrices))
except core.DematelError as e:
    st.error(t(f"error.{e.code}"))
    st.stop()

gaps = core.consensus_gaps([m.values for m in matrices])
final_gap = gaps[-1][1] if gaps else None

with threshold_box:
    st.header(t("threshold.header"))
    method = st.radio(
        t("threshold.method"), threshold.METHODS,
        format_func=lambda m: t(f"threshold.{m}"), key="th_method", help=t("threshold.method_help"),
    )
    custom = None
    if method == "custom":
        lo, hi = threshold.off_diagonal_range(res.T)
        hi = max(hi, lo + 1e-3)
        if not lo <= ss.get("th_custom", lo) <= hi:
            del ss["th_custom"]  # 데이터가 바뀌어 이전 값이 범위를 벗어난 경우
        custom = st.slider(
            t("threshold.value"), min_value=lo, max_value=hi,
            value=min(max(threshold.compute(res.T, "mean"), lo), hi),
            step=(hi - lo) / 200, format=f"%.{decimals}f", key="th_custom", help=t("threshold.value_help"),
        )
    theta = threshold.compute(res.T, method, custom)
    rels = threshold.relations(res.T, theta)
    st.metric(t("threshold.theta"), num(theta), help=t("threshold.theta_help"))
    st.caption(t("threshold.count", count=len(rels), total=n * (n - 1)))

st.divider()
st.subheader(t("results.header"))
m1, m2, m3, m4 = st.columns(4)
m1.metric(t("summary.experts"), H)
m2.metric(t("summary.factors"), n)
m3.metric(t("summary.s"), num(res.s), help=t("summary.s_help"))
if final_gap is None:
    m4.metric(t("summary.gap"), "—", help=t("summary.gap_help") + "\n\n" + t("summary.gap_na"))
else:
    ok = final_gap < gap_limit
    m4.metric(
        t("summary.gap"), f"{final_gap:.2f}%",
        delta=t("gap.ok") if ok else t("gap.ng"), delta_color="normal" if ok else "off",
        delta_arrow="off", help=t("summary.gap_help"),
    )

# ------------------------------------------------------------------ 논문용 문장 (AI)
if LLM_CONFIG is not None:
    with ai_box:
        st.header(t("ai.sidebar_header"))
        st.caption(t("ai.beta_free"))
        # 작성 언어는 화면 언어를 따르되, 사용자가 바꿀 수 있다. 화면 언어를 바꾸면 다시 화면 언어로 맞춘다.
        if ss.get("ai_lang_ui") != ss.lang:
            ss.ai_lang = ss.lang
            ss.ai_lang_ui = ss.lang
        paper_lang = st.selectbox(
            t("ai.language"), list(i18n.LANGS), format_func=i18n.LANGS.get,
            key="ai_lang", help=t("ai.language_help"),
        )
        paper_topic = st.text_input(
            t("ai.context"), placeholder=t("ai.context_placeholder"),
            key="ai_context", help=t("ai.context_help"),
        )
    paper_ctx = llm.build_context(
        factors, res, rels, theta=theta, threshold_method=method, n_experts=H,
        scale_max=scale_max, gaps=gaps, gap_limit=gap_limit, decimals=decimals,
    )
ss.setdefault("ai_results", {})


def ai_section(kind: str) -> None:
    """탭 아래쪽의 논문용 문장 영역. LLM은 자리표시자만 쓰고 수치는 Python 계산값으로 채운다."""
    st.divider()
    st.markdown(f"#### {t(f'ai.header.{kind}')}")
    if LLM_CONFIG is None:
        st.info(t("ai.not_configured"))
        return
    st.caption(t(f"ai.description.{kind}"))
    messages = llm.build_messages(paper_ctx, kind, paper_lang, paper_topic)
    # 같은 입력으로 다시 요청하지 않도록 결과를 세션에 보관한다 (언어 전환·탭 이동 시에도 유지).
    request_key = hashlib.sha256(
        json.dumps([LLM_CONFIG.model, messages], ensure_ascii=False).encode()
    ).hexdigest()
    result: llm.Generation | None = ss.ai_results.get(request_key)

    clicked = st.button(
        t("ai.regenerate") if result else t("ai.generate"),
        type="secondary" if result else "primary", key=f"ai_generate_{kind}",
    )
    st.caption(t("ai.privacy", model=LLM_CONFIG.model) + " " + t("ai.beta_free"))
    if clicked:
        try:
            with st.spinner(t("ai.generating")):
                send = llm.with_request_id(messages) if result else messages  # 다시 생성: 서버 캐시 우회
                result = llm.generate(_llm_completer(LLM_CONFIG), send, paper_ctx)
        except llm.GenerationFailed as e:
            st.error(t("ai.blocked", attempts=llm.MAX_RETRIES + 1))
            with st.expander(t("ai.blocked_detail")):
                st.code("\n".join(e.violations), language=None, wrap_lines=True)
            return
        except Exception as e:  # 네트워크·인증·모델 오류를 모두 사용자 메시지로 보여 준다
            st.error(t("ai.error", detail=f"{type(e).__name__}: {str(e)[:300]}"))
            return
        ss.ai_results[request_key] = result
        st.rerun()  # 버튼 문구(다시 생성)와 복사·다운로드 영역을 갱신

    if result:
        st.markdown(result.text)
        st.success(t("ai.verified", numbers=result.numbers, attempts=result.attempts))
        st.caption(t("ai.review_notice"))
        with st.expander(t("ai.copy")):
            st.code(result.text, language=None, wrap_lines=True)
        st.download_button(
            t("ai.download"), result.text.encode("utf-8"),
            file_name=f"dematel_{kind}_{paper_lang}.txt", mime="text/plain", key=f"ai_download_{kind}",
        )


# ------------------------------------------------------------------ 4. 결과
tab_ind, tab_map, tab_int, tab_mat, tab_exp = st.tabs([
    t("tab.indicators"), t("tab.map"), t("tab.interpret"), t("tab.matrices"), t("tab.export"),
])

indicators = export.indicator_frame(factors, res, t)
number_cols = [t("col.R"), t("col.C"), t("col.prominence"), t("col.relation"), t("col.weight")]

with tab_ind:
    st.dataframe(
        indicators.style.format({c: num for c in number_cols}),
        hide_index=True, width="stretch",
    )
    st.caption(t("ind.caption"))
    ai_section("indicators")

with tab_map:
    fig = inrm.build_figure(factors, res, rels, theta, t, decimals)
    image_format = st.radio(t("map.image_format"), ["png", "svg"], horizontal=True, key="img_format")
    st.plotly_chart(
        fig, width="stretch",
        config={
            "displaylogo": False,
            "toImageButtonOptions": {"format": image_format, "filename": "inrm", "scale": 2},
        },
    )
    st.caption(t("map.hint"))
    st.dataframe(
        pd.DataFrame({
            t("quad.col_quadrant"): [t(f"quad.roman{q}") for q in (1, 2, 3, 4)],
            t("quad.col_position"): [t(f"quad.pos{q}") for q in (1, 2, 3, 4)],
            t("quad.col_meaning"): [t(f"quad.meaning{q}") for q in (1, 2, 3, 4)],
            t("quad.col_factors"): [
                t("list_sep").join(f for f, fq in zip(factors, res.quadrant) if fq == q) or "—"
                for q in (1, 2, 3, 4)
            ],
        }),
        hide_index=True, width="stretch",
    )
    ai_section("inrm")

with tab_int:
    st.markdown(f"#### {t('interp.summary_header')}")
    for line in interpret.generate(factors, res, rels, theta, t, decimals):
        st.markdown(f"- {line}")

    ai_section("results")

with tab_mat:
    with st.expander(t("mat.A"), expanded=True):
        st.dataframe(export.matrix_frame(res.A, factors).style.format(num), width="stretch")
    with st.expander(t("mat.X")):
        st.caption(t("mat.X_caption", s=num(res.s)))
        st.dataframe(export.matrix_frame(res.X, factors).style.format(num), width="stretch")
    with st.expander(t("mat.T"), expanded=True):
        st.caption(t("mat.T_caption", theta=num(theta)))
        off_diag = ~np.eye(n, dtype=bool)
        T_df = export.matrix_frame(res.T, factors)
        css = pd.DataFrame(np.where((res.T >= theta) & off_diag, HIGHLIGHT, ""), index=T_df.index, columns=T_df.columns)
        st.dataframe(T_df.style.format(num).apply(lambda _: css, axis=None), width="stretch")
    with st.expander(t("mat.gap")):
        if not gaps:
            st.info(t("summary.gap_na"))
        else:
            st.caption(t("mat.gap_caption", limit=f"{gap_limit:g}"))
            st.dataframe(
                pd.DataFrame({
                    t("gap.col_p"): [p for p, _ in gaps],
                    t("gap.col_gap"): [f"{g:.2f}" if g is not None else "—" for _, g in gaps],
                    t("gap.col_result"): [
                        "—" if g is None else t("gap.ok") if g < gap_limit else t("gap.ng") for _, g in gaps
                    ],
                }),
                hide_index=True, width="stretch",
            )
    ai_section("procedure")

with tab_exp:
    st.caption(t("exp.hint"))
    A_df, X_df, T_df = (export.matrix_frame(M, factors) for M in (res.A, res.X, res.T))
    c1, c2 = st.columns(2)
    c1.download_button(
        t("exp.csv_indicators"), export.to_csv_bytes(indicators, index=False),
        file_name="dematel_indicators.csv", mime="text/csv", width="stretch",
    )
    c1.download_button(t("exp.csv_A"), export.to_csv_bytes(A_df), file_name="dematel_A.csv", mime="text/csv", width="stretch")
    c1.download_button(t("exp.csv_X"), export.to_csv_bytes(X_df), file_name="dematel_X.csv", mime="text/csv", width="stretch")
    c1.download_button(t("exp.csv_T"), export.to_csv_bytes(T_df), file_name="dematel_T.csv", mime="text/csv", width="stretch")

    settings = pd.DataFrame({
        t("set.item"): [
            t("summary.experts"), t("summary.factors"), t("settings.scale_max"), t("summary.s"),
            t("threshold.method"), t("threshold.theta"), t("summary.gap"),
        ],
        t("set.value"): [
            H, n, scale_max, res.s, t(f"threshold.{method}"), theta,
            "—" if final_gap is None else round(final_gap, 4),
        ],
    })
    sheets = [(name, export.matrix_frame(m.values, factors), True) for name, m in zip(expert_names, matrices)]
    sheets += [
        (t("sheet.A"), A_df, True),
        (t("sheet.X"), X_df, True),
        (t("sheet.T"), T_df, True),
        (t("sheet.indicators"), indicators, False),
        (t("sheet.settings"), settings, False),
    ]
    c2.download_button(
        t("exp.excel"), export.to_excel_bytes(sheets), file_name="dematel_results.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary", width="stretch",
    )
    c2.caption(t("exp.excel_hint"))
