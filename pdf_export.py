"""토론 결과 → PDF bytes. 한글은 OS 시스템 폰트로 렌더링."""
import datetime
from pathlib import Path

from fpdf import FPDF

FONT_CANDIDATES = [
    # macOS — AppleGothic.ttf는 OS/2 테이블이 없어 fpdf2가 로드 불가, Arial Unicode 사용
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    "C:/Windows/Fonts/malgun.ttf",                          # Windows 맑은 고딕
    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",      # Linux(참고)
]

ROLE_LABEL = {"bear": "Bear (공매도)", "bull": "Bull (매수)"}


def _mc(pdf, w, h, text):
    # multi_cell 기본값이 커서를 오른쪽 끝에 두어 다음 셀 폭이 0이 되는 것 방지
    pdf.multi_cell(w, h, text, new_x="LMARGIN", new_y="NEXT")


def _find_font():
    for p in FONT_CANDIDATES:
        if Path(p).exists():
            return p
    raise RuntimeError(
        "한글 폰트를 찾을 수 없음 — macOS(Arial Unicode) 또는 Windows(맑은 고딕) 환경에서 실행하세요."
    )


def _new_pdf():
    pdf = FPDF()
    pdf.add_font("kr", "", _find_font())
    pdf.set_auto_page_break(True, margin=15)
    pdf.add_page()
    return pdf


def build_text_pdf(title, text):
    """요약 보고서 등 단일 텍스트 PDF."""
    pdf = _new_pdf()
    pdf.set_font("kr", size=18)
    _mc(pdf, 0, 10, title)
    pdf.set_font("kr", size=10)
    _mc(pdf, 0, 6, f"생성일: {datetime.date.today().isoformat()}")
    pdf.ln(4)
    pdf.set_font("kr", size=10.5)
    _mc(pdf, 0, 5.5, text)
    return bytes(pdf.output())


def build_tournament_pdf(data):
    """토너먼트 최종 보고서: 랭킹 → 종목별 판정 요약 → 변론 전문."""
    pdf = _new_pdf()
    pdf.set_font("kr", size=18)
    _mc(pdf, 0, 10, "종목 토너먼트 최종 보고서 — TOP" + str(len(data.get("results", {}))))
    pdf.set_font("kr", size=10)
    _mc(pdf, 0, 6, f"생성일: {datetime.date.today().isoformat()}   대상: {', '.join(data.get('tickers', []))}")
    if data.get("failed"):
        _mc(pdf, 0, 6, f"실패(제외): {', '.join(data['failed'])}")
    pdf.ln(4)

    ranking = data.get("ranking") or {}
    pdf.set_font("kr", size=14)
    _mc(pdf, 0, 8, "최종 순위")
    pdf.set_font("kr", size=11)
    if ranking.get("parse_error"):
        _mc(pdf, 0, 6, "랭킹 파싱 실패 — 원문:")
        _mc(pdf, 0, 6, str(ranking.get("raw", "")))
    else:
        for row in ranking.get("ranking", []):
            t = row.get("ticker", "?")
            total = (data["results"].get(t, {}).get("verdict") or {}).get("total", "?")
            _mc(pdf, 0, 6, f"{row.get('rank')}. {t}  (ORCA {total}/10) — {row.get('reason', '')}")
        if ranking.get("portfolio_comment"):
            pdf.ln(2)
            _mc(pdf, 0, 6, f"포트폴리오 코멘트: {ranking['portfolio_comment']}")
    pdf.ln(4)

    pdf.set_font("kr", size=14)
    _mc(pdf, 0, 8, "종목별 판정 요약")
    for t, res in data.get("results", {}).items():
        v = res.get("verdict") or {}
        pdf.set_font("kr", size=12)
        _mc(pdf, 0, 7, f"■ {t}")
        pdf.set_font("kr", size=10)
        _mc(pdf, 0, 5.5, f"Verdict: {v.get('verdict')} / Winner: {v.get('winner')} / Total: {v.get('total')}")
        _mc(pdf, 0, 5.5, f"핵심 근거: {v.get('key_reason', '')}")
        for item in v.get("invalidation") or []:
            _mc(pdf, 0, 5.5, f"  - 무효화: {item}")
        pdf.ln(2)

    if data.get("advocacy"):
        pdf.set_font("kr", size=14)
        _mc(pdf, 0, 8, "비교 변론 전문")
        for t, speech in data["advocacy"].items():
            pdf.set_font("kr", size=12)
            _mc(pdf, 0, 7, f"[{t}]")
            pdf.set_font("kr", size=10)
            _mc(pdf, 0, 5.5, speech)
            pdf.ln(2)

    pdf.set_font("kr", size=9)
    _mc(pdf, 0, 5, f"명목 비용: ${data.get('notional_cost_usd', 0):.4f} (구독 기반이므로 실제 청구 없음)")
    return bytes(pdf.output())


def build_pdf(ticker, transcript, verdict, notional_cost_usd):
    pdf = _new_pdf()

    # 표지/헤더
    pdf.set_font("kr", size=18)
    _mc(pdf, 0, 10, f"Bull vs Bear 토론 리포트 — {ticker}")
    pdf.set_font("kr", size=10)
    _mc(pdf, 0, 6, f"생성일: {datetime.date.today().isoformat()}")
    pdf.ln(4)

    # 판정 요약
    pdf.set_font("kr", size=14)
    _mc(pdf, 0, 8, "판정 결과")
    pdf.set_font("kr", size=11)
    if verdict.get("parse_error"):
        _mc(pdf, 0, 6, "심판 JSON 파싱 실패 — 원문:")
        _mc(pdf, 0, 6, str(verdict.get("raw", "")))
    else:
        _mc(pdf, 0, 6, f"Verdict: {verdict.get('verdict')}   Winner: {verdict.get('winner')}")
        _mc(pdf, 
            0, 6,
            f"ORCA — O: {verdict.get('O')}  R: {verdict.get('R')}  "
            f"C: {verdict.get('C')}  A: {verdict.get('A')}  /  Total: {verdict.get('total')}",
        )
        _mc(pdf, 0, 6, f"핵심 근거: {verdict.get('key_reason', '')}")
        inv = verdict.get("invalidation") or []
        if inv:
            _mc(pdf, 0, 6, "무효화(반증) 조건:")
            for item in inv:
                _mc(pdf, 0, 6, f"  - {item}")
    pdf.ln(4)

    # 토론 전문
    pdf.set_font("kr", size=14)
    _mc(pdf, 0, 8, "토론 전문")
    for m in transcript:
        pdf.set_font("kr", size=12)
        _mc(pdf, 0, 7, f"[라운드 {m['round']}] {ROLE_LABEL.get(m['role'], m['role'])}")
        pdf.set_font("kr", size=10)
        _mc(pdf, 0, 5.5, m["text"])
        pdf.ln(3)

    pdf.set_font("kr", size=9)
    _mc(pdf, 0, 5, f"명목 비용: ${notional_cost_usd:.4f} (구독 기반이므로 실제 청구 없음)")
    return bytes(pdf.output())
