"""claude_api 백엔드 — mock anthropic SDK로 모델 전달·폴백·비용 검증."""
import sys
import types

import pytest


class _FakeResp:
    def __init__(self, text="응답", stop_reason="end_turn"):
        self.stop_reason = stop_reason
        self.content = [types.SimpleNamespace(type="text", text=text)]
        self.usage = types.SimpleNamespace(input_tokens=1000, output_tokens=2000)


@pytest.fixture
def fake_anthropic(monkeypatch):
    calls = []

    class _Messages:
        def create(self, **kw):
            calls.append(kw)
            fail = _Messages.fail_models
            if kw["model"] in fail:
                if fail[kw["model"]] == "refusal":
                    return _FakeResp(stop_reason="refusal")
                raise RuntimeError("api down")
            return _FakeResp()

    _Messages.fail_models = {}

    class _Client:
        def __init__(self, **kw):
            self.messages = _Messages()

    mod = types.SimpleNamespace(Anthropic=_Client)
    monkeypatch.setitem(sys.modules, "anthropic", mod)
    _Messages.calls = calls
    yield _Messages


def test_ask_uses_selected_model_and_computes_cost(fake_anthropic):
    import claude_api

    out = claude_api.ask("sys", "user", "key", model="claude-sonnet-5")
    assert fake_anthropic.calls[0]["model"] == "claude-sonnet-5"
    assert out["model"] == "claude-sonnet-5"
    # sonnet-5: 1000*$3/M + 2000*$15/M = 0.033
    assert out["total_cost_usd"] == pytest.approx(0.033)
    assert out["result"] == "응답"


def test_fallback_on_error(fake_anthropic):
    import claude_api

    fake_anthropic.fail_models = {"claude-fable-5": "error"}
    out = claude_api.ask("sys", "user", "key", model="claude-fable-5")
    assert out["model"] == "claude-opus-4-8"


def test_refusal_triggers_fallback(fake_anthropic):
    import claude_api

    fake_anthropic.fail_models = {"claude-fable-5": "refusal"}
    out = claude_api.ask("sys", "user", "key", model="claude-fable-5")
    assert out["model"] == "claude-opus-4-8"


def test_research_uses_web_search_tool(fake_anthropic):
    import claude_api

    text = claude_api.research("삼성전자", "key", model="claude-opus-4-8")
    assert text == "응답"
    tools = fake_anthropic.calls[0]["tools"]
    assert tools[0]["name"] == "web_search"
    assert "삼성전자" in fake_anthropic.calls[0]["messages"][0]["content"]
