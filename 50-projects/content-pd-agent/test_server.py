#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""server.py 단위 — SSE 포맷·키 부재·폴백. 네트워크/모델 mock."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import server as srv


def test_sse_format():
    """sse_pack: 'event: X\\ndata: {json}\\n\\n' 포맷."""
    out = srv.sse_pack("step", {"stage": "creator", "retry": 0})
    assert out.startswith("event: step\n"), out
    assert "data: " in out and out.endswith("\n\n"), out
    import json
    body = out.split("data: ", 1)[1].rstrip()
    assert json.loads(body) == {"stage": "creator", "retry": 0}, body
    print("PASS test_sse_format")


def test_load_samples():
    """폴백 샘플 로더 — output의 CONTENT_*.md 파싱(존재분만)."""
    samples = srv.load_samples()
    assert isinstance(samples, list)
    for s in samples:
        assert "title" in s and "script" in s, s
    print(f"PASS test_load_samples ({len(samples)} samples)")


def test_sse_format_queued():
    """queued stage도 정상 직렬화."""
    out = srv.sse_pack("step", {"stage": "queued", "reason": "대기"})
    import json
    body = json.loads(out.split("data: ", 1)[1].rstrip())
    assert body["stage"] == "queued", body
    print("PASS test_sse_format_queued")


if __name__ == "__main__":
    test_sse_format()
    test_load_samples()
    test_sse_format_queued()
    print("\n✅ ALL PASS (server: 3 tests)")
