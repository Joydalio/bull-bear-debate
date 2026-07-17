import pdf_export


def _sample():
    transcript = [
        {"role": "bear", "round": 1, "text": "하방 리스크: 마진 압박이 심각함. " * 30},
        {"role": "bull", "round": 1, "text": "경제적 해자가 견고함. " * 30},
        {"role": "bear", "round": 2, "text": "선반영 주장에 가격 근거가 없음."},
        {"role": "bull", "round": 2, "text": "FCF 창출력이 하방을 지지함."},
    ]
    verdict = {"O": 2.0, "R": 1.5, "C": 2.0, "A": 1.0, "total": 6.5,
               "verdict": "관망", "winner": "무승부",
               "key_reason": "양측 논거가 팽팽함",
               "invalidation": ["PER 30 초과 시", "FCF 적자 전환 시"]}
    return transcript, verdict


def test_build_pdf_returns_pdf_bytes():
    transcript, verdict = _sample()
    data = pdf_export.build_pdf("삼성전자(005930)", transcript, verdict, 0.53)
    assert data[:5] == b"%PDF-"
    assert len(data) > 2000


def test_build_pdf_parse_error_verdict():
    transcript, _ = _sample()
    data = pdf_export.build_pdf("T", transcript, {"parse_error": True, "raw": "심판 응답 원문"}, 0.1)
    assert data[:5] == b"%PDF-"
