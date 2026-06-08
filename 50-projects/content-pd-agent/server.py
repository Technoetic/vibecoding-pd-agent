#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI 콘텐츠 PD 에이전트 — 웹 데모 서버.
표준 라이브러리 http.server만(의존성 0). 정적 페이지 + /api/pd SSE + /api/samples 폴백.
API 키는 서버 환경변수에서만 읽어 브라우저 노출 0.

주의: 데모는 동시 1요청 직렬 처리. 클라가 중간에 끊겨도 백엔드 기획(유료 LLM)은 완주한다(협조적 중단 미구현 — 데모 단순성).
실행:  BIZROUTER_API_KEY=... python server.py     (PORT 환경변수 또는 8000)
"""
import os, re, json, time, queue, threading, traceback, hashlib
from pathlib import Path
from urllib.parse import unquote
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import orchestrator as orc

HERE = Path(__file__).resolve().parent
WEB = HERE / "web"
OUTPUT = HERE / "output"
PORT = int(os.environ.get("PORT", 8000))

# 데모 동시성: 모델 호출 직렬화(전역 cost_total/State 레이스 회피)
_run_lock = threading.Lock()

# /api/suggest TTL 캐시 — 접속마다 유료 Sonar+LLM 호출 폭주 방지(비용 통제).
_SUGGEST_TTL = int(os.environ.get("SUGGEST_TTL", 1800))  # 기본 30분
_suggest_cache = {"at": 0.0, "data": None}
_suggest_lock = threading.Lock()

# /api/thumbnail prompt 해시 TTL 캐시 — 무인증 공개 엔드포인트의 비용 DoS 완화.
# 동일 prompt 재호출 시 유료 이미지 생성 0회. {prompt_sha256: (monotonic_at, image)}.
_THUMB_CACHE_TTL = int(os.environ.get("THUMBNAIL_CACHE_TTL", 3600))  # 기본 1시간
_THUMB_CACHE_MAX = 64                                                # 메모리 상한(무한증식 차단)
_thumb_cache = {}
_thumb_lock = threading.Lock()


def get_suggestions(refresh: bool = False) -> dict:
    """동적 주제 제안 — TTL 캐시. refresh=True면 캐시 무시하고 재생성.
    빈 결과(키부재·실패)는 캐시하지 않아 다음 호출에서 재시도 가능.

    CRITICAL(502 수정): 모델 호출은 반드시 _run_lock으로 직렬화한다. /api/pd와
    suggest가 동시에 BizRouter를 두드리면 컨테이너가 죽어 Railway 502(fallback)가 났다.
    단 suggest는 부가기능이므로 락을 짧게만 시도하고, 못 잡으면 캐시/빈결과로 즉시 폴백한다
    (느린 기획 생성이 홈 화면 로드를 막지 않게)."""
    now = time.monotonic()
    with _suggest_lock:
        c = _suggest_cache
        cached_ok = bool(c["data"] and c["data"].get("topics"))
        if not refresh and cached_ok and (now - c["at"]) < _SUGGEST_TTL:
            return {**c["data"], "cached": True}
        cached_snapshot = dict(c["data"]) if cached_ok else None

    # 모델 호출 직렬화: _run_lock을 짧게 시도. 다른 기획이 처리 중이면 즉시 폴백(블로킹 금지).
    acquired = _run_lock.acquire(timeout=2)
    if not acquired:
        if cached_snapshot:                    # 진행 중 → 가진 캐시라도 반환(만료됐어도)
            return {**cached_snapshot, "cached": True, "busy": True}
        return {"topics": [], "trends": [], "sources": [], "busy": True}
    try:
        data = orc.suggest_topics(n=6)
    finally:
        _run_lock.release()

    with _suggest_lock:
        if data.get("topics"):                 # 성공분만 캐시(빈 결과는 재시도 허용)
            _suggest_cache["at"] = time.monotonic()
            _suggest_cache["data"] = data
    return {**data, "cached": False}


def sse_pack(event: str, data: dict) -> str:
    """SSE 이벤트 직렬화: 'event: X\\ndata: {json}\\n\\n'."""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def load_samples() -> list:
    """output/CONTENT_*.md를 폴백 샘플로 파싱(존재분만 — 002 없음 graceful)."""
    out = []
    if not OUTPUT.exists():
        return out
    for md in sorted(OUTPUT.glob("CONTENT_*.md")):
        txt = md.read_text(encoding="utf-8")
        title_m = re.search(r'^title:\s*"(.+?)"', txt, re.M)
        script_m = re.search(r"## 🎬 스크립트\s*\n(.+?)(?:\n##|\Z)", txt, re.S)
        tags_m = re.search(r"## 🏷 해시태그\s*\n(.+?)(?:\n##|\Z)", txt, re.S)
        out.append({
            "id": md.stem,
            "title": title_m.group(1) if title_m else md.stem,
            "script": (script_m.group(1).strip() if script_m else ""),
            "hashtags": (tags_m.group(1).strip() if tags_m else ""),
        })
    return out


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, ctype, body: bytes):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/" or path == "/index.html":
            f = WEB / "index.html"
            if f.exists():
                self._send(200, "text/html; charset=utf-8", f.read_bytes())
            else:
                self._send(200, "text/plain; charset=utf-8", b"index.html missing")
            return
        if path == "/api/samples":
            self._send(200, "application/json; charset=utf-8",
                       json.dumps(load_samples(), ensure_ascii=False).encode("utf-8"))
            return
        if path == "/api/suggest":
            refresh = "refresh=1" in (self.path.split("?", 1)[1] if "?" in self.path else "")
            try:
                data = get_suggestions(refresh=refresh)
            except Exception as e:                          # 제안 실패가 페이지 로드를 막지 않게(빈 결과 graceful)
                data = {"topics": [], "trends": [], "sources": [], "error": str(e)[:200]}
            self._send(200, "application/json; charset=utf-8",
                       json.dumps(data, ensure_ascii=False).encode("utf-8"))
            return
        if path == "/api/gamma":
            # Gamma 생성 상태 프록시 — 키는 orchestrator가 환경변수에서만(브라우저 노출 0).
            # 모델호출 아님(502 레이스 무관)이라 _run_lock 불필요. 클라가 5초 폴링.
            qs = self.path.split("?", 1)[1] if "?" in self.path else ""
            gid = ""
            for kv in qs.split("&"):
                if kv.startswith("id="):
                    gid = unquote(kv[3:])
                    break
            try:
                data = orc.gamma_status(gid)
            except Exception as e:                          # 폴링 실패가 프론트를 깨지 않게 graceful
                data = {"status": "failed", "error": str(e)[:200]}
            self._send(200, "application/json; charset=utf-8",
                       json.dumps(data, ensure_ascii=False).encode("utf-8"))
            return
        if path == "/api/health":
            self._send(200, "application/json", b'{"ok":true}')
            return
        self._send(404, "text/plain", b"not found")

    def _handle_thumbnail(self):
        # 썸네일 이미지 생성 프록시 — 키는 orchestrator가 환경변수에서만(브라우저 노출 0).
        # 생성 실패/키 없음/토글 OFF는 status:"failed"로 강등 → 프론트가 프롬프트 텍스트 폴백.
        try:
            length = int(self.headers.get("Content-Length", 0))
        except (TypeError, ValueError):
            length = 0
        if length < 0 or length > 1_000_000:        # thumbnail_prompt는 짧음
            self._send(400, "application/json", b'{"error":"bad content-length"}')
            return
        try:
            req = json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
        except json.JSONDecodeError:
            req = {}
        prompt = (req.get("prompt") or "").strip()
        if not prompt:
            self._send(400, "application/json", b'{"error":"prompt required"}')
            return
        # prompt 해시 TTL 캐시 — 동일 prompt 반복 호출 시 유료 생성 0회(비용 DoS 완화)
        key = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        now = time.monotonic()
        with _thumb_lock:
            hit = _thumb_cache.get(key)
            if hit and (now - hit[0]) < _THUMB_CACHE_TTL:
                self._send(200, "application/json; charset=utf-8",
                           json.dumps({"status": "ok", "image": hit[1], "cached": True}, ensure_ascii=False).encode("utf-8"))
                return
        try:
            with _run_lock:                          # 모델 호출 — 전역 cost_total 레이스 회피(기존 정책 일관)
                image = orc.generate_thumbnail(prompt)
            payload = {"status": "ok", "image": image} if image else {"status": "failed"}
        except Exception as e:                        # 어떤 예외도 프론트를 깨지 않게 graceful
            payload = {"status": "failed", "error": str(e)[:200]}
        if payload.get("status") == "ok" and payload.get("image"):   # 성공분만 캐시(실패는 재시도 허용)
            with _thumb_lock:
                if len(_thumb_cache) >= _THUMB_CACHE_MAX:            # 상한 초과 시 단순 비움(무한증식 차단)
                    _thumb_cache.clear()
                _thumb_cache[key] = (now, payload["image"])
        self._send(200, "application/json; charset=utf-8",
                   json.dumps(payload, ensure_ascii=False).encode("utf-8"))

    def do_POST(self):
        post_path = self.path.split("?", 1)[0]
        if post_path == "/api/thumbnail":
            self._handle_thumbnail()
            return
        if post_path != "/api/pd":
            self._send(404, "text/plain", b"not found")
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
        except (TypeError, ValueError):
            length = 0
        if length < 0 or length > 1_000_000:  # 1MB 상한(데모 토픽은 짧음)
            self._send(400, "application/json", b'{"error":"bad content-length"}')
            return
        try:
            req = json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
        except json.JSONDecodeError:
            req = {}
        topic = (req.get("topic") or "").strip()
        if not topic:
            self._send(400, "application/json", b'{"error":"topic required"}')
            return

        # SSE 헤더
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("X-Accel-Buffering", "no")  # 프록시 버퍼링 방지(Railway 엣지)
        self.end_headers()

        q = queue.Queue()
        SENTINEL = object()

        def on_step(payload):
            q.put(payload)

        def worker():
            acquired = _run_lock.acquire(timeout=180)  # 좀비 worker가 무한 점유 못 하게
            if not acquired:
                q.put({"stage": "error", "reason": "서버가 다른 기획을 처리 중입니다. 잠시 후 다시 시도하세요."})
                q.put(SENTINEL)
                return
            try:
                orc.run(topic, on_step=on_step)
            except Exception as e:
                traceback.print_exc()  # 컨테이너 stderr에 남긴다 — 크래시/예외 사인 관측(로그 소실 방지)
                q.put({"stage": "error", "reason": str(e)[:200], "trace": traceback.format_exc()[:300]})
            finally:
                _run_lock.release()
                q.put(SENTINEL)

        if _run_lock.locked():
            self.wfile.write(sse_pack("step", {"stage": "queued", "reason": "앞선 요청 처리 중 — 대기"}).encode("utf-8"))
            self.wfile.flush()

        t = threading.Thread(target=worker, daemon=True)
        t.start()

        try:
            while True:
                payload = q.get()
                if payload is SENTINEL:
                    break
                stage = payload.get("stage", "step")
                event = "done" if stage in ("done", "escalated") else ("error" if stage == "error" else "step")
                self.wfile.write(sse_pack(event, payload).encode("utf-8"))
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass  # 클라이언트 끊김 — 서버 크래시 방지

    def log_message(self, *a):
        pass  # 로그 소음 억제


def main():
    srv = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"PD 에이전트 데모 서버 — http://0.0.0.0:{PORT}")
    srv.serve_forever()


if __name__ == "__main__":
    main()
