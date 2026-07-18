# ⚖️ bull-bear-debate

공매도(Bear) 에이전트와 가치투자(Bull) 에이전트가 종목을 두고 토론하고,
중립 심판이 **ORCA 점수**(O/R/C/A 각 0~2.5, 총 10점)로 판정하는 로컬 Streamlit 앱.

**두 가지 LLM 백엔드 지원** — 앱 화면에서 선택:

| 백엔드 | 준비물 | 과금 |
|---|---|---|
| **Claude (로컬 CLI)** | Claude Code CLI 설치 + 로그인 | 구독 기반, 추가 과금 없음 |
| **Claude (API 키)** | [platform.claude.com](https://platform.claude.com/settings/keys)에서 키 발급 후 앱 화면에 입력 | API 사용량만큼 과금 |
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

### 토너먼트 모드 (다중 종목 비교)

종목을 2~5개 입력하면(줄바꿈/쉼표 구분) 종목별 토론 후 비교 변론과 랭킹 심판을 거쳐
매수 우선순위 TOP5를 정하고 최종 보고서를 만든다. 컨텍스트는 종목별로 자동 리서치된다.
5종목×2라운드 기준 약 30분 소요.

### 기타 옵션

- **모델 선택**: 사이드바에서 백엔드별 모델 선택 (기본값 = 최상위 모델)
- **고급 설정**: 라운드별 타임아웃 조정 (기본값이 최적값)
- **PDF 분량**: 전체 원문 또는 AI 요약 약 1~10장 선택
- **보고서 자동 저장**: 모든 결과가 `reports/`에 저장되며 사이드바에서 언제든 다시 열람

## 휴대폰에서 쓰기

앱을 PC에서 실행해 두면 **같은 Wi-Fi에 연결된 휴대폰**에서 바로 쓸 수 있다.

1. `run.sh` / `run.bat` 실행 시 터미널에 표시되는 **Network URL**(예: `http://192.168.0.10:8501`)을 휴대폰 브라우저에 입력
2. 좌상단 **≫** 버튼을 누르면 종목 입력·모델 선택 등 설정 패널이 열림
3. 토론·토너먼트는 수 분~30분 걸리므로 실행 중에는 휴대폰 화면이 꺼지지 않게 유지 (연결이 끊겨도 결과는 `reports/`에 자동 저장되어 "지난 보고서"에서 열람 가능)

집 밖에서도 쓰려면 PC와 휴대폰에 [Tailscale](https://tailscale.com)을 설치하고 Tailscale IP로 접속하면 된다 (포트 개방·설정 변경 불필요).

### 폰만으로 쓰기 — 노트북 없이 (클라우드 배포)

API 키 백엔드(Claude API 키 / Gemini API 키)는 로컬 CLI가 필요 없어서
무료 호스팅에 올려두면 **휴대폰 브라우저만으로** 쓸 수 있다:

1. 이 저장소를 본인 GitHub 계정으로 포크 (또는 그대로 사용)
2. [share.streamlit.io](https://share.streamlit.io) 로그인 → **Create app** → 저장소·브랜치(`main`)·파일(`app.py`) 지정 → Deploy
3. 발급된 `*.streamlit.app` 주소를 휴대폰 브라우저에서 열고 홈 화면에 추가
4. 앱에서 백엔드를 **Claude (API 키)** 로 선택하고 [platform.claude.com](https://platform.claude.com/settings/keys)에서 발급한 키 입력

주의: API 백엔드는 구독이 아니라 **사용량만큼 과금**된다 (5종목 토너먼트 1회 수 달러 수준,
화면의 명목 비용이 실제 청구액). 키는 세션 메모리에만 있으므로 접속할 때마다 입력한다.
Claude (로컬 CLI) 백엔드는 클라우드에서 동작하지 않는다 — 배포 앱에서는 API 키 백엔드만 사용.

## 사용 모델

항상 최상위 모델 우선, 사용 불가 시 자동 폴백:

- Claude: `claude-fable-5` → `claude-opus-4-8`
- Gemini: `gemini-3-pro-preview` → `gemini-2.5-pro`

## 알려진 제약

- **로컬 서버 전용** — 클라우드 배포 불가. `claude` CLI 로그인 세션이 있는 PC에서 실행해야 하며, 휴대폰 등 다른 기기는 같은 네트워크에서 브라우저로 접속
- 화면의 "명목 비용"은 CLI가 보고하는 참고 수치일 뿐, 구독 기반이므로 실제 청구 없음
- 인코딩은 utf-8(errors=replace)로 처리해 Windows cp949 환경에서도 한글 깨짐 방지
- PDF 한글 폰트: macOS(Arial Unicode) / Windows(맑은 고딕) 시스템 폰트 자동 사용
- 토론은 라운드당 수 분 소요 (2라운드 기준 CLI 호출 5회)

## 테스트

```bash
pip install pytest
pytest tests/ -v
```
