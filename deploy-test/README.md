# Streamlit 배포 테스트 (학교 VM · 포트 3000)

학교 VM에서 Streamlit을 포트 3000으로 실행했을 때 `https://thugmba.thu.edu.tw` 포워딩을 통해 정상 동작하는지 확인하는 테스트입니다. 본 DEMATEL 앱을 만들기 전에 다음 사항을 미리 확인합니다.

```
사용자 브라우저 ──HTTPS──▶ Cloudflare ──▶ 학교 포워딩 ──▶ VM:3000 (Streamlit)
```

- HTTPS는 학교 앞단의 Cloudflare가 처리합니다. VM에서는 nginx·인증서 설정 없이 Streamlit을 3000번으로 실행하기만 하면 됩니다.

- 학교 포워딩이 **WebSocket**을 통과시키는지 (Streamlit 동작의 필수 조건)
- 프록시를 거쳐도 **CSV 업로드**가 되는지 (403 오류 여부)
- 장시간 연결이 유지되는지

### 테스트 결과 (2026-10-30)

| 항목 | 결과 |
|---|---|
| 외부 접속 `https://thugmba.thu.edu.tw/` | ✅ 200 |
| 헬스체크 `/_stcore/health` | ✅ `ok` |
| WebSocket `/_stcore/stream` (Cloudflare 경유) | ✅ 101 연결 성공 |
| 화면 동작 (슬라이더 등) | ✅ 정상 |
| CSV 업로드 (403 여부) | ⬜ 확인 필요 |
| 10분 이상 연결 유지 | ⬜ 확인 필요 |

## 파일 구성

```
deploy-test/
├── app.py                  # 테스트 앱 (확인 항목 1~6)
├── requirements.txt        # streamlit, numpy, pandas, plotly
├── .streamlit/config.toml  # 0.0.0.0:3000 수신 설정
├── samples/
│   ├── expert_utf8.csv     # 한글 요인명, UTF-8(BOM) 인코딩
│   └── expert_cp949.csv    # 한글 요인명, CP949 인코딩 (Excel 저장 형식)
└── README.md               # 이 문서
```

---

## 1. 로컬 PC: GitHub에 올리기

```bash
cd ~/Projects/dematel
git add .gitignore deploy-test/
git commit -m "Add Streamlit deployment test app"
git push origin main
```

---

## 2. 서버: 사전 확인

SSH로 VM에 접속한 뒤 실행합니다.

```bash
# Python 3.10 이상 필요
python3 --version

# venv 모듈 확인 (오류가 나면 아래 '문제 해결' 참고)
python3 -m venv --help > /dev/null && echo "venv OK"

# 3000번 포트를 쓰고 있는 프로그램 확인 (기존 Node 앱)
sudo ss -ltnp | grep :3000
```

3000번 포트를 사용 중인 프로그램이 있으면 먼저 중지합니다. 실행 방식에 따라 명령이 다릅니다.

> **이 VM에는 nginx가 기본 설치되어 3000번을 점유하고 있었습니다.** 외부 접속 시 "Welcome to nginx!" 페이지가 보이면 이 경우입니다. nginx는 이 구성에서 필요 없으므로 중지하고 자동 시작을 해제합니다.
>
> ```bash
> sudo systemctl stop nginx
> sudo systemctl disable nginx     # 재부팅 후 다시 켜지지 않게
> ```
>
> 나중에 다시 필요하면 `sudo systemctl enable --now nginx`로 되돌릴 수 있습니다.

```bash
pm2 list && pm2 stop <앱 이름>          # pm2로 실행 중인 경우
sudo systemctl stop <서비스 이름>        # systemd 서비스인 경우
kill <PID>                               # 직접 실행한 경우 (PID는 위 ss 결과에서 확인)
```

---

## 3. 서버: 설치

```bash
cd ~
git clone https://github.com/thugmba/dematel.git
cd dematel

python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r deploy-test/requirements.txt
```

> 저장소가 **private**이면 `git clone` 시 비밀번호 대신 GitHub Personal Access Token을 입력해야 합니다.
> (GitHub → Settings → Developer settings → Personal access tokens에서 `repo` 읽기 권한으로 발급)

---

## 4. 서버: 실행

`.streamlit/config.toml`은 **실행하는 위치 기준**으로 읽히므로 반드시 `deploy-test` 폴더에서 실행합니다.

### 4-1. 화면에 띄워 실행 (첫 테스트용)

```bash
cd ~/dematel/deploy-test
../.venv/bin/streamlit run app.py
```

`Uvicorn server started on 0.0.0.0:3000` 또는 `URL: http://0.0.0.0:3000`이 보이면 실행된 것입니다. 종료하려면 `Ctrl+C`를 누릅니다. 이 방식은 **SSH 접속을 끊으면 앱도 종료**됩니다.

VM 안에서 먼저 응답을 확인할 수 있습니다(다른 SSH 창에서 실행).

```bash
curl http://localhost:3000/_stcore/health      # "ok"가 나오면 정상
```

### 4-2. 백그라운드 실행 (SSH를 끊어도 유지)

```bash
cd ~/dematel/deploy-test
nohup ../.venv/bin/streamlit run app.py > streamlit.log 2>&1 &

tail -f streamlit.log                  # 로그 보기 (Ctrl+C로 보기만 종료)
pkill -f "streamlit run app.py"        # 앱 종료
```

---

## 5. 외부 접속 확인 체크리스트

PC나 휴대폰 브라우저에서 `https://thugmba.thu.edu.tw`로 접속해 화면의 1~6번 항목을 순서대로 확인합니다.

| # | 확인 항목 | 방법 | 정상 결과 |
|:-:|---|---|---|
| 0 | 페이지 접속 | 주소 입력 | "Streamlit 배포 테스트" 제목 표시 |
| 1 | WebSocket | 슬라이더 이동 | 선택값·갱신 횟수가 즉시 바뀜 |
| 2 | CSV 업로드 | `samples/`의 두 파일을 함께 업로드 | 두 파일 모두 한글 요인명 표가 표시되고 인코딩이 각각 `utf-8-sig`, `cp949`로 나옴 |
| 3 | 계산·그래프 | 그래프에 마우스 오버, 툴바 카메라 아이콘 | 값 표시, PNG 저장됨 |
| 4 | 다운로드 | "결과 CSV 다운로드" 클릭 | `test_result.csv` 저장, Excel에서 열림 |
| 5 | 언어·URL | 5번 항목의 "언어 선택" 드롭다운 변경 | 인사말만 바뀌고 주소창에 `?lang=...` 표시. 브라우저 언어 값 확인 (테스트 앱은 화면 전체를 번역하지 않음) |
| 6 | 장시간 연결 | 탭을 10분 이상 둔 뒤 슬라이더 이동 | "세션 시작 시각"이 바뀌지 않음 |

> 샘플 CSV는 서버가 아니라 **접속하는 PC**에 있어야 업로드할 수 있습니다. GitHub 저장소 페이지에서 `deploy-test/samples/`의 파일을 내려받아 사용하세요.

6번 "연결 정보" 표의 `Host`, `X-Forwarded-For`, `X-Forwarded-Proto` 값은 학교 프록시 구성을 파악하는 데 쓰이므로 결과와 함께 기록해 두세요.

---

## 6. 문제 해결

| 증상 | 원인 | 해결 |
|---|---|---|
| 외부 접속 시 "Welcome to nginx!" 페이지 | VM의 nginx가 3000번 점유 | 2단계의 nginx 중지 |
| 접속 시 "Please wait..." 또는 로딩 화면에서 멈춤 | 학교 포워딩이 **WebSocket 차단** | 전산실에 `thugmba.thu.edu.tw`의 WebSocket(HTTP Upgrade 헤더) 허용 요청. 이 문제가 해결되지 않으면 Streamlit 사용 불가 |
| 업로드 시 `AxiosError: Request failed with status code 403` | 프록시와 XSRF 보호 충돌 | `.streamlit/config.toml`에서 `enableXsrfProtection = false`, `enableCORS = false` 주석 해제 후 재실행 |
| 업로드 시 413 오류 | 학교 프록시의 업로드 크기 제한 | 전산실에 제한 크기 문의 (CSV는 보통 수 KB라 문제 가능성 낮음) |
| 10분 후 "세션 시작 시각"이 바뀜 | 프록시의 유휴 연결 시간 초과 | 사용에는 지장 없지만 업로드한 데이터가 초기화됨. 전산실에 WebSocket timeout 연장 문의 |
| `Address already in use` | 3000번 포트 사용 중 | 2단계의 `ss -ltnp \| grep :3000`으로 확인 후 기존 프로그램 중지 |
| `python3 -m venv` 실패 (`ensurepip is not available`) | venv 패키지 미설치 | `sudo apt install python3-venv`. sudo 권한이 없으면 아래 uv 사용 |
| 외부에서 접속 안 되는데 `curl localhost:3000/_stcore/health`는 `ok` | 수신 주소 또는 방화벽 | 로그에 `0.0.0.0:3000`인지 확인. VM 방화벽(`sudo ufw status`)에서 3000 허용 |

**sudo 권한 없이 Python 환경 만들기 (uv)**

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc
cd ~/dematel
uv venv .venv --python 3.12
uv pip install --python .venv -r deploy-test/requirements.txt
```

---

## 7. 코드 업데이트 후 재실행

```bash
pkill -f "streamlit run app.py"
cd ~/dematel && git pull
.venv/bin/pip install -r deploy-test/requirements.txt
cd deploy-test && nohup ../.venv/bin/streamlit run app.py > streamlit.log 2>&1 &
```

## 8. 테스트 종료 후

```bash
pkill -f "streamlit run app.py"
# 필요하면 기존 Node 앱 재시작 (예: pm2 start <앱 이름>)
```

`.venv`는 본 DEMATEL 앱에서도 그대로 사용할 수 있으므로 지우지 않아도 됩니다.
