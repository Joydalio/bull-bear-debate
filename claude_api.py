"""Claude API 백엔드 — 사용자가 브라우저에서 입력한 API 키로 호출. 클라우드 배포용.

키는 디스크에 저장하지 않으며 Streamlit 세션 메모리에만 유지됨.
claude_cli.ask()와 동일한 반환 형식을 맞춰 debate_engine에 그대로 주입 가능.
CLI와 달리 API는 사용량만큼 실제 과금됨 — 비용은 usage 토큰으로 실측 계산.
"""

MODEL_FALLBACK = "claude-opus-4-8"

# $/MTok (입력, 출력)
PRICES = {
    "claude-fable-5": (10.0, 50.0),
    "claude-opus-4-8": (5.0, 25.0),
    "claude-sonnet-5": (3.0, 15.0),
}


def _generate(api_key, model, system_prompt, user_prompt, timeout, tools=None):
    import anthropic

    client = anthropic.Anthropic(api_key=api_key, timeout=float(timeout), max_retries=1)
    kwargs = {}
    if system_prompt:
        kwargs["system"] = system_prompt
    if tools:
        kwargs["tools"] = tools
    if not model.startswith("claude-fable"):
        kwargs["thinking"] = {"type": "adaptive"}  # fable-5는 항상 켜져 있어 파라미터 자체를 거부
    resp = client.messages.create(
        model=model,
        max_tokens=16000,
        messages=[{"role": "user", "content": user_prompt}],
        **kwargs,
    )
    if resp.stop_reason == "refusal":
        raise RuntimeError(f"Claude 안전 분류기 거부 (model={model})")
    text = "".join(b.text for b in resp.content if b.type == "text")
    if not text:
        raise RuntimeError(f"Claude 빈 응답 (model={model})")
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
    """서버측 웹검색 도구로 종목 정량 스크리닝 요약을 자동 생성."""
    from prompts import RESEARCH_PROMPT_TEMPLATE

    prompt = RESEARCH_PROMPT_TEMPLATE.format(ticker=ticker)
    tools = [{"type": "web_search_20250305", "name": "web_search", "max_uses": 3}]
    (text, _), _ = _with_fallback(
        lambda m: _generate(api_key, m, None, prompt, timeout, tools=tools),
        model or MODEL_FALLBACK,
    )
    return text
