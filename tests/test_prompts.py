import prompts


def test_five_prompts_exist_and_intact():
    assert "숏셀러(공매도 투자자)입니다" in prompts.BEAR_SYSTEM_R1
    assert "Reverse DCF" in prompts.BEAR_SYSTEM_R1
    assert "매수(Long) 관점의 투자자입니다" in prompts.BULL_SYSTEM_R1
    assert "숨겨진 콜옵션" in prompts.BULL_SYSTEM_R1
    assert "가장 약한 고리 2개" in prompts.BEAR_SYSTEM_REBUTTAL
    assert "최대 800자" in prompts.BULL_SYSTEM_REBUTTAL
    assert '"verdict": "매수|관망|매도"' in prompts.JUDGE_SYSTEM
