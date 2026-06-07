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


def test_suggest_cache_hit():
    """get_suggestions: 성공 결과는 TTL 내 캐시(2번째 호출은 suggest_topics 재호출 안 함)."""
    import orchestrator as orc
    srv._suggest_cache.update(at=0.0, data=None)   # 캐시 초기화
    calls = {"n": 0}
    real = orc.suggest_topics
    orc.suggest_topics = lambda n=6: (calls.__setitem__("n", calls["n"]+1) or
                                      {"topics": [{"title": "주제A", "why": "근거"}], "trends": [], "sources": []})
    try:
        r1 = srv.get_suggestions()
        r2 = srv.get_suggestions()
        assert calls["n"] == 1, f"캐시 미동작 — 호출 {calls['n']}회"
        assert r1["cached"] is False and r2["cached"] is True, (r1.get("cached"), r2.get("cached"))
        assert r2["topics"][0]["title"] == "주제A"
    finally:
        orc.suggest_topics = real
        srv._suggest_cache.update(at=0.0, data=None)
    print("PASS test_suggest_cache_hit")


def test_suggest_empty_not_cached():
    """빈 결과(키부재·실패)는 캐시하지 않아 다음 호출에서 재시도 가능."""
    import orchestrator as orc
    srv._suggest_cache.update(at=0.0, data=None)
    calls = {"n": 0}
    real = orc.suggest_topics
    orc.suggest_topics = lambda n=6: (calls.__setitem__("n", calls["n"]+1) or
                                      {"topics": [], "trends": [], "sources": []})
    try:
        srv.get_suggestions()
        srv.get_suggestions()
        assert calls["n"] == 2, f"빈결과가 캐시됨 — 재시도 안 됨(호출 {calls['n']}회)"
        assert srv._suggest_cache["data"] is None, "빈결과를 캐시하면 안 됨"
    finally:
        orc.suggest_topics = real
        srv._suggest_cache.update(at=0.0, data=None)
    print("PASS test_suggest_empty_not_cached")


def test_suggest_refresh_bypasses_cache():
    """refresh=True면 유효 캐시가 있어도 재생성."""
    import orchestrator as orc
    calls = {"n": 0}
    real = orc.suggest_topics
    orc.suggest_topics = lambda n=6: (calls.__setitem__("n", calls["n"]+1) or
                                      {"topics": [{"title": f"T{calls['n']}", "why": ""}], "trends": [], "sources": []})
    try:
        srv._suggest_cache.update(at=0.0, data=None)
        srv.get_suggestions()                 # 캐시 채움(호출1)
        r = srv.get_suggestions(refresh=True) # 캐시 무시 재생성(호출2)
        assert calls["n"] == 2, f"refresh가 캐시 우회 안 함(호출 {calls['n']}회)"
        assert r["cached"] is False
    finally:
        orc.suggest_topics = real
        srv._suggest_cache.update(at=0.0, data=None)
    print("PASS test_suggest_refresh_bypasses_cache")


if __name__ == "__main__":
    test_sse_format()
    test_load_samples()
    test_sse_format_queued()
    test_suggest_cache_hit()
    test_suggest_empty_not_cached()
    test_suggest_refresh_bypasses_cache()
    print("\n✅ ALL PASS (server: 6 tests)")
