import datetime
import json

import streamlit as st

import claude_cli
import debate_engine
import pdf_export

st.set_page_config(page_title="Bull vs Bear Debate", page_icon="⚖️", layout="wide")
st.title("⚖️ Bull vs Bear Debate")

preflight_error = claude_cli.preflight()
if preflight_error:
    st.error(preflight_error)

with st.sidebar:
    ticker = st.text_input("종목명 또는 종목코드", placeholder="삼성전자 또는 005930")
    rounds = st.slider("라운드 수", 1, 4, 2)
    run = st.button(
        "토론 시작",
        type="primary",
        disabled=bool(preflight_error),
        use_container_width=True,
    )

context = st.text_area(
    "컨텍스트",
    height=220,
    placeholder="정량 스크리닝 요약 붙여넣기 — 주가/PER/PSR/수급/오버행 등",
)


def render_message(role, rnd, text):
    with st.chat_message(role, avatar="🐻" if role == "bear" else "🐮"):
        st.caption(f"라운드 {rnd} · {'Bear (공매도)' if role == 'bear' else 'Bull (매수)'}")
        if rnd == 1 and len(text) > 300:
            st.write(text[:300] + "…")
            with st.expander("전문 보기"):
                st.write(text)
        else:
            st.write(text)


just_ran = False
if run:
    if not ticker.strip() or not context.strip():
        st.warning("종목명(또는 종목코드)과 컨텍스트를 모두 입력하세요.")
    else:
        chat_area = st.container()

        def on_message(role, rnd, text):
            with chat_area:
                render_message(role, rnd, text)

        try:
            with st.spinner("토론 진행 중… (라운드당 1~3분 소요)"):
                result = debate_engine.debate(
                    ticker.strip(), context.strip(), rounds=rounds, on_message=on_message
                )
        except Exception as e:
            st.error(f"토론 중단: {e}")
            st.stop()
        st.session_state["result"] = result
        st.session_state["ticker"] = ticker.strip()
        just_ran = True

if "result" in st.session_state:
    result = st.session_state["result"]
    saved_ticker = st.session_state["ticker"]

    if not just_ran:  # 다운로드 버튼 클릭 등 rerun 시 기록에서 다시 그림
        for m in result["transcript"]:
            render_message(m["role"], m["round"], m["text"])

    st.divider()
    st.subheader("🧑‍⚖️ 심판 판정")
    verdict = result["verdict"]
    if verdict.get("parse_error"):
        st.error("심판 응답 JSON 파싱 실패 — 원문:")
        st.code(verdict.get("raw", ""))
    else:
        cols = st.columns(4)
        for col, axis in zip(cols, ["O", "R", "C", "A"]):
            col.metric(axis, f"{verdict.get(axis, '?')} / 2.5")
        v_col, w_col, t_col = st.columns(3)
        v_col.metric("Verdict", verdict.get("verdict", "?"))
        w_col.metric("Winner", verdict.get("winner", "?"))
        t_col.metric("Total", f"{verdict.get('total', '?')} / 10")
        st.markdown(f"**핵심 근거:** {verdict.get('key_reason', '')}")
        inv = verdict.get("invalidation") or []
        if inv:
            st.markdown("**무효화(반증) 조건:**")
            for item in inv:
                st.markdown(f"- {item}")

    date_str = datetime.date.today().strftime("%Y%m%d")
    dl_json, dl_pdf = st.columns(2)
    dl_json.download_button(
        "📄 JSON 다운로드",
        data=json.dumps(result, ensure_ascii=False, indent=2),
        file_name=f"{saved_ticker}_{date_str}.json",
        mime="application/json",
        use_container_width=True,
    )
    try:
        pdf_bytes = pdf_export.build_pdf(
            saved_ticker, result["transcript"], verdict, result["notional_cost_usd"]
        )
        dl_pdf.download_button(
            "📑 PDF 다운로드",
            data=pdf_bytes,
            file_name=f"{saved_ticker}_{date_str}.pdf",
            mime="application/pdf",
            use_container_width=True,
        )
    except RuntimeError as e:
        dl_pdf.error(str(e))

    st.caption(
        f"명목 비용: ${result['notional_cost_usd']:.4f} — 구독 기반이므로 실제 청구 없음"
    )
