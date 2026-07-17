# ⚖️ bull-bear-debate

공매도(Bear) 에이전트와 가치투자(Bull) 에이전트가 종목을 두고 토론하고,
중립 심판이 **ORCA 점수**(O/R/C/A 각 0~2.5, 총 10점)로 판정하는 로컬 Streamlit 앱.

**두 가지 LLM 백엔드 지원** — 앱 화면에서 선택:

| 백엔드 | 준비물 | 과금 |
|---|---|---|
| **Claude (로컬 CLI)** | Claude Code CLI 설치 + 로그인 | 구독 기반, 추가 과금 없음 |
| **Gemini (API 키)** | [aistudio.google.com/apikey](https://aistudio.google.com/apikey)에서 키 발급 후 앱 화면에 입력 | API 사용량만큼 과금 (무료 티어 있음) |

- **컨텍스트 자동 생성**: 종목명만 넣으면 웹검색(Claude WebSearch / Gemini Google 검색)으로 정량 스크리닝 요약을 AI가 자동 작성 — 직접 붙여넣기도 가능
- Gemini API 키는 브라우저 세션에만 보관되며 디스크에 저장되지 않음
- macOS / Windows 지원, Python 3.9+ (3.11+ 권장)

## 전제조건

1. Python 3.9 이상 (3.11+ 권장)
2. **Claude 백엔드 사용 시**: [Claude Code CLI](https://claude.com/claude-code) 설치 및 로그인, 터미널에서 `claude --version` 동작 확인 (PATH 등록 필요)
3. **Gemini 백엔드 사용 시**: 별도 설치 불필요 — API 키만 발급받아 앱 화면에 입력

## 설치 및 실행 (원클릭)

[Code → Download ZIP](https://github.com/Joydalio/bull-bear-debate/archive/refs/heads/main.zip)으로 받아 압축을 풀거나 `git clone` 후:

- **Windows**: `run.bat` 더블클릭
- **macOS/Linux**: 터미널에서 `./run.sh`

가상환경 생성 → 패키지 설치 → 앱 실행 → 브라우저 자동 오픈까지 전부 자동입니다.
Python 3.9+만 설치되어 있으면 됩니다 (Windows는 [python.org](https://www.python.org/downloads/)에서 설치 시 **"Add Python to PATH" 체크 필수**).

<details>
<summary>수동 설치를 원하면</summary>

```bash
git clone https://github.com/Joydalio/bull-bear-debate.git
cd bull-bear-debate
python -m venv .venv
# macOS/Linux: source .venv/bin/activate | Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```
</details>

브라우저에서 `http://localhost:8501` 접속 후:

1. 사이드바에서 **LLM 백엔드 선택** (Claude 로컬 CLI 또는 Gemini API 키 입력)
2. **종목명 또는 상장사 종목코드**(예: `삼성전자` 또는 `005930`) 입력
3. **🔍 AI로 컨텍스트 자동 생성** 버튼 클릭 (또는 정량 스크리닝 요약을 직접 붙여넣기)
4. 라운드 수 선택(1~4, 기본 2) 후 **토론 시작**
5. 판정 후 **JSON / PDF 다운로드** 버튼으로 결과 저장

## 사용 모델

항상 최상위 모델 우선, 사용 불가 시 자동 폴백:

- Claude: `claude-fable-5` → `claude-opus-4-8`
- Gemini: `gemini-3-pro-preview` → `gemini-2.5-pro`

## 알려진 제약

- **로컬 전용** (localhost) — 서버 배포 불가. `claude` CLI 로그인 세션이 있는 머신에서만 동작
- 화면의 "명목 비용"은 CLI가 보고하는 참고 수치일 뿐, 구독 기반이므로 실제 청구 없음
- 인코딩은 utf-8(errors=replace)로 처리해 Windows cp949 환경에서도 한글 깨짐 방지
- PDF 한글 폰트: macOS(Arial Unicode) / Windows(맑은 고딕) 시스템 폰트 자동 사용
- 토론은 라운드당 수 분 소요 (2라운드 기준 CLI 호출 5회)

## 테스트

```bash
pip install pytest
pytest tests/ -v
```
