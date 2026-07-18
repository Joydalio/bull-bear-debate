# 멀티 종목 토너먼트 모드 설계 스펙

날짜: 2026-07-17
기반: 기존 bull-bear-debate 단일 종목 토론 앱

## 개요

최대 5개 종목을 입력하면 종목별 Bear/Bull 토론 후, 종목 간 비교 변론과 랭킹 심판을 거쳐
TOP5 우선순위와 최종 보고서를 생성한다.

## 1. 입력

- 사이드바 종목 입력을 여러 줄 `st.text_area`로 변경. 줄바꿈/쉼표 구분, 최대 5개 (초과분 무시 + 경고)
- 1개 입력 시 기존 단일 모드와 동일하게 동작, 2개 이상이면 토너먼트 모드 자동 전환
- **LLM 모델 선택 메뉴** (신규): 백엔드별 selectbox, 기본값은 최상위 모델
  - Claude: `claude-fable-5`(기본) / `claude-opus-4-8` / `claude-sonnet-5`
  - Gemini: `gemini-3-pro-preview`(기본) / `gemini-2.5-pro` / `gemini-2.5-flash`
  - 선택한 모델이 1순위로 사용되고, 실패 시 기존 폴백 체인 유지 (Claude→opus-4-8, Gemini→2.5-pro)
- **라운드별 타임아웃 설정** (신규): 사이드바 "고급 설정" expander 안 슬라이더 2개
  - R1(장문) 타임아웃: 60~600초, 기본 180초 (현재 최적값)
  - 반박(R2+)·심판 타임아웃: 30~300초, 기본 90초 (현재 최적값)
  - `debate()`에 `r1_timeout` / `rebuttal_timeout` 매개변수로 전달 (기본값 = 기존 상수)

## 2. 컨텍스트

- 토너먼트 모드: 종목별 컨텍스트를 자동 리서치로 통일 (기존 `research_fn` 재사용, 종목당 웹검색 1회)
- 단일 모드: 기존 수동 붙여넣기 + 자동 생성 버튼 유지

## 3. 토너먼트 흐름 (`debate_engine.tournament()`)

```
1. 종목별 순차 진행: research(ticker) → debate(ticker, context, rounds, ...) 기존 그대로
2. 비교 변론: 각 종목 대표(Bull)가 1회씩 발언 — "왜 내 종목이 경쟁 종목보다 우선 매수인가"
   입력: 자기 종목 verdict + key_reason + 경쟁 종목들의 (ticker, total, verdict, key_reason) 요약
   길이: 최대 800자
3. 랭킹 심판: 개별 ORCA 결과 + 전체 변론을 읽고 JSON 판정 (백틱 제거 후 파싱, 실패 시 1회 재시도)
   {"ranking": [{"rank": 1, "ticker": "...", "reason": "1문장"}, ...], "portfolio_comment": "1~2문장"}
```

- 새 프롬프트 2종 `ADVOCATE_SYSTEM`, `RANKING_JUDGE_SYSTEM`을 prompts.py에 추가 (자유 작성 가능)
- 콜백 `on_event(stage, ticker, detail)`로 진행 상황 전달 (stage: research/debate/advocate/ranking)
- 5종목×2라운드 기준 총 호출 약 31회, 예상 30분 — 실행 전 UI에 예상 시간 표시

## 4. 에러 처리

- 특정 종목의 리서치/토론 실패 시 해당 종목만 제외하고 계속 진행, 결과에 `failed: [종목명]` 기록
- 남은 종목이 1개 이하면 비교 변론·랭킹 생략하고 개별 결과만 반환

## 5. 결과 화면

- 순위표: 1~5위 카드 (종목명, ORCA 총점, verdict, 선정 이유) — 기존 피그마 스타일 스탯 카드 재사용
- portfolio_comment 표시
- 종목별 개별 토론 전문 + 개별 ORCA는 종목별 expander로 접어서 표시
- 진행 표시: "[2/5] SK하이닉스 · 라운드 1 · 🐻 Bear 생성 중…"

## 6. 저장/보고서

- 전체 결과를 `reports/TOP5_{YYYYMMDD_HHMMSS}.json` 하나로 자동 저장
  - 포맷: `{"type": "tournament", "tickers": [...], "results": {ticker: 개별 debate 결과},
    "advocacy": {ticker: 변론}, "ranking": {...}, "failed": [...], "notional_cost_usd": 합산}`
  - 단일 모드 저장 포맷에는 `"type": "single"` 필드 추가 (기존 파일은 type 부재 = single로 간주)
- "지난 보고서" 뷰어가 type을 보고 단일/토너먼트 렌더 분기
- PDF: `pdf_export.build_tournament_pdf()` — 랭킹표 → portfolio_comment → 종목별 판정 요약 → 변론 전문
- JSON/PDF 다운로드 버튼 (파일명 `TOP5_{YYYYMMDD}.json/pdf`)
- **PDF 분량 옵션** (신규, 단일/토너먼트 공통):
  - selectbox: "전체(원문)" 기본 + "요약 약 1장" ~ "요약 약 10장"
  - 전체: 기존처럼 즉시 다운로드
  - 요약 N장: "요약 PDF 생성" 버튼 → LLM이 보고서 전문을 약 N×1,800자 한국어 보고서로 재작성
    (구조: 결론/랭킹 → 핵심 근거 → 리스크 → 무효화 조건, 수치 보존) → 다운로드 버튼 표시
  - 새 프롬프트 `SUMMARY_SYSTEM_TEMPLATE`을 prompts.py에 추가 (자유 작성 가능)
  - 글자수 기반 근사치이므로 UI에 "약 N장" 표기

## 검수 기준

- [x] 단일 종목 입력 시 기존 동작과 완전 동일 (회귀 없음, 기존 테스트 통과)
- [x] tournament() 단위 테스트: mock ask_fn으로 2종목 흐름(개별→변론→랭킹), 1종목 실패 시 스킵 동작
- [x] 모델 선택: 선택 모델이 CLI/API 호출에 실제 반영되는지 (mock으로 cmd/model 인자 검증)
- [x] 타임아웃 슬라이더 값이 debate()에 전달되는지
- [x] 랭킹 JSON 파싱 실패 시 재시도 및 raw 반환
- [x] 토너먼트 PDF 한글 생성
- [x] PDF 분량 옵션: mock ask_fn으로 목표 글자수가 프롬프트에 반영되는지, 요약 PDF 바이트 생성 확인
- [x] 실전 검수: 2종목×1라운드 실호출 1회 (전체 흐름 end-to-end)
- [x] README 갱신 + GitHub push
