"""openai_client 백엔드 — mock openai SDK로 모델 전달·폴백·비용 검증."""
import sys
import types

import pytest


class _FakeResp:
    def __init__(self, text="응답"):
        self.output_text = text
        self.usage = types.SimpleNamespace(input_tokens=1000, output_tokens=2000)


@pytest.fixture
def fake_openai(monkeypatch):
    calls = []

    class _Responses:
        fail_models = {}

        def create(self, **kw):
            calls.append(kw)
            if kw["model"] in _Responses.fail_models:
                raise RuntimeError("api down")
            return _FakeResp()

    class _Client:
        def __init__(self, **kw):
            self.responses = _Responses()

    monkeypatch.setitem(sys.modules, "openai", types.SimpleNamespace(OpenAI=_Client))
    _Responses.calls = calls
    yield _Responses


def test_ask_uses_selected_model_and_computes_cost(fake_openai):
    import openai_client

    out = openai_client.ask("sys", "user", "key", model="gpt-5.1")
    assert fake_openai.calls[0]["model"] == "gpt-5.1"
    assert fake_openai.calls[0]["instructions"] == "sys"
    assert out["model"] == "gpt-5.1"
    # gpt-5.1: 1000*$1.25/M + 2000*$10/M = 0.02125
    assert out["total_cost_usd"] == pytest.approx(0.02125)
    assert out["result"] == "응답"


def test_fallback_on_error(fake_openai):
    import openai_client

    fake_openai.fail_models = {"gpt-5.1": True}
    out = openai_client.ask("sys", "user", "key", model="gpt-5.1")
    assert out["model"] == "gpt-5"
    fake_openai.fail_models = {}


def test_research_uses_web_search_tool(fake_openai):
    import openai_client

    text = openai_client.research("삼성전자", "key", model="gpt-5")
    assert text == "응답"
    assert fake_openai.calls[0]["tools"] == [{"type": "web_search"}]
    assert "삼성전자" in fake_openai.calls[0]["input"]
