"""토론 오케스트레이션: 라운드 진행 → 심판 판정."""
import json

import claude_cli
from prompts import (
    BEAR_SYSTEM_R1,
    BULL_SYSTEM_R1,
    BEAR_SYSTEM_REBUTTAL,
    BULL_SYSTEM_REBUTTAL,
    JUDGE_SYSTEM,
)

R1_TIMEOUT = 180  # R1은 장문 생성
REBUTTAL_TIMEOUT = 90


def debate(ticker, context, rounds=2, on_message=None):
    transcript = []
    cost = 0.0
    bear_r1 = bull_r1 = last_bear = last_bull = ""

    for r in range(1, rounds + 1):
        for role in ("bear", "bull"):
            if r == 1:
                system = BEAR_SYSTEM_R1 if role == "bear" else BULL_SYSTEM_R1
                timeout = R1_TIMEOUT
                if role == "bear":
                    user = f"[대상 기업: {ticker}]\n컨텍스트:\n{context}"
                else:
                    user = (f"[대상 기업: {ticker}]\n컨텍스트:\n{context}"
                            f"\n\n=== Bear Case 전문 ===\n{bear_r1}")
            else:
                system = BEAR_SYSTEM_REBUTTAL if role == "bear" else BULL_SYSTEM_REBUTTAL
                timeout = REBUTTAL_TIMEOUT
                if role == "bear":
                    user = (f"[{ticker}] 직전 상대(Bull) 주장:\n{last_bull}"
                            f"\n\n본인의 R1 논지 요약:\n{bear_r1[:500]}")
                else:
                    user = (f"[{ticker}] 직전 상대(Bear) 주장:\n{last_bear}"
                            f"\n\n본인의 R1 논지 요약:\n{bull_r1[:500]}")

            resp = claude_cli.ask(system, user, timeout=timeout)
            text = resp["result"]
            cost += resp.get("total_cost_usd") or 0.0
            transcript.append({"role": role, "round": r, "text": text})

            if role == "bear":
                last_bear = text
                if r == 1:
                    bear_r1 = text
            else:
                last_bull = text
                if r == 1:
                    bull_r1 = text

            if on_message:
                on_message(role, r, text)

    verdict, judge_cost = _judge(ticker, transcript)
    return {
        "transcript": transcript,
        "verdict": verdict,
        "notional_cost_usd": cost + judge_cost,
    }


def _judge(ticker, transcript):
    full = "\n\n".join(
        f"[라운드 {m['round']} — {m['role'].upper()}]\n{m['text']}" for m in transcript
    )
    user = f"[{ticker}] 토론 전문:\n{full}"
    cost = 0.0
    raw = ""
    for _ in range(2):  # 파싱 실패 시 1회 재시도
        resp = claude_cli.ask(JUDGE_SYSTEM, user, timeout=REBUTTAL_TIMEOUT)
        cost += resp.get("total_cost_usd") or 0.0
        raw = resp["result"].strip()
        cleaned = raw.replace("```json", "").replace("```", "").strip()
        try:
            return json.loads(cleaned), cost
        except json.JSONDecodeError:
            continue
    return {"parse_error": True, "raw": raw}, cost
