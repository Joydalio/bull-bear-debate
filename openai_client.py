"""OpenAI(GPT) API 백엔드 — 사용자가 브라우저에서 입력한 API 키로 호출.

키는 디스크에 저장하지 않으며 Streamlit 세션 메모리에만 유지됨.
claude_cli.ask()와 동일한 반환 형식을 맞춰 debate_engine에 그대로 주입 가능.
Responses API 사용 — 리서치는 내장 web_search 도구.
"""

MODEL_FALLBACK = "gpt-5"

# $/MTok (입력, 출력)
PRICES = {
    "gpt-5.1": (1.25, 10.0),
    "gpt-5": (1.25, 10.0),
    "gpt-5-mini": (0.25, 2.0),
}


def _generate(api_key, model, system_prompt, user_prompt, timeout, tools=None):
    import openai

    client = openai.OpenAI(api_key=api_key, timeout=float(timeout), max_retries=1)
    kwargs = {}
    if system_prompt:
        kwargs["instructions"] = system_prompt
    if tools:
        kwargs["tools"] = tools
    resp = client.responses.create(model=model, input=user_prompt, **kwargs)
    text = resp.output_text
    if not text:
        raise RuntimeError(f"GPT 빈 응답 (model={model})")
    inp, out = PRICES.get(model, (0.0, 0.0))
    cost = (resp.usage.input_tokens * inp + resp.usage.output_tokens * out) / 1e6
    return text, cost


def _with_fallback(fn, model):
    try:
        return fn(model), model
    except Exception:
        if model == MODEL_FALLBACK:
            raise
        return fn(MODEL_FALLBACK), MODEL_FALLBACK


def ask(system_prompt, user_prompt, api_key, timeout=90, model=None):
    (text, cost), used = _with_fallback(
        lambda m: _generate(api_key, m, system_prompt, user_prompt, timeout),
        model or MODEL_FALLBACK,
    )
    return {"result": text, "total_cost_usd": cost, "model": used}


def research(ticker, api_key, timeout=300, model=None):
    """내장 웹검색 도구로 종목 정량 스크리닝 요약을 자동 생성."""
    from prompts import RESEARCH_PROMPT_TEMPLATE

    prompt = RESEARCH_PROMPT_TEMPLATE.format(ticker=ticker)
    (text, _), _ = _with_fallback(
        lambda m: _generate(api_key, m, None, prompt, timeout, tools=[{"type": "web_search"}]),
        model or MODEL_FALLBACK,
    )
    return text
