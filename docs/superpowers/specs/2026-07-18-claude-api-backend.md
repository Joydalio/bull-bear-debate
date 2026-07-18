# Claude API 백엔드 — 폰 단독 사용 설계 스펙

날짜: 2026-07-18
목적: 노트북 없이 휴대폰만으로 Claude 백엔드를 쓸 수 있게 한다.

## 접근

`claude` CLI는 로컬 로그인 세션이 필요해 클라우드 배포가 불가능하다.
Gemini와 동일한 패턴의 **Claude API 키 백엔드**(`claude_api.py`)를 추가하면
앱 전체가 CLI 의존 없이 동작하므로 Streamlit Community Cloud에 배포해
휴대폰 브라우저만으로 사용할 수 있다.

## 설계

- `claude_api.py`: `gemini_client.py`와 동일한 인터페이스
  - `ask(system, user, api_key, timeout, model)` → `{result, total_cost_usd, is_error, model}`
  - `research(ticker, api_key, timeout, model)` → 요약 문자열 (서버측 `web_search` 도구 사용)
  - 폴백 체인: 선택 모델 실패 시 `claude-opus-4-8` 1회 재시도 (기존 패턴 재사용)
  - `stop_reason == "refusal"`(Fable 5 안전 분류기)은 실패로 간주 → 폴백
  - 비용: `usage` 토큰 × 모델 단가로 실측 계산 (CLI와 달리 API는 실제 과금)
- `app.py`: 백엔드 라디오에 "Claude (API 키)" 추가, 키 입력은 Gemini 패턴 재사용
- `requirements.txt`: `anthropic` 추가
- README: Streamlit Community Cloud 배포 절차 + API 과금 주의 문구

## 검수 기준

- [x] mock 테스트: 선택 모델 전달, 폴백 동작, refusal 폴백, 비용 계산
- [x] 기존 테스트 전체 통과 (회귀 없음)
- [ ] 실호출 1회 — 사용자 API 키 필요, 배포 후 확인 (요청 형식은 공식 API 문서 기준)
- [x] 앱 부팅 + 새 백엔드 옵션 UI 확인
- [ ] main 머지
