#!/usr/bin/env bash
# 운영 서버 업데이트: 중지 → 최신 코드 → 라이브러리 → 링크 미리보기 수정 → 재실행 → 확인
#
#   cd ~/dematel && ./scripts/update.sh
#
# 처음 설치한 서버에서도 쓸 수 있다 (.venv가 없으면 만든다).

set -euo pipefail

cd "$(dirname "$0")/.."
APP_DIR="$(pwd)"
PORT=3000
LOG="$APP_DIR/streamlit.log"

step() { printf '\n[%s] %s\n' "$(date +%H:%M:%S)" "$*"; }

step "1/6 실행 중인 앱 중지"
if pkill -f "streamlit run app.py"; then
    for _ in $(seq 20); do
        pgrep -f "streamlit run app.py" >/dev/null || break
        sleep 0.5
    done
    pkill -9 -f "streamlit run app.py" 2>/dev/null || true
    echo "중지했습니다."
else
    echo "실행 중인 앱이 없습니다."
fi

step "2/6 최신 코드 받기"
git pull --ff-only

step "3/6 Python 가상환경 확인"
if [ ! -x .venv/bin/python ]; then
    echo ".venv가 없어 새로 만듭니다."
    python3 -m venv .venv
fi
.venv/bin/python --version

step "4/6 라이브러리 설치 (이미 설치된 것은 건너뜀)"
.venv/bin/pip install -q -r requirements.txt

step "5/6 링크 미리보기 제목·설명 적용"
.venv/bin/python scripts/patch_index_html.py

if [ ! -f .env ]; then
    echo "주의: .env가 없어 AI 문장 기능이 꺼진 상태로 실행됩니다 (사용자 설명서 1-2 참고)."
fi

step "6/6 앱 실행"
nohup .venv/bin/streamlit run app.py > "$LOG" 2>&1 &
for _ in $(seq 60); do
    if curl -fs "http://localhost:$PORT/_stcore/health" >/dev/null 2>&1; then
        echo "실행 완료: http://localhost:$PORT (로그: $LOG)"
        exit 0
    fi
    sleep 0.5
done

echo "오류: 30초 안에 앱이 응답하지 않았습니다. 로그 마지막 부분:" >&2
tail -n 30 "$LOG" >&2
exit 1
