# ⚖️ bull-bear-debate

공매도(Bear) 에이전트와 가치투자(Bull) 에이전트가 종목을 두고 토론하고,
중립 심판이 **ORCA 점수**(O/R/C/A 각 0~2.5, 총 10점)로 판정하는 로컬 Streamlit 앱.

- **API 키 불필요·추가 과금 없음** — 모든 LLM 호출은 로컬에 로그인된 Claude Code CLI(`claude -p`)를 통해 구독 세션으로 처리
- macOS / Windows 지원, Python 3.9+ (3.11+ 권장)

## 전제조건

1. [Claude Code CLI](https://claude.com/claude-code) 설치 및 로그인 (`claude login` 또는 앱 최초 실행 시 로그인)
2. 터미널에서 `claude --version`이 동작하는지 확인 (PATH 등록 필요)
3. Python 3.9 이상 (3.11+ 권장)

## 설치

```bash
git clone https://github.com/Joydalio/bull-bear-debate.git
cd bull-bear-debate
python -m venv .venv
# macOS/Linux
source .venv/bin/activate
# Windows
# .venv\Scripts\activate
pip install -r requirements.txt
```

## 실행

```bash
streamlit run app.py
```

브라우저에서 `http://localhost:8501` 접속 후:

1. 사이드바에 **종목명 또는 상장사 종목코드**(예: `삼성전자` 또는 `005930`) 입력
2. 메인 영역에 정량 스크리닝 요약(주가/PER/PSR/수급/오버행 등) 붙여넣기
3. 라운드 수 선택(1~4, 기본 2) 후 **토론 시작**
4. 판정 후 **JSON / PDF 다운로드** 버튼으로 결과 저장

## 사용 모델

항상 최상위 모델을 사용: `claude-fable-5` 우선, 사용 불가 시 `claude-opus-4-8`로 자동 폴백.

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
