@echo off
chcp 65001 >nul
cd /d "%~dp0"

set PY=python
where python >nul 2>nul || set PY=py

if not exist .venv (
    echo [1/3] 가상환경 생성 중...
    %PY% -m venv .venv
    if errorlevel 1 (
        echo.
        echo [오류] Python이 설치되어 있지 않습니다.
        echo https://www.python.org/downloads/ 에서 설치 후 다시 실행하세요.
        echo 설치 화면에서 "Add Python to PATH" 체크 필수!
        pause
        exit /b 1
    )
)

echo [2/3] 패키지 설치 확인 중...
.venv\Scripts\python.exe -m pip install --quiet -r requirements.txt

rem 최초 실행 시 뜨는 이메일 입력 프롬프트 건너뛰기
if not exist "%USERPROFILE%\.streamlit\credentials.toml" (
    mkdir "%USERPROFILE%\.streamlit" 2>nul
    (echo [general]& echo email = "") > "%USERPROFILE%\.streamlit\credentials.toml"
)

echo [3/3] 앱 실행 — 브라우저가 자동으로 열립니다
echo       휴대폰에서 쓰려면: 같은 Wi-Fi에서 아래 "Network URL" 주소로 접속
.venv\Scripts\python.exe -m streamlit run app.py

pause
