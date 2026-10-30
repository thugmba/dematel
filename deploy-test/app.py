"""학교 VM(포트 3000 포워딩) 환경에서 Streamlit이 정상 동작하는지 확인하는 테스트 앱.

확인 항목: WebSocket 상호작용, CSV 업로드(한글 인코딩), NumPy 계산, Plotly 그래프,
파일 다운로드, URL 쿼리 파라미터·브라우저 언어 감지, 프록시 헤더, 장시간 연결 유지.
"""

import datetime as dt
import io
import platform

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title="Streamlit 배포 테스트", layout="wide")

# 세션이 새로 만들어지면(= WebSocket 재연결) 시작 시각과 갱신 횟수가 초기화된다.
if "started" not in st.session_state:
    st.session_state.started = dt.datetime.now()
    st.session_state.reruns = 0
st.session_state.reruns += 1

st.title("Streamlit 배포 테스트")
st.caption("이 화면이 보이면 HTTP 포워딩은 정상입니다. 아래 1~6번을 순서대로 확인하세요.")

# ---------------------------------------------------------------- 1. WebSocket
st.header("1. WebSocket (상호작용)")
n = st.slider("슬라이더를 움직여 보세요", 0, 100, 50)
st.write(f"선택값: **{n}** · 이 세션의 화면 갱신 횟수: **{st.session_state.reruns}**")
st.caption("값과 갱신 횟수가 즉시 바뀌면 WebSocket 정상입니다.")

# ---------------------------------------------------------------- 2. 업로드
st.header("2. CSV 업로드 (한글 인코딩)")
st.caption("`samples/` 폴더의 UTF-8, CP949 파일을 함께 올려 보세요. 403 오류가 나면 README의 문제 해결 참고.")
files = st.file_uploader("CSV 파일 (여러 개 선택 가능)", type="csv", accept_multiple_files=True)
for f in files:
    raw = f.getvalue()
    for enc in ("utf-8-sig", "cp949"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        st.error(f"{f.name}: UTF-8/CP949로 읽을 수 없습니다.")
        continue
    df = pd.read_csv(io.StringIO(text), index_col=0)
    st.write(f"**{f.name}** · {len(raw):,} bytes · 인코딩 `{enc}` · 크기 {df.shape[0]}×{df.shape[1]}")
    st.dataframe(df)

# ---------------------------------------------------------------- 3. 계산 + 그래프
st.header("3. NumPy 계산 + Plotly 그래프")
factors = ["F1", "F2", "F3", "F4"]
A = np.array([[0, 3, 2, 1], [1, 0, 4, 2], [2, 1, 0, 3], [0, 2, 1, 0]], dtype=float)
s = max(A.sum(axis=1).max(), A.sum(axis=0).max())
X = A / s
T = X @ np.linalg.inv(np.eye(len(A)) - X)
R, C = T.sum(axis=1), T.sum(axis=0)
result = pd.DataFrame({"R": R, "C": C, "R+C": R + C, "R-C": R - C}, index=factors).round(3)

left, right = st.columns(2)
left.dataframe(result)
fig = go.Figure(go.Scatter(
    x=R + C, y=R - C, mode="markers+text", text=factors, textposition="top center",
    marker=dict(size=12),
))
fig.add_hline(y=0, line_dash="dash")
fig.update_layout(xaxis_title="R+C", yaxis_title="R-C", height=350, margin=dict(t=20, b=20))
right.plotly_chart(fig, width="stretch")
st.caption("그래프 위에 마우스를 올리면 값이 보이고, 툴바의 카메라 아이콘으로 PNG 저장이 되면 정상입니다.")

# ---------------------------------------------------------------- 4. 다운로드
st.header("4. 파일 다운로드")
st.download_button(
    "결과 CSV 다운로드",
    result.to_csv().encode("utf-8-sig"),
    file_name="test_result.csv",
    mime="text/csv",
)

# ---------------------------------------------------------------- 5. 언어
st.header("5. 언어 감지 · URL 파라미터")
browser_locale = getattr(st.context, "locale", None)
st.write(f"브라우저 언어 (`st.context.locale`): **{browser_locale or '지원 안 됨'}**")
langs = ["en", "zh-TW", "ko"]
current = st.query_params.get("lang", "ko")
lang = st.selectbox("언어 선택", langs, index=langs.index(current) if current in langs else 2)
st.query_params["lang"] = lang
greeting = {"en": "Hello", "zh-TW": "你好", "ko": "안녕하세요"}[lang]
st.write(f"{greeting} · 주소창 URL 끝에 `?lang={lang}`이 붙으면 정상입니다.")

# ---------------------------------------------------------------- 6. 연결 정보
st.header("6. 연결 정보")
headers = st.context.headers
st.table(pd.DataFrame(
    {
        "값": [
            dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            st.session_state.started.strftime("%Y-%m-%d %H:%M:%S"),
            platform.python_version(),
            st.__version__,
            headers.get("Host", "-"),
            headers.get("X-Forwarded-For", "-"),
            headers.get("X-Forwarded-Proto", "-"),
        ]
    },
    index=[
        "서버 시각", "세션 시작 시각", "Python", "Streamlit",
        "Host", "X-Forwarded-For", "X-Forwarded-Proto",
    ],
))
st.caption(
    "장시간 연결 테스트: 이 탭을 10분 이상 그대로 둔 뒤 슬라이더를 움직여 보세요. "
    "'세션 시작 시각'이 그대로면 연결 유지, 바뀌었으면 연결이 끊겼다가 재접속된 것입니다."
)
