# bull-bear-debate 설계 스펙

날짜: 2026-07-17
위치: `/Users/jun/bull-bear-debate` (독립 git 저장소)

## 개요

공매도(Bear) 에이전트와 가치투자(Bull) 에이전트가 종목을 두고 라운드제 토론을 벌이고,
중립 심판이 ORCA 점수(O/R/C/A 각 0~2.5, 총 10점)로 판정하는 로컬 전용 Streamlit 앱.

- 환경: **macOS + Windows 모두 지원** / Python 3.11+ / localhost 전용, 서버 배포 불가
- 코드 배포: https://github.com/Joydalio/bull-bear-debate 공개 저장소 — 누구나 clone해서 사용
- 핵심 제약: **Anthropic API 키를 절대 사용하지 않음.** 모든 LLM 호출은 로컬에 로그인된
  Claude Code CLI(`claude -p`)를 subprocess로 실행 (구독 기반, 추가 과금 없음)
- 모델: 항상 최상위 모델 사용 — `claude-fable-5` 우선, 사용 불가 시 `claude-opus-4-8`로 자동 폴백

## 파일 구조

```
bull-bear-debate/
├── app.py             # Streamlit UI
├── debate_engine.py   # 토론 오케스트레이션
├── claude_cli.py      # claude -p subprocess 래퍼
├── prompts.py         # 시스템 프롬프트 5종 (문구 수정 금지)
├── pdf_export.py      # 토론 전문 + 판정 결과 PDF 생성
├── requirements.txt   # streamlit, fpdf2
└── README.md          # 전제조건, 실행법, 제약
```

## claude_cli.py

- 모델 상수: `MODEL_PRIMARY = "claude-fable-5"`, `MODEL_FALLBACK = "claude-opus-4-8"`
- `ask(system_prompt, user_prompt, timeout=90) -> dict`
  - 명령: `["claude", "-p", user_prompt, "--system-prompt", system_prompt, "--output-format", "json", "--max-turns", "1", "--model", <모델>]`
  - 모델 선택: 최초 호출은 PRIMARY로 시도, 모델 관련 오류로 실패하면 FALLBACK으로 1회 재시도하고
    이후 호출은 모듈 레벨 캐시로 FALLBACK을 계속 사용 (매 호출 재시도 방지)
  - `subprocess.run(..., encoding="utf-8", errors="replace", shell=False, capture_output=True, timeout=timeout, env=env)`
  - env: `os.environ.copy()` 후 `ANTHROPIC_API_KEY` 제거 — API 과금 유출 원천 차단
  - stdout JSON에서 `result`, `total_cost_usd`, `is_error` 파싱
  - `is_error=True` 또는 `returncode != 0` → stderr 포함 `RuntimeError` 발생
- `preflight() -> str | None`
  - `claude --version` 실행. 실패 시 "claude login 필요 또는 PATH 미등록" 안내 문자열 반환, 성공 시 None
- `if __name__ == "__main__":` — "테스트 질문"으로 `ask()` 1회 호출해 응답 출력 (단독 실행 검수 겸 self-check)

## prompts.py

`BEAR_SYSTEM_R1`, `BULL_SYSTEM_R1`, `BEAR_SYSTEM_REBUTTAL`, `BULL_SYSTEM_REBUTTAL`, `JUDGE_SYSTEM`
5종 상수를 사용자 제공 원문 그대로 정의. 요약·수정 금지.

## debate_engine.py

- `debate(ticker, context, rounds=2, on_message=None) -> dict`
- 라운드별 시스템 프롬프트: r==1 → R1 프롬프트 / r>=2 → REBUTTAL 프롬프트
- user_prompt 구성:
  - R1 bear: `[대상 기업: {ticker}]\n컨텍스트:\n{context}`
  - R1 bull: R1 bear 입력 + `\n\n=== Bear Case 전문 ===\n{bear_r1_full}`
  - R2+ bear: `[{ticker}] 직전 상대(Bull) 주장:\n{last_bull}\n\n본인의 R1 논지 요약:\n{bear_r1[:500]}`
  - R2+ bull: `[{ticker}] 직전 상대(Bear) 주장:\n{last_bear}\n\n본인의 R1 논지 요약:\n{bull_r1[:500]}`
- timeout: R1은 180초, R2+는 90초
- `on_message(role, round, text)` 콜백을 각 발언 생성 직후 호출 (Streamlit 실시간 렌더링)
- 전 라운드 종료 후 심판 호출: 전 라운드 전문을 그대로 전달. 응답에서 백틱 제거 후
  `json.loads`, 실패 시 1회 재시도. 재시도도 실패하면 raw 텍스트를 담은 파싱 실패 표시 verdict 반환 (앱이 죽지 않게)
- 라운드 도중 `ask()` 예외(타임아웃 등)는 그대로 전파 → app.py에서 st.error 처리 (부분 결과를 조용히 감추지 않음)
- 반환: `{"transcript": [...], "verdict": {...}, "notional_cost_usd": 합산}`
  - transcript 항목: `{"role": "bear"|"bull", "round": int, "text": str}`

## pdf_export.py

- `build_pdf(ticker, transcript, verdict, notional_cost_usd) -> bytes`
- fpdf2 사용. 한글 지원을 위해 OS별 시스템 폰트 자동 탐색:
  - macOS: `/System/Library/Fonts/Supplemental/AppleGothic.ttf`
  - Windows: `C:/Windows/Fonts/malgun.ttf`
  - 둘 다 없으면 명확한 안내 메시지와 함께 예외 발생 (PDF 버튼에서 st.error로 표시)
- 구성: 표지(종목, 날짜, verdict/winner/total) → 라운드별 Bear/Bull 발언 전문 → ORCA 점수표 → invalidation 조건 → 명목 비용

## app.py

1. 사이드바: 종목명 **또는 상장사 종목코드**(예: 삼성전자 또는 005930) 입력, 라운드 수 슬라이더(1~4, 기본 2), 실행 버튼
   - 종목코드는 식별자로만 사용 (시세·재무 자동 조회는 범위 외 — 컨텍스트는 사용자가 붙여넣음)
2. 메인: 컨텍스트 `st.text_area` (placeholder: "정량 스크리닝 요약 붙여넣기 — 주가/PER/PSR/수급/오버행 등")
3. 시작 시 `preflight()` — 실패하면 `st.error` 안내 + 실행 버튼 비활성화
4. 진행 표시: `st.chat_message("bear"/"bull")` + on_message 콜백으로 라운드별 실시간 렌더링 (전체 완료 대기 금지)
5. R1 장문 발언: 앞 300자 미리보기 + `st.expander("전문 보기")`로 전문
6. 판정: ORCA 4축 `st.metric` 4개, verdict/winner 강조, invalidation 리스트 표시
7. 하단 캡션: 명목 비용 + "구독 기반이므로 실제 청구 없음"
8. 결과 다운로드 버튼 2개 — JSON(`{ticker}_{YYYYMMDD}.json`) + **PDF**(`{ticker}_{YYYYMMDD}.pdf`, pdf_export 사용)
9. 토론 실행 중 예외 → `st.error`로 표시하고 중단

## requirements.txt

`streamlit`, `fpdf2`. (LLM 호출은 subprocess이므로 anthropic SDK 불필요)

## README.md

- 전제조건: Claude Code CLI 설치·로그인(`claude login`), PATH 등록 (`claude --version`으로 확인)
- 설치: `git clone https://github.com/Joydalio/bull-bear-debate` → `pip install -r requirements.txt`
- 실행: `streamlit run app.py` (macOS/Windows 공통)
- 알려진 제약: 로컬 전용(localhost), 서버 배포 불가, Windows 인코딩은 utf-8/errors=replace로 처리

## 배포

- GitHub 공개 저장소 https://github.com/Joydalio/bull-bear-debate 에 push (사용자 승인 완료)

## 검수 기준 (구현 완료 전 직접 확인)

- [ ] 모든 파일 임포트 에러 없음
- [ ] `python claude_cli.py` 단독 실행 → "테스트 질문" 1회 호출 응답 출력
- [ ] 한글 컨텍스트 입력 시 인코딩 깨짐 없음
- [ ] ANTHROPIC_API_KEY를 임의 설정한 상태에서도 subprocess env에서 제거됨을 코드로 확인
- [ ] `debate()`를 mock 없이 rounds=2로 1회 실행해 R1/R2 프롬프트 분기 확인
- [ ] 모델 폴백: `claude-fable-5` 사용 가능 여부 실호출로 확인, 불가 시 `claude-opus-4-8` 폴백 작동 확인
- [ ] PDF 생성: 한글 transcript로 `build_pdf()` 실행해 깨짐 없는 PDF 바이트 생성 확인
- [ ] README에 전제조건, 설치·실행 명령, 알려진 제약 명시
- [ ] GitHub 저장소 push 완료 및 clone 가능 확인
