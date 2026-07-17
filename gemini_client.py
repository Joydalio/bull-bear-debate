"""Gemini API 백엔드 — 사용자가 브라우저에서 입력한 API 키로 호출.

키는 디스크에 저장하지 않으며 Streamlit 세션 메모리에만 유지됨.
claude_cli.ask()와 동일한 반환 형식을 맞춰 debate_engine에 그대로 주입 가능.
"""

MODEL_PRIMARY = "gemini-3-pro-preview"
MODEL_FALLBACK = "gemini-2.5-pro"

_active_model = MODEL_PRIMARY


def _client(api_key):
    from google import genai

    return genai.Client(api_key=api_key)


def _generate(api_key, model, system_prompt, user_prompt, timeout, tools=None):
    from google.genai import types

    config = types.GenerateContentConfig(
        system_instruction=system_prompt or None,
        tools=tools,
        http_options=types.HttpOptions(timeout=int(timeout * 1000)),
    )
    resp = _client(api_key).models.generate_content(
        model=model, contents=user_prompt, config=config
    )
    text = resp.text
    if not text:
        raise RuntimeError(f"Gemini 빈 응답 (model={model})")
    return text


def _with_fallback(fn):
    global _active_model
    try:
        return fn(_active_model), _active_model
    except Exception:
        if _active_model != MODEL_PRIMARY:
            raise
        out = fn(MODEL_FALLBACK)
        _active_model = MODEL_FALLBACK  # 성공한 폴백 캐시
        return out, MODEL_FALLBACK


def ask(system_prompt, user_prompt, api_key, timeout=90):
    text, model = _with_fallback(
        lambda m: _generate(api_key, m, system_prompt, user_prompt, timeout)
    )
    # Gemini API는 응답에 비용을 포함하지 않음 — 명목 비용 0으로 처리
    return {"result": text, "total_cost_usd": 0.0, "is_error": False, "model": model}


def research(ticker, api_key, timeout=180):
    """Google 검색 그라운딩으로 종목 정량 스크리닝 요약을 자동 생성."""
    from google.genai import types

    from prompts import RESEARCH_PROMPT_TEMPLATE

    prompt = RESEARCH_PROMPT_TEMPLATE.format(ticker=ticker)
    tools = [types.Tool(google_search=types.GoogleSearch())]
    text, _ = _with_fallback(
        lambda m: _generate(api_key, m, None, prompt, timeout, tools=tools)
    )
    return text
