"""Streamlit 기본 index.html의 제목·설명·링크 미리보기 정보를 이 앱에 맞게 바꾼다.

메신저·SNS의 링크 미리보기는 JavaScript를 실행하지 않으므로, 이 HTML의 <title>과 <noscript>
문구("Streamlit", "You need to enable JavaScript…")가 그대로 보인다. Streamlit을 설치·업그레이드할
때마다 파일이 원래대로 돌아가므로 `pip install` 뒤에 다시 실행해야 한다. 원본은 index.html.orig로
보관하고 항상 원본에서 다시 만들므로 여러 번 실행해도 결과가 같다.

    .venv/bin/python scripts/patch_index_html.py
"""

import html
import shutil
from pathlib import Path

import streamlit

TITLE = "DEMATEL 분석 AI 시스템 | DEMATEL Analysis AI System"
DESCRIPTION = (
    "전문가 영향 행렬(CSV)로 DEMATEL 분석, 인과 네트워크 지도(INRM), AI 논문 문장 생성. "
    "DEMATEL analysis, INRM and AI-assisted paper writing. 支援繁體中文."
)
URL = "https://thugmba.thu.edu.tw"
NOSCRIPT = "이 앱을 사용하려면 JavaScript를 켜 주세요. Please enable JavaScript to use this app."

ORIGINAL_TITLE = "<title>Streamlit</title>"
ORIGINAL_NOSCRIPT = "<noscript>You need to enable JavaScript to run this app.</noscript>"


def main() -> None:
    index = Path(streamlit.__file__).parent / "static" / "index.html"
    original = index.with_name("index.html.orig")
    if not original.exists():
        shutil.copy2(index, original)
    text = original.read_text(encoding="utf-8")

    for marker in (ORIGINAL_TITLE, ORIGINAL_NOSCRIPT):
        if marker not in text:
            raise SystemExit(f"index.html 구조가 바뀌어 수정할 수 없습니다 (찾지 못함: {marker})")

    t, d = html.escape(TITLE), html.escape(DESCRIPTION)
    head = "\n    ".join([
        f"<title>{t}</title>",
        f'<meta name="description" content="{d}" />',
        '<meta property="og:type" content="website" />',
        f'<meta property="og:title" content="{t}" />',
        f'<meta property="og:description" content="{d}" />',
        f'<meta property="og:url" content="{URL}" />',
        '<meta name="twitter:card" content="summary" />',
    ])
    text = text.replace(ORIGINAL_TITLE, head).replace(ORIGINAL_NOSCRIPT, f"<noscript>{html.escape(NOSCRIPT)}</noscript>")
    index.write_text(text, encoding="utf-8")
    print(f"patched: {index}")


if __name__ == "__main__":
    main()
