"""토론 오케스트레이션: 라운드 진행 → 심판 판정."""
import json

import claude_cli
from prompts import (
    BEAR_SYSTEM_R1,
    BULL_SYSTEM_R1,
    BEAR_SYSTEM_REBUTTAL,
    BULL_SYSTEM_REBUTTAL,
    JUDGE_SYSTEM,
    ADVOCATE_SYSTEM,
    RANKING_JUDGE_SYSTEM,
)

R1_TIMEOUT = 180  # R1은 장문 생성
REBUTTAL_TIMEOUT = 90


def debate(ticker, context, rounds=2, on_message=None, ask_fn=None,
           r1_timeout=R1_TIMEOUT, rebuttal_timeout=REBUTTAL_TIMEOUT):
    ask_fn = ask_fn or claude_cli.ask  # 기본은 로컬 Claude CLI, Gemini 등 다른 백엔드 주입 가능
    transcript = []
    cost = 0.0
    bear_r1 = bull_r1 = last_bear = last_bull = ""

    for r in range(1, rounds + 1):
        for role in ("bear", "bull"):
            if r == 1:
                system = BEAR_SYSTEM_R1 if role == "bear" else BULL_SYSTEM_R1
                timeout = r1_timeout
                if role == "bear":
                    user = f"[대상 기업: {ticker}]\n컨텍스트:\n{context}"
                else:
                    user = (f"[대상 기업: {ticker}]\n컨텍스트:\n{context}"
                            f"\n\n=== Bear Case 전문 ===\n{bear_r1}")
            else:
                system = BEAR_SYSTEM_REBUTTAL if role == "bear" else BULL_SYSTEM_REBUTTAL
                timeout = rebuttal_timeout
                if role == "bear":
                    user = (f"[{ticker}] 직전 상대(Bull) 주장:\n{last_bull}"
                            f"\n\n본인의 R1 논지 요약:\n{bear_r1[:500]}")
                else:
                    user = (f"[{ticker}] 직전 상대(Bear) 주장:\n{last_bear}"
                            f"\n\n본인의 R1 논지 요약:\n{bull_r1[:500]}")

            resp = ask_fn(system, user, timeout=timeout)
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

    verdict, judge_cost = _judge(ticker, transcript, ask_fn, rebuttal_timeout)
    return {
        "transcript": transcript,
        "verdict": verdict,
        "notional_cost_usd": cost + judge_cost,
    }


def _ask_json(ask_fn, system, user, timeout):
    """JSON 응답 요청 — 백틱 제거 후 파싱, 실패 시 1회 재시도. (dict, cost) 반환."""
    cost = 0.0
    raw = ""
    for _ in range(2):
        resp = ask_fn(system, user, timeout=timeout)
        cost += resp.get("total_cost_usd") or 0.0
        raw = resp["result"].strip()
        cleaned = raw.replace("```json", "").replace("```", "").strip()
        try:
            return json.loads(cleaned), cost
        except json.JSONDecodeError:
            continue
    return {"parse_error": True, "raw": raw}, cost


def _judge(ticker, transcript, ask_fn, timeout=REBUTTAL_TIMEOUT):
    full = "\n\n".join(
        f"[라운드 {m['round']} — {m['role'].upper()}]\n{m['text']}" for m in transcript
    )
    return _ask_json(ask_fn, JUDGE_SYSTEM, f"[{ticker}] 토론 전문:\n{full}", timeout)


def tournament(tickers, rounds, ask_fn, research_fn, on_event=None,
               r1_timeout=R1_TIMEOUT, rebuttal_timeout=REBUTTAL_TIMEOUT):
    """종목별 토론 → 비교 변론 → 랭킹 심판. 한 종목 실패는 스킵하고 계속."""
    def emit(stage, ticker, detail=None):
        if on_event:
            on_event(stage, ticker, detail)

    contexts, results, failed = {}, {}, []
    cost = 0.0
    for t in tickers:
        try:
            emit("research", t)
            contexts[t] = research_fn(t)
            emit("debate", t)
            out = debate(t, contexts[t], rounds=rounds, ask_fn=ask_fn,
                         on_message=lambda role, r, text, _t=t: emit("debate", _t, (role, r, text)),
                         r1_timeout=r1_timeout, rebuttal_timeout=rebuttal_timeout)
            results[t] = out
            cost += out["notional_cost_usd"]
        except Exception:
            failed.append(t)  # 한 종목 실패가 전체를 죽이지 않음

    advocacy, ranking = {}, {}
    if len(results) >= 2:
        def _summary(t):
            v = results[t]["verdict"]
            return f"- {t}: 총점 {v.get('total')} / verdict {v.get('verdict')} / {v.get('key_reason', '')}"

        for t in results:
            rivals = "\n".join(_summary(x) for x in results if x != t)
            v = results[t]["verdict"]
            user = (f"[본인 종목: {t}]\n개별 판정: 총점 {v.get('total')}, verdict {v.get('verdict')}, "
                    f"핵심 근거: {v.get('key_reason', '')}\n\n경쟁 종목 판정 요약:\n{rivals}")
            emit("advocate", t)
            resp = ask_fn(ADVOCATE_SYSTEM, user, timeout=rebuttal_timeout)
            advocacy[t] = resp["result"]
            cost += resp.get("total_cost_usd") or 0.0

        emit("ranking", None)
        user = ("개별 판정 요약:\n" + "\n".join(_summary(t) for t in results)
                + "\n\n=== 종목별 비교 변론 ===\n"
                + "\n\n".join(f"[{t}]\n{advocacy[t]}" for t in advocacy))
        ranking, jcost = _ask_json(ask_fn, RANKING_JUDGE_SYSTEM, user, rebuttal_timeout)
        cost += jcost

    return {"type": "tournament", "tickers": list(tickers), "contexts": contexts,
            "results": results, "advocacy": advocacy, "ranking": ranking,
            "failed": failed, "notional_cost_usd": cost}
