# DEMATEL 분석 AI 시스템

전문가가 평가한 요인 간 영향 행렬(CSV)을 업로드하면 **DEMATEL** 분석을 수행하고, 지표 테이블·인과 네트워크 지도(INRM)·결과 해석을 출력하는 웹 애플리케이션입니다. (English / 繁體中文 / 한국어)

- 서비스 주소: **https://thugmba.thu.edu.tw**
- 기술 스택: Python · Streamlit · NumPy · pandas · Plotly

## 설명서

| 문서 | 대상 | 내용 |
|---|---|---|
| [사용자 설명서](docs/user-guide.md) | 앱 사용자, 서버 관리자 | 설치, 테스트, 사용 방법 |
| [개발자 설명서](docs/developer-guide.md) | 개발자 | 요구사항 명세, 분석 알고리즘, 다국어, 기술 스택, 구조, 배포 |

## 빠른 시작

```bash
git clone https://github.com/thugmba/dematel.git
cd dematel
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/streamlit run app.py      # http://localhost:3000
```
