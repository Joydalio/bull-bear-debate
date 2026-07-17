#!/bin/sh
# macOS/Linux 원클릭 실행: ./run.sh
cd "$(dirname "$0")"

if [ ! -d .venv ]; then
    echo "[1/3] 가상환경 생성 중..."
    python3 -m venv .venv || { echo "[오류] Python 3.9+ 를 먼저 설치하세요: https://www.python.org/downloads/"; exit 1; }
fi

echo "[2/3] 패키지 설치 확인 중..."
.venv/bin/pip install --quiet -r requirements.txt

# 최초 실행 시 뜨는 이메일 입력 프롬프트 건너뛰기
mkdir -p "$HOME/.streamlit"
[ -f "$HOME/.streamlit/credentials.toml" ] || printf '[general]\nemail = ""\n' > "$HOME/.streamlit/credentials.toml"

echo "[3/3] 앱 실행 — 브라우저가 자동으로 열립니다"
.venv/bin/python -m streamlit run app.py
