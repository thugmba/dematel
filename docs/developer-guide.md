# DEMATEL 분석 AI 시스템 — 개발자 설명서

> 사용 방법은 [사용자 설명서](user-guide.md)를 참고하세요. 이 문서는 요구사항 명세, 분석 알고리즘, 구조, 배포 등 개발·유지보수 정보를 다룹니다.

전문가가 평가한 요인 간 영향 행렬(CSV)을 업로드하면 **DEMATEL(Decision Making Trial and Evaluation Laboratory)** 분석을 수행하고, 지표 테이블·결과 해석·인과 네트워크 지도(INRM)를 출력하는 웹 애플리케이션입니다.

> **개발 현황**: v0.1 — 명세의 입력·분석·출력·다국어 기능 구현 완료. 논문 예제 데이터와의 대조 검증은 진행 예정([테스트](#테스트)).
>
> 서비스 주소: **https://thugmba.thu.edu.tw**

---

## 목차

1. [주요 기능](#주요-기능)
2. [다국어 지원](#다국어-지원)
3. [입력](#입력)
4. [분석 절차](#분석-절차)
5. [출력](#출력)
6. [기술 스택](#기술-스택)
7. [설치 및 실행](#설치-및-실행)
8. [디렉터리 구조](#디렉터리-구조)
9. [테스트](#테스트)
10. [데이터 처리 및 개인정보](#데이터-처리-및-개인정보)
11. [범위 및 향후 계획](#범위-및-향후-계획)
12. [참고문헌](#참고문헌)
13. [라이선스](#라이선스)

---

## 주요 기능

- 전문가별 CSV 파일 다중 업로드 및 형식 검증
- 전문가 응답 통합(산술평균) 및 합의도 검증
- 정규화 → 총영향행렬 T 계산
- R, C, 중심도(R+C), 원인도(R−C), 가중치, 원인/결과 구분 테이블 생성
- 임계값 기반 인과 네트워크 지도(INRM) 시각화
- 분석 결과 자동 해석 문장 생성
- 결과 내보내기(CSV / Excel / PNG·SVG)
- 다국어 UI: **English / 繁體中文(台灣) / 한국어**

---

## 다국어 지원

| 언어 | 코드 |
|---|---|
| English | `en` |
| 繁體中文(台灣) | `zh-TW` |
| 한국어 | `ko` |

- 화면 상단의 언어 선택 메뉴에서 언제든 전환할 수 있으며, 전환해도 업로드한 데이터와 분석 결과는 유지됩니다.
- 최초 접속 시 브라우저 언어 설정(`st.context.locale`)을 따르고, 지원하지 않는 언어이면 English로 표시합니다.
- 선택한 언어는 URL 쿼리 파라미터(`?lang=ko`, `?lang=zh-TW`, `?lang=en`)에 반영되므로, 해당 URL을 북마크하거나 공유하면 같은 언어로 열립니다.
- **번역 대상**: 메뉴·버튼·안내문, 입력 검증 오류/경고 메시지, 지표 테이블 머리글과 구분값(원인/결과), INRM 축·사분면 라벨, 결과 해석 문장, 내보내기 파일(CSV·Excel 머리글, 시트명, INRM 그림 라벨)
- **번역하지 않는 것**: 사용자가 입력한 요인명(입력 그대로 표시)
- 숫자 형식(소수점·천 단위 구분)은 세 언어 모두 `1,234.567` 형식으로 통일합니다.
- 용어 대응표:

| 한국어 | English | 繁體中文 |
|---|---|---|
| 직접영향행렬 | Direct-relation matrix | 直接影響矩陣 |
| 정규화 직접영향행렬 | Normalized direct-relation matrix | 正規化直接影響矩陣 |
| 총영향행렬 | Total-relation matrix | 總影響矩陣 |
| 중심도 (R+C) | Prominence | 中心度 |
| 원인도 (R−C) | Relation | 原因度 |
| 가중치 | Weight | 權重 |
| 원인군 / 결과군 | Cause group / Effect group | 原因群 / 結果群 |
| 임계값 | Threshold | 門檻值 |
| 인과 네트워크 지도 | Influential Network Relation Map (INRM) | 影響網絡關係圖 (INRM) |

---

## 입력

### 파일 형식

- **CSV 파일**, 전문가 1인당 1개 파일
- 전문가가 여러 명이면 각 파일을 별도로 업로드 (복수 선택 가능)
- 인코딩: **UTF-8(BOM 포함/미포함)** 및 **CP949(EUC-KR)** 자동 인식 — Excel에서 저장한 한글 CSV 지원

### 행렬 구조

- 첫 행과 첫 열에 **요인명**을 기재하고, 나머지는 n × n 정사각 행렬
- 셀 aᵢⱼ = 요인 i가 요인 j에 미치는 직접 영향의 정도
- 대각 원소(aᵢᵢ)는 **0**

### 평가 척도 (기본값)

| 점수 | 의미 |
|:---:|---|
| 0 | 영향 없음 |
| 1 | 낮은 영향 |
| 2 | 보통 영향 |
| 3 | 높은 영향 |
| 4 | 매우 높은 영향 |

척도 최댓값은 설정에서 변경할 수 있습니다(예: 0–3, 0–5).

### 입력 예시 (`samples/expert_01.csv`)

```csv
,F1,F2,F3,F4
F1,0,3,2,1
F2,1,0,4,2
F3,2,1,0,3
F4,0,2,1,0
```

### 검증 규칙

업로드 시 다음을 검사하고, 위반 시 **파일명·행·열 위치를 포함한 오류 메시지**를 표시합니다.

| 항목 | 조건 | 처리 |
|---|---|---|
| 행렬 형태 | 정사각 행렬(n × n), n ≥ 2 | 오류 |
| 요인명 일치 | 행 요인명과 열 요인명이 같은 순서로 일치 | 오류 |
| 전문가 간 일치 | 모든 파일의 요인 수·요인명·순서가 동일 | 오류 |
| 값 형식 | 숫자만 허용(빈 칸, 문자 불가) | 오류 |
| 값 범위 | 0 ≤ aᵢⱼ ≤ 척도 최댓값 | 오류 |
| 대각 원소 | aᵢᵢ = 0 | 경고 후 0으로 대체 |
| 정수 여부 | 척도는 정수 기준 | 소수는 경고 후 허용 |

---

## 분석 절차

H명의 전문가, n개의 요인을 가정합니다.

### 1단계. 평균 직접영향행렬 A

각 전문가 k의 행렬 Aᵏ = [aᵢⱼᵏ]를 산술평균합니다.

$$
A = [a_{ij}], \quad a_{ij} = \frac{1}{H}\sum_{k=1}^{H} a_{ij}^{k}
$$

### 2단계. (선택) 합의도 검증

전문가 수가 p−1명에서 p명으로 늘 때 평균 행렬이 얼마나 변하는지로 응답의 안정성을 확인합니다.

$$
\text{Gap}(\%) = \frac{1}{n(n-1)} \sum_{i \ne j} \frac{\left| a_{ij}^{(p)} - a_{ij}^{(p-1)} \right|}{a_{ij}^{(p)}} \times 100
$$

- a⁽ᵖ⁾ᵢⱼ: p명의 평균값. a⁽ᵖ⁾ᵢⱼ = 0인 셀은 계산에서 제외하고, 나머지 셀의 평균으로 계산 (위 식의 n(n−1)은 제외한 셀 수만큼 줄어듦)
- 전문가는 업로드 순서대로 추가되며, p = 2..H 각각의 Gap을 표로 보여 줌
- Gap < 5%이면 합의에 도달한 것으로 판단 (기준값 설정 가능)
- 전문가가 2명 이상일 때만 계산하며, 결과는 참고 지표로 표시하고 분석을 중단하지 않음

### 3단계. 정규화 직접영향행렬 X

$$
X = \frac{A}{s}, \quad s = \max\left( \max_{i}\sum_{j=1}^{n} a_{ij},\ \max_{j}\sum_{i=1}^{n} a_{ij} \right)
$$

- s = 0(모든 값이 0)이면 분석 불가 오류 처리

### 4단계. 총영향행렬 T

$$
T = X(I - X)^{-1}
$$

- I: n × n 단위행렬
- (I − X)가 특이행렬이면(역행렬 불가) 오류 메시지 표시

### 5단계. 지표 계산

T = [tᵢⱼ]에 대해

| 기호 | 정의 | 의미 |
|---|---|---|
| Rᵢ | Σⱼ tᵢⱼ (행 합) | 요인 i가 다른 요인에 **주는** 총영향 |
| Cᵢ | Σⱼ tⱼᵢ (열 합) | 요인 i가 다른 요인으로부터 **받는** 총영향 |
| R+C | 중심도 (Prominence) | 시스템 내 요인의 중요도·관여 정도 |
| R−C | 원인도 (Relation) | 양수면 원인 요인, 음수면 결과 요인 |
| wᵢ | 가중치 (Weight) | 아래 식으로 계산한 상대적 중요도 |

$$
w_i' = \sqrt{(R_i + C_i)^2 + (R_i - C_i)^2}, \quad w_i = \frac{w_i'}{\sum_{k=1}^{n} w_k'}
$$

**구분 기준**: R−C > 0 → **원인군(Cause)**, R−C < 0 → **결과군(Effect)**, R−C = 0 → 중립

### 6단계. 임계값 설정

INRM에 표시할 영향 관계를 고르는 기준입니다. tᵢⱼ ≥ θ인 관계만 표시합니다.

| 방법 | θ | 비고 |
|---|---|---|
| 평균 (기본값) | T 전체 원소의 평균 | 가장 널리 쓰이는 방식 |
| 평균 + 표준편차 | μ + σ | 관계가 많을 때 핵심만 표시 |
| 사용자 지정 | 직접 입력 | 슬라이더로 실시간 조정 |

대각 원소(tᵢᵢ)는 INRM 화살표에서 제외합니다.

---

## 출력

### 1. 지표 테이블

| 요인 | R | C | R+C | R−C | 가중치 | 순위 | 구분 |
|---|---:|---:|---:|---:|---:|:---:|:---:|
| F1 | 1.234 | 0.987 | 2.221 | 0.247 | 0.262 | 2 | 원인 |
| F2 | … | … | … | … | … | … | 결과 |

- 기본 정렬: R+C 내림차순 (열 머리글 클릭으로 정렬 변경)
- 소수점: 기본 3자리 (설정 가능)
- *위 표의 숫자는 형식 예시이며 실제 계산값이 아님*

### 2. 중간 행렬 (펼침 패널)

- 평균 직접영향행렬 A
- 정규화 직접영향행렬 X
- 총영향행렬 T (임계값 이상 셀 강조)
- 합의도 Gap(%) (전문가 2명 이상인 경우)

### 3. 인과 네트워크 지도 (INRM)

- **x축**: R+C (중심도), **y축**: R−C (원인도)
- y = 0 기준선(원인/결과 구분)과 x = R+C 평균 기준선으로 4개 사분면 표시
- 각 요인은 점과 요인명 라벨로 표시
- tᵢⱼ ≥ θ인 관계를 i → j 화살표로 표시하고, 양방향이면 양쪽 화살표로 표시
- 화살표 굵기는 tᵢⱼ 크기에 비례, 마우스 오버 시 tᵢⱼ 값 표시

| 사분면 | 위치 | 해석 |
|---|---|---|
| Ⅰ | R+C 높음, R−C > 0 | 핵심 원인 요인 — 우선 관리 대상 |
| Ⅱ | R+C 낮음, R−C > 0 | 독립적 원인 요인 — 다른 요인에 일부 영향 |
| Ⅲ | R+C 낮음, R−C < 0 | 독립적 결과 요인 — 상대적 중요도 낮음 |
| Ⅳ | R+C 높음, R−C < 0 | 핵심 결과 요인 — 원인 요인 개선으로 간접 관리 |

### 4. 결과 해석

규칙 기반 템플릿으로 다음 문장을 자동 생성합니다.

- 중심도 상위 요인과 그 값
- 원인군·결과군 요인 목록
- 원인도가 가장 큰 요인(가장 강한 원인)과 가장 작은 요인(가장 강한 결과)
- 사분면별 요인 분류와 관리 시사점
- 임계값을 넘는 영향 관계 수와 가장 강한 관계 상위 N개

#### 논문용 문장 (AI)

학교 제공 LLM(OpenAI 호환 API)으로 각 탭의 결과를 논문 문장으로 옮깁니다. **분석은 모두 Python이 하고, LLM은 결과를 문장으로 쓰는 일만 합니다.** 사용자가 버튼을 누를 때만 호출합니다.

| 탭 | 종류(`kind`) | 작성 내용 |
|---|---|---|
| 지표 테이블 | `indicators` | 표 제목, 기호 주석(값 없이 정의만), 표 설명 문단 |
| INRM | `inrm` | 그림 제목, 그림 설명 문단 |
| 결과 해석 | `results` | 연구 결과(Results) 3–5문단 |
| 중간 행렬 | `procedure` | 분석 절차(연구 방법) 문단, 수식 없음 |

**숫자 차단 방식 (자리표시자)**

1. `llm.build_context()`가 Python 계산값으로 자리표시자 사전과 사실 목록을 만듭니다.
   - 요인명 `{F1}`…, 요인별 `{R:F1}` `{C:F1}` `{P:F1}`(R+C) `{D:F1}`(R−C) `{W:F1}`(가중치) `{rank:F1}`
   - 관계 `{t:F1>F2}`(T) `{a:F1>F2}`(A), 전체 값 `{n_experts}` `{n_factors}` `{scale_max}` `{scale_points}` `{s}` `{theta}` `{p_mean}` `{n_above}` `{n_pairs}` `{n_cause}` `{n_effect}` `{gap}` `{gap_limit}`, 단계별 `{experts_at:p}` `{gap_at:p}`
2. 시스템 프롬프트로 **숫자(0–9)를 한 글자도 쓰지 말고** 자리표시자만 쓰게 합니다. 요인명도 자리표시자로만 씁니다.
3. `find_violations()`가 응답을 검사합니다. 자리표시자 밖의 숫자(아라비아·전각·위첨자·아래첨자), 정의되지 않은 자리표시자, 짝이 맞지 않는 중괄호, 빈 응답이 위반입니다.
4. 위반이 있으면 위반 내용을 대화에 덧붙여 최대 2회 다시 요청하고(`MAX_RETRIES`), 그래도 실패하면 `GenerationFailed`로 **차단**하여 화면에 문장을 보여 주지 않습니다.
5. 통과하면 `render()`가 자리표시자를 계산값으로 바꿉니다. 화면에 "수치 N개가 모두 Python 계산값"이라는 검증 표시를 붙입니다.

| 항목 | 내용 |
|---|---|
| 설정 | `.env`의 `LLM_API_KEY`, `LLM_MODEL`(필수), `LLM_BASE_URL`(선택, 기본 `https://api.ithu.tw/v1`). 필수 값이 없으면 안내 문구만 표시 |
| 전송 내용 | 사실 목록(요인명, 지표, 사분면, θ 이상 관계 상위 15개, 합의도)과 선택 입력인 연구 주제. **업로드 파일 원본은 보내지 않음** |
| 작성 언어 | 사이드바 "AI 논문 문장"에서 선택. 기본값은 화면 언어이며, 화면 언어를 바꾸면 새 화면 언어로 다시 맞춤 |
| 프롬프트 규칙 | 숫자 금지·자리표시자 사용, 부호를 자리표시자 앞에 붙이지 않음, 사분면은 로마 숫자, 용어 대응표의 용어 사용, 표·그림은 "Table X"·"Figure X"(언어별 표기), 글머리표·수식·인용·추측 금지 |
| 호출 | `openai_completer()` (비스트리밍, temperature 0.3, 타임아웃 120초). 문장 전체를 받아 검증한 뒤에만 보여 주므로 스트리밍하지 않음 |
| 캐시 | 모델·메시지의 SHA-256을 키로 `st.session_state.ai_results`에 보관 |
| 다시 생성 | 학교 서버가 **같은 요청에 같은 답을 캐시해 돌려주므로**(2026-10-30 확인), 다시 생성할 때는 `with_request_id()`로 고유 ID를 붙여 보냄 |

**한계**: 이 방식은 화면의 모든 숫자가 Python 계산값임을 보장하지만, 올바른 값을 **다른 의미의 자리**에 쓰는 오류까지 자동으로 막지는 못합니다(예: 처음에는 단계별 Gap 값을 전문가 수로 씀 → `{experts_at:p}`를 추가해 해결). 숫자를 글자로 쓰는 것("세 명")도 프롬프트로만 막습니다. 그래서 화면에 문장 표현과 해석을 검토하라는 안내를 항상 표시합니다. 한국어에서는 자리표시자 뒤 조사가 값과 맞지 않을 수 있습니다(예: "Training가").

**검증 (2026-10-30, 샘플 데이터)**: 4종류 × 3개 언어 모두 통과했습니다(일부는 재시도 1회 후). 단계별 Gap 문장과 5점 척도 표현이 바르게 나오는 것도 확인했습니다.

### 5. 내보내기

| 형식 | 내용 |
|---|---|
| CSV | 지표 테이블, 각 행렬 |
| Excel (.xlsx) | 입력 원자료, A, X, T, 지표 테이블을 시트별로 저장 |
| PNG / SVG | INRM 그림 (Plotly 차트 툴바의 다운로드 버튼, 브라우저에서 생성) |

---

## 기술 스택

| 구분 | 사용 기술 | 용도 |
|---|---|---|
| 언어 | Python 3.11 이상 | |
| 웹 UI | [Streamlit](https://streamlit.io) 1.45 이상 | 화면 구성, 파일 업로드, 슬라이더, 다운로드 |
| 행렬 계산 | NumPy | 평균, 정규화, 역행렬(`numpy.linalg.solve`) |
| 표 처리 | pandas | CSV 읽기, 지표 테이블, CSV 내보내기 |
| 시각화 | Plotly | INRM(마우스 오버, 화살표 굵기, PNG/SVG 다운로드) |
| Excel 내보내기 | openpyxl | `.xlsx` 시트별 저장 |
| 논문용 문장 | openai (OpenAI 호환 클라이언트), python-dotenv | 학교 LLM API 호출, `.env` 읽기 |
| 다국어 | JSON 번역 사전 (`locales/`) | 별도 i18n 라이브러리 없이 키-문자열 매핑 |
| 테스트 | pytest | 계산·검증 로직 단위 테스트 |
| 배포 | 학교 제공 가상 서버 (Ubuntu) | `https://thugmba.thu.edu.tw` → VM 3000번 포트 포워딩 |

설계 원칙:

- **계산 로직과 UI 분리**: `dematel/` 패키지의 함수는 Streamlit에 의존하지 않는 순수 함수로 작성해 pytest로 단독 검증합니다. `app.py`는 입력을 받아 이 함수들을 호출하고 결과를 표시하기만 합니다.
- **역행렬 직접 계산 지양**: T = X(I − X)⁻¹은 `inv()` 대신 `numpy.linalg.solve`로 계산해 수치 오차를 줄이고, 특이행렬이면 `LinAlgError`를 잡아 오류 메시지로 변환합니다.
- **인코딩 처리**: `utf-8-sig` → `cp949` 순서로 디코딩을 시도하며, 추가 라이브러리를 쓰지 않습니다.
- **상태 관리**: 업로드 데이터와 계산 결과는 `st.session_state`에만 보관하고, 계산 함수는 `st.cache_data`로 캐시해 임계값 슬라이더 조작 시 T를 다시 계산하지 않습니다.

## 설치 및 실행

### 로컬 실행

```bash
git clone <저장소 URL>
cd dematel

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

pip install -r requirements.txt
streamlit run app.py
```

브라우저에서 `http://localhost:3000`으로 접속합니다(포트는 `.streamlit/config.toml`에서 지정).

### 테스트 실행

```bash
pip install -r requirements-dev.txt
pytest
```

### 배포 (학교 가상 서버)

```
사용자 브라우저 ──HTTPS──▶ Cloudflare ──▶ 학교 포워딩 ──▶ VM:3000 (Streamlit)
```

- 외부 주소 **`https://thugmba.thu.edu.tw`** 로 들어온 요청은 학교가 가상 서버의 **3000번 포트**로 포워딩합니다.
- HTTPS 인증서는 학교 앞단의 Cloudflare가 처리하므로 VM에서 nginx나 인증서를 설정할 필요가 없습니다. Streamlit을 `0.0.0.0:3000`으로 실행하기만 하면 됩니다.
- Cloudflare·학교 포워딩을 거친 WebSocket 연결은 확인 완료(2026-10-30, `deploy-test/` 테스트 앱).

`.streamlit/config.toml`:

```toml
[server]
address = "0.0.0.0"
port = 3000
headless = true
maxUploadSize = 10

[browser]
gatherUsageStats = false
```

서버에서 최초 설치·실행:

```bash
# 3000번을 다른 프로그램이 쓰고 있지 않은지 확인 (VM 기본 설치된 nginx가 점유하는 경우가 있음)
sudo ss -ltnp | grep :3000
sudo systemctl stop nginx && sudo systemctl disable nginx   # nginx가 점유 중일 때만

cd ~ && git clone https://github.com/thugmba/dematel.git && cd dematel
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
nohup .venv/bin/streamlit run app.py > streamlit.log 2>&1 &
curl http://localhost:3000/_stcore/health   # ok
```

코드 업데이트:

```bash
pkill -f "streamlit run app.py"
cd ~/dematel && git pull
.venv/bin/pip install -r requirements.txt
nohup .venv/bin/streamlit run app.py > streamlit.log 2>&1 &
```

자세한 확인 절차와 문제 해결은 [`deploy-test/README.md`](../deploy-test/README.md)를 참고하세요.

## 디렉터리 구조

```
dematel/
├── app.py                  # Streamlit 진입점 (화면 구성만 담당)
├── dematel/                # 계산 로직 패키지 (Streamlit 비의존)
│   ├── __init__.py
│   ├── loader.py           # CSV 읽기, 인코딩 인식, 입력 검증
│   ├── core.py             # 평균 A, 합의도 Gap, 정규화 X, 총영향 T, R·C·가중치
│   ├── threshold.py        # 임계값 계산(평균, 평균+표준편차, 사용자 지정)
│   ├── inrm.py             # INRM Plotly Figure 생성
│   ├── interpret.py        # 결과 해석 문장 생성 (템플릿 기반)
│   ├── llm.py              # 논문용 문장: 자리표시자·사실 목록, 프롬프트, 위반 검사·재시도·차단, 학교 LLM 호출
│   ├── export.py           # CSV / Excel 내보내기
│   └── i18n.py             # 언어 감지·전환, 번역 함수 t(key)
├── locales/
│   ├── en.json
│   ├── zh-TW.json
│   └── ko.json
├── samples/                # 예시 입력 CSV (전문가 3명 × 요인 5개, '샘플 데이터 불러오기'에 사용)
│   ├── expert_01.csv
│   ├── expert_02.csv
│   └── expert_03.csv
├── tests/
│   ├── test_core.py        # 계산: 손계산 예제, 급수 전개 대조, 합의도, 임계값
│   ├── test_loader.py      # 입력 검증 규칙, 인코딩, 구분자
│   ├── test_outputs.py     # 번역 키 일치, 언어 감지, 3개 언어 출력·Excel
│   └── test_llm.py         # 자리표시자 해석·치환, 위반 검사, 재시도·차단(가짜 LLM), 프롬프트 (네트워크 호출 없음)
├── deploy-test/            # 학교 VM 배포 확인용 테스트 앱
├── docs/
│   ├── developer-guide.md  # 개발자 설명서 (이 문서)
│   └── user-guide.md       # 사용자 설명서 (설치·테스트·사용 방법)
├── .streamlit/
│   └── config.toml         # 포트 3000, 업로드 크기 제한, 툴바
├── pyproject.toml          # pytest 설정
├── requirements.txt
├── requirements-dev.txt    # pytest 등 개발용 의존성
└── README.md               # 프로젝트 소개와 설명서 링크
```

---

## 테스트

- **계산 정확성** (구현됨): 손으로 계산한 2×2 예제와 일치, T가 급수 X + X² + X³ + … 와 일치하는지 대조
- **계산 정확성** (예정): 논문에 실린 DEMATEL 예제 데이터를 입력해 A, X, T, R, C 값이 논문 결과와 소수점 3자리까지 일치하는지 확인
- **입력 검증**: [검증 규칙](#검증-규칙)의 각 항목에 대해 정상/오류 CSV로 테스트
- **경계 조건**: 요인 2개, 전문가 1명, 모든 값 0, 특이행렬, 한글 요인명(UTF-8 / CP949)

---

## 데이터 처리 및 개인정보

- 업로드한 파일은 서버 메모리(`st.session_state`)에서만 처리하며 디스크나 데이터베이스에 저장하지 않습니다. 브라우저 탭을 닫아 세션이 끝나면 삭제됩니다.
- 앱은 `https://thugmba.thu.edu.tw`로 누구나 접속할 수 있는 공개 서비스입니다. 업로드 데이터는 학교 VM의 메모리에서만 처리됩니다.
- 각 탭의 **논문용 문장(AI)** 버튼을 누르면 요인명과 분석 결과 수치가 학교 LLM 서버로 전송됩니다(업로드 파일 원본은 제외). 화면에는 "AI를 이용해서 문단을 생성합니다"라는 일반 안내만 표시하고, 전송 내용은 사용자 설명서 3-9절에 안내합니다.
- `LLM_API_KEY`는 `.env`에만 두며, `.env`는 `.gitignore`로 저장소에서 제외됩니다.
- 파일명이 전문가 이름이면 화면과 내보내기 파일에서는 `Expert 1`, `Expert 2` … 로 익명화하는 옵션을 제공합니다.

---

## 범위 및 향후 계획

| 구분 | 내용 |
|---|---|
| 현재 범위 | Crisp(정수 척도) DEMATEL, 산술평균 통합, 평균 기반 임계값 |
| 향후 검토 | Fuzzy DEMATEL, Grey DEMATEL, DANP(DEMATEL + ANP), 임계값 민감도 분석 |

---

## 참고문헌

- Gabus, A., & Fontela, E. (1972). *World problems, an invitation to further thought within the framework of DEMATEL*. Battelle Geneva Research Centre.
- Gabus, A., & Fontela, E. (1973). *Perceptions of the world problematique: Communication procedure, communicating with those bearing collective responsibility*. Battelle Geneva Research Centre.
- Tzeng, G.-H., Chiang, C.-H., & Li, C.-W. (2007). Evaluating intertwined effects in e-learning programs: A novel hybrid MCDM model based on factor analysis and DEMATEL. *Expert Systems with Applications, 32*(4), 1028–1044.

---

## 라이선스

> TODO: 라이선스 결정 후 기재 (예: MIT)
