#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""server.py 단위 — SSE 포맷·키 부재·폴백·동시성 직렬화(502 회귀 방지). 네트워크/모델 mock."""
import sys, time
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


def test_suggest_serialized_under_run_lock():
    """502 회귀 방지: suggest는 _run_lock으로 직렬화 — 모델 호출 중 락을 잡는다.
    /api/pd가 락을 점유 중이면 suggest는 블로킹하지 않고 캐시/빈결과로 폴백(busy)."""
    import orchestrator as orc
    srv._suggest_cache.update(at=0.0, data=None)
    # 락이 suggest_topics 실행 시점에 잡혀 있는지 검사
    held = {"locked": None}
    real = orc.suggest_topics
    orc.suggest_topics = lambda n=6: (held.__setitem__("locked", srv._run_lock.locked()) or
                                      {"topics": [{"title": "T", "why": ""}], "trends": [], "sources": []})
    try:
        srv.get_suggestions()
        assert held["locked"] is True, "suggest_topics 실행 중 _run_lock이 안 잡힘(직렬화 깨짐)"
        assert not srv._run_lock.locked(), "suggest 후 _run_lock 해제 안 됨(누수)"
    finally:
        orc.suggest_topics = real
        srv._suggest_cache.update(at=0.0, data=None)
    print("PASS test_suggest_serialized_under_run_lock")


def test_suggest_busy_fallback_no_block():
    """다른 요청이 _run_lock 점유 중이면 suggest는 막히지 않고 즉시 폴백(busy)."""
    import orchestrator as orc
    srv._suggest_cache.update(at=0.0, data=None)
    called = {"n": 0}
    real = orc.suggest_topics
    orc.suggest_topics = lambda n=6: (called.__setitem__("n", called["n"]+1) or {"topics": [], "trends": [], "sources": []})
    srv._run_lock.acquire()                      # /api/pd가 점유 중인 상황 모사
    try:
        t0 = time.monotonic()
        r = srv.get_suggestions()
        dt = time.monotonic() - t0
        assert r.get("busy") is True, f"busy 폴백 안 함: {r}"
        assert called["n"] == 0, "락 점유 중인데 suggest_topics를 호출함(블로킹/직렬화 위반)"
        assert dt < 4, f"폴백이 너무 오래 걸림({dt:.1f}s) — 블로킹 의심"
    finally:
        srv._run_lock.release()
        orc.suggest_topics = real
        srv._suggest_cache.update(at=0.0, data=None)
    print("PASS test_suggest_busy_fallback_no_block")


def test_suggest_busy_returns_stale_cache():
    """락 점유 중이고 만료 캐시가 있으면, 빈손 대신 가진 캐시라도 반환(UX 보존)."""
    import orchestrator as orc
    srv._suggest_cache.update(at=1.0, data={"topics": [{"title": "캐시주제", "why": ""}], "trends": [], "sources": []})
    real = orc.suggest_topics
    orc.suggest_topics = lambda n=6: {"topics": [{"title": "새로생성"}], "trends": [], "sources": []}
    srv._run_lock.acquire()
    try:
        r = srv.get_suggestions()
        assert r.get("busy") is True and r["topics"][0]["title"] == "캐시주제", r
    finally:
        srv._run_lock.release()
        orc.suggest_topics = real
        srv._suggest_cache.update(at=0.0, data=None)
    print("PASS test_suggest_busy_returns_stale_cache")


# ── /api/gamma 프록시 (Handler를 소켓 없이 구동 — _send 캡처) ──────────
class _CapHandler(srv.Handler):
    """do_GET을 네트워크 없이 구동: __init__ 우회 + _send 캡처."""
    def __init__(self, path):
        self.path = path
        self.captured = {}
    def _send(self, code, ctype, body):
        self.captured = {"code": code, "ctype": ctype, "body": body}


def _gamma_get(path):
    h = _CapHandler(path)
    h.do_GET()
    import json
    return json.loads(h.captured["body"].decode("utf-8"))


def test_api_gamma_proxies_status():
    """/api/gamma?id=X → orc.gamma_status(X) 위임 + JSON 반환."""
    import orchestrator as orc
    real = orc.gamma_status
    seen = {}
    orc.gamma_status = lambda gid: (seen.__setitem__("id", gid) or
                                    {"status": "completed", "pdf_url": "https://x/AI.pdf"})
    try:
        d = _gamma_get("/api/gamma?id=abc123XYZ")
        assert seen["id"] == "abc123XYZ", seen
        assert d["status"] == "completed" and d["pdf_url"] == "https://x/AI.pdf", d
    finally:
        orc.gamma_status = real
    print("PASS test_api_gamma_proxies_status")


def test_api_gamma_graceful_on_exception():
    """gamma_status가 예외를 던져도 프록시는 {status:failed}로 graceful(프론트 폴링 보호)."""
    import orchestrator as orc
    real = orc.gamma_status
    def boom(gid): raise RuntimeError("내부 폭발")
    orc.gamma_status = boom
    try:
        d = _gamma_get("/api/gamma?id=abc123")
        assert d["status"] == "failed" and "폭발" in d["error"], d
    finally:
        orc.gamma_status = real
    print("PASS test_api_gamma_graceful_on_exception")


def test_api_gamma_missing_id():
    """id 없으면 빈 문자열로 위임 → gamma_status가 자체 검증(failed)."""
    import orchestrator as orc
    real = orc.gamma_status
    orc.gamma_status = lambda gid: {"status": "failed", "error": "잘못된 generation id"} if not gid else {"status": "completed"}
    try:
        d = _gamma_get("/api/gamma")
        assert d["status"] == "failed", d
    finally:
        orc.gamma_status = real
    print("PASS test_api_gamma_missing_id")


# ── /api/thumbnail 프록시 (POST 구동 — rfile/headers 페이크) ──────────
import io as _io, json as _json


class _CapPostHandler(srv.Handler):
    """do_POST를 네트워크 없이 구동: rfile(BytesIO)+headers 페이크 + _send 캡처."""
    def __init__(self, path, body_bytes):
        self.path = path
        self.rfile = _io.BytesIO(body_bytes)
        self.headers = {"Content-Length": str(len(body_bytes))}
        self.captured = {}
    def _send(self, code, ctype, body):
        self.captured = {"code": code, "ctype": ctype, "body": body}


def _thumb_post(prompt_obj):
    body = _json.dumps(prompt_obj).encode("utf-8")
    h = _CapPostHandler("/api/thumbnail", body)
    h.do_POST()
    return h.captured["code"], _json.loads(h.captured["body"].decode("utf-8")) if h.captured["body"] else {}


def test_thumbnail_empty_prompt_400():
    """prompt 없으면 400."""
    code, _ = _thumb_post({})
    assert code == 400, code
    print("PASS test_thumbnail_empty_prompt_400")


def test_thumbnail_ok_and_failed():
    """generate_thumbnail 반환에 따라 ok/failed."""
    import orchestrator as orc
    real = orc.generate_thumbnail
    srv._thumb_cache.clear()
    orc.generate_thumbnail = lambda p: "data:image/png;base64,OK1"
    try:
        code, d = _thumb_post({"prompt": "a cat playing"})
        assert code == 200 and d["status"] == "ok" and d["image"].endswith("OK1"), d
    finally:
        orc.generate_thumbnail = real
    srv._thumb_cache.clear()
    orc.generate_thumbnail = lambda p: None
    try:
        code, d = _thumb_post({"prompt": "another unique prompt"})
        assert code == 200 and d["status"] == "failed", d
    finally:
        orc.generate_thumbnail = real
    print("PASS test_thumbnail_ok_and_failed")


def test_thumbnail_cache_hit_no_regenerate():
    """동일 prompt 2회 호출 시 2번째는 캐시 — generate_thumbnail 미호출."""
    import orchestrator as orc
    real = orc.generate_thumbnail
    srv._thumb_cache.clear()
    calls = {"n": 0}
    def counted(p):
        calls["n"] += 1
        return "data:image/png;base64,C%d" % calls["n"]
    orc.generate_thumbnail = counted
    try:
        c1, d1 = _thumb_post({"prompt": "동일 프롬프트 cache test"})
        c2, d2 = _thumb_post({"prompt": "동일 프롬프트 cache test"})
        assert d1["status"] == "ok" and d2["status"] == "ok", (d1, d2)
        assert d2.get("cached") is True, "2번째가 캐시 hit이 아님: %s" % d2
        assert d1["image"] == d2["image"], "캐시 이미지 불일치"
        assert calls["n"] == 1, "생성이 2번 호출됨(캐시 미작동): %d" % calls["n"]
    finally:
        orc.generate_thumbnail = real
        srv._thumb_cache.clear()
    print("PASS test_thumbnail_cache_hit_no_regenerate")


if __name__ == "__main__":
    test_sse_format()
    test_load_samples()
    test_sse_format_queued()
    test_suggest_cache_hit()
    test_suggest_empty_not_cached()
    test_suggest_refresh_bypasses_cache()
    test_suggest_serialized_under_run_lock()
    test_suggest_busy_fallback_no_block()
    test_suggest_busy_returns_stale_cache()
    test_api_gamma_proxies_status()
    test_api_gamma_graceful_on_exception()
    test_api_gamma_missing_id()
    test_thumbnail_empty_prompt_400()
    test_thumbnail_ok_and_failed()
    test_thumbnail_cache_hit_no_regenerate()
    print("\n✅ ALL PASS (server)")
