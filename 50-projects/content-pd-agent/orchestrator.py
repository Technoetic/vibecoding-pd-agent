#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI 콘텐츠 PD 에이전트 — 4-에이전트 오케스트레이터
백엔드: BizRouter (OpenAI 호환) / 모델: google/gemini-2.5-flash-lite

표준 라이브러리만 사용(의존성 0). 페르소나 .md를 system 프롬프트로 주입하고,
State.json을 상태 머신으로 굴리며, eval_scenarios.json으로 Eval 루프를 돈다.

실행:
    export BIZROUTER_API_KEY="sk-br-v1-..."
    python orchestrator.py "개발 없이 5일 만에 수익 웹서비스 비법"
"""
import os, sys, json, re, time, urllib.request, urllib.error
from datetime import date
from pathlib import Path

# ── 경로 (어디서 실행해도 동작 — 볼트 안 / 번들 컨테이너 양쪽) ─────────
HERE = Path(__file__).resolve().parent              # 50-projects/content-pd-agent

def _resolve_dir(*candidates: Path) -> Path:
    """존재하는 첫 후보 디렉토리를 반환(없으면 마지막 후보 — graceful 폴백)."""
    for c in candidates:
        if c.exists():
            return c
    return candidates[-1]

# 볼트 안에서 실행: HERE.parents[1] = 볼트 루트. 컨테이너 번들: HERE/_vault.
# parents[1]은 /app 같은 얕은 경로에서 IndexError → 안전 추출.
_VAULT_UP = HERE.parents[1] if len(HERE.parents) >= 2 else HERE
_BUNDLE = HERE / "_vault"                            # 컨테이너 배포용 번들(00-meta·20-knowledge 사본)
PERSONAS = _resolve_dir(_BUNDLE / "00-meta" / "personas", _VAULT_UP / "00-meta" / "personas")
KNOWLEDGE = _resolve_dir(_BUNDLE / "20-knowledge", _VAULT_UP / "20-knowledge")
LOG = _VAULT_UP / "00-meta" / "log.md"              # 로그는 볼트 안에서만(컨테이너는 graceful skip)
STATE_PATH = HERE / "State.json"
EVAL_PATH = HERE / "eval_scenarios.json"
OUTPUT_DIR = HERE / "output"
CATALOG_PATH = HERE / "channel_catalog.json"     # 양실장 채널 영상 카탈로그(중복검사·트렌드용)

API_URL = "https://api.bizrouter.ai/v1/chat/completions"
MODEL = "google/gemini-2.5-flash-lite"  # 종료 2026-10-16 — 그 전까지 저단가 유지(3.1은 2.85배), horizon 임박 시 1줄 교체. ADR-006
TREND_MODEL = "perplexity/sonar"  # 실시간 트렌드 조사(웹검색 내장). json_object 미지원, 출처는 metadata.search_results
API_KEY = os.environ.get("BIZROUTER_API_KEY", "")

# Gamma Generate API v1.0 — 승인 기획안을 프레젠테이션(PDF)으로. 키는 환경변수만(브라우저 노출 0).
# BizRouter와 별개 크레딧 체계라 token_usage/cost_total에 누적하지 않음(credits는 status로 노출만).
GAMMA_API_KEY = os.environ.get("GAMMA_API_KEY", "")
GAMMA_BASE = "https://public-api.gamma.app/v1.0"

cost_total = 0.0  # 누적 비용(원)
token_usage = {"prompt": 0, "completion": 0, "total": 0, "calls": 0}  # 누적 토큰(BizRouter usage 실측 키)


# ── BizRouter 호출 (json_object 강제) ──────────────────────────────
def call(system: str, user: str, temperature: float = 0.7, max_tokens: int = 1200) -> dict:
    global cost_total
    body = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "response_format": {"type": "json_object"},
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    data = None
    for attempt in range(3):  # 일시 오류 재시도(지수 백오프)
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            break
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "ignore")[:300]
            if attempt == 2:
                raise RuntimeError(f"HTTP {e.code}: {detail}")
            time.sleep(2 ** attempt)
        except Exception:
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)
    if data is None:
        raise RuntimeError("BizRouter 호출 실패 — 응답 없음")
    usage = data.get("usage", {})
    cost_total += float(usage.get("cost", 0) or 0)
    token_usage["prompt"] += int(usage.get("prompt_tokens", 0) or 0)
    token_usage["completion"] += int(usage.get("completion_tokens", 0) or 0)
    token_usage["total"] += int(usage.get("total_tokens", 0) or 0)
    token_usage["calls"] += 1
    choices = data.get("choices") or []      # API가 {"error":...} 줄 때 KeyError/IndexError 방어
    if not choices:
        raise RuntimeError(f"BizRouter 비정상 응답(choices 없음): {str(data)[:200]}")
    choice = choices[0]
    if choice.get("finish_reason") == "length":
        raise RuntimeError(
            f"응답이 max_tokens({max_tokens})에서 잘림 — 토큰 상향 필요. "
            f"completion_tokens={usage.get('completion_tokens')}"
        )
    content = (choice.get("message") or {}).get("content") or ""
    return parse_json(content)


def call_text(user: str, model: str = TREND_MODEL, temperature: float = 0.2, max_tokens: int = 1000):
    """
    비-JSON 텍스트 호출(Perplexity Sonar용 — json_object 미지원).
    반환: (content_str, sources[{title,url}]). 출처는 message.metadata.search_results에서 추출.
    토큰/비용은 call()과 동일하게 token_usage·cost_total에 누적.
    """
    global cost_total
    body = {
        "model": model,
        "messages": [{"role": "user", "content": user}],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
        method="POST",
    )
    data = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            break
        except urllib.error.HTTPError as e:
            if attempt == 2:
                raise RuntimeError(f"HTTP {e.code}: {e.read().decode('utf-8', 'ignore')[:300]}")
            time.sleep(2 ** attempt)
        except Exception:
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)
    if data is None:
        raise RuntimeError("Sonar 호출 실패 — 응답 없음")
    usage = data.get("usage", {})
    cost_total += float(usage.get("cost", 0) or 0)
    token_usage["prompt"] += int(usage.get("prompt_tokens", 0) or 0)
    token_usage["completion"] += int(usage.get("completion_tokens", 0) or 0)
    token_usage["total"] += int(usage.get("total_tokens", 0) or 0)
    token_usage["calls"] += 1
    choices = data.get("choices") or []      # Sonar 비정상 응답 방어(fetch_live_trends가 상위서 graceful catch)
    if not choices:
        raise RuntimeError(f"Sonar 비정상 응답(choices 없음): {str(data)[:200]}")
    if choices[0].get("finish_reason") == "length":
        raise RuntimeError(
            f"Sonar 응답 잘림(max_tokens={max_tokens}) — 토큰 상향 필요. "
            f"completion_tokens={usage.get('completion_tokens')}"
        )
    msg = choices[0].get("message") or {}
    meta = msg.get("metadata") or {}
    raw_sources = meta.get("search_results") or []
    sources = [{"title": s.get("title") or s.get("url", ""), "url": s.get("url", "")} for s in raw_sources if s.get("url")]
    return msg.get("content", ""), sources


# ── Gamma Generate API (승인 기획안 → 프레젠테이션 PDF) ───────────────
# 설계: 접근법 A(서버 백그라운드 + 클라 폴링). gamma_generate는 생성요청만(블로킹 0),
# 폴링은 server.py /api/gamma 프록시가 gamma_status로 대리. 실패는 예외 대신 dict로
# 강등해 기획안(done payload) 표시를 절대 막지 않는다(graceful degradation).
def gamma_build_input(payload: dict, topic: str) -> str:
    """승인 payload(title/script/storyboard/thumbnail_prompt/hashtags)를 Gamma inputText로.
    슬라이드 구획 힌트를 포함한 일반 텍스트."""
    title = _as_str(payload.get("title") or topic)
    script = _as_str(payload.get("script"))
    storyboard = _as_list(payload.get("storyboard"))
    thumb = _as_str(payload.get("thumbnail_prompt"))
    tags = _as_list(payload.get("hashtags"))
    sb_lines = "\n".join(f"{i+1}. {_as_str(s)}" for i, s in enumerate(storyboard))
    tag_line = " ".join(_as_str(t) for t in tags)
    parts = [
        f"{title} — 쇼츠 기획안 프레젠테이션",
        f"이 발표는 '{topic}' 주제의 승인된 쇼츠/틱톡 기획안을 발표용 슬라이드로 정리한 것이다.",
        "",
        "[슬라이드: 제목] " + title,
        "",
        "[슬라이드: 스크립트] 영상 대본",
        script,
        "",
        "[슬라이드: 스토리보드] 장면 구성",
        sb_lines,
        "",
        "[슬라이드: 썸네일 컨셉] " + thumb,
        "",
        "[슬라이드: 해시태그] " + tag_line,
    ]
    return "\n".join(p for p in parts if p is not None)


def _gamma_request(method: str, path: str, body: "dict | None" = None, timeout: int = 30) -> dict:
    """Gamma API 단일 호출(urllib, 의존성 0). 성공 시 파싱된 dict 반환, 실패 시 RuntimeError."""
    url = f"{GAMMA_BASE}{path}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(
        url, data=data,
        # User-Agent 필수 — Gamma 앞단 Cloudflare가 기본 'Python-urllib' UA를 봇(HTTP 403 code 1010)으로 차단.
        headers={"X-API-KEY": GAMMA_API_KEY, "Content-Type": "application/json",
                 "User-Agent": "content-pd-agent/1.0", "Accept": "application/json"},
        method=method,
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def gamma_generate(payload: dict, topic: str, num_cards: int = 9) -> dict:
    """POST /generations — 생성요청만(폴링 안 함, 블로킹 0).
    반환: {"status":"generating","id":genId} | {"status":"failed","error":...}.
    예외를 던지지 않는다 — Gamma 실패가 기획안 표시를 막으면 안 됨(부가기능)."""
    if not GAMMA_API_KEY:
        return {"status": "failed", "error": "GAMMA_API_KEY 미설정"}
    req_body = {
        "inputText": gamma_build_input(payload, topic),
        "format": "presentation",
        "textMode": "generate",
        "numCards": num_cards,
        "exportAs": "pdf",
        "cardOptions": {"dimensions": "16x9"},
        "textOptions": {"amount": "medium", "tone": "professional",
                        "audience": "general", "language": "ko"},
        "imageOptions": {"source": "aiGenerated"},
    }
    try:
        data = _gamma_request("POST", "/generations", req_body)
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "ignore")[:200]
        return {"status": "failed", "error": f"HTTP {e.code}: {detail}"}
    except Exception as e:
        return {"status": "failed", "error": str(e)[:200]}
    gid = data.get("generationId") or data.get("id")
    if not gid:
        return {"status": "failed", "error": f"generationId 없음: {str(data)[:150]}"}
    return {"status": "generating", "id": gid}


def gamma_status(gen_id: str) -> dict:
    """GET /generations/{id} — server.py /api/gamma 프록시가 호출.
    반환: {"status":"completed|pending|failed", "pdf_url":..., "gamma_url":..., "credits":...}.
    예외 대신 dict 강등(프론트 폴링이 graceful)."""
    if not GAMMA_API_KEY:
        return {"status": "failed", "error": "GAMMA_API_KEY 미설정"}
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", gen_id or ""):
        return {"status": "failed", "error": "잘못된 generation id"}
    try:
        data = _gamma_request("GET", f"/generations/{gen_id}")
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "ignore")[:200]
        return {"status": "failed", "error": f"HTTP {e.code}: {detail}"}
    except Exception as e:
        return {"status": "failed", "error": str(e)[:200]}
    st = data.get("status", "")
    out = {"status": st, "credits": data.get("credits", {})}
    if st == "completed":
        out["pdf_url"] = data.get("exportUrl", "")
        out["gamma_url"] = data.get("gammaUrl", "")
    elif st == "failed":
        out["error"] = _as_str(data.get("error")) or "Gamma 생성 실패"
    return out


def _coerce_dict(obj) -> dict:
    """파싱 결과가 dict가 아니면(LLM이 배열·null·문자열 반환) 빈 dict로 강등.
    핸드오프 무결성 — 후속 .get/.update가 항상 dict 위에서 동작하도록 보장."""
    return obj if isinstance(obj, dict) else {}


def parse_json(text: str) -> dict:
    """모델 출력에서 첫 JSON 객체를 견고하게 추출(항상 dict 반환).
    코드펜스(```json), 선행 설명, 후행 여분텍스트('Extra data'), 비-dict 최상위를
    모두 흡수한다. Sonar/flash-lite의 비결정 출력 방어(공개 배포 검증서 발견)."""
    s = (text or "").strip()
    # 1) 코드펜스 제거: ```json ... ``` 또는 ``` ... ```
    fence = re.search(r"```(?:json)?\s*(.+?)\s*```", s, re.S)
    if fence:
        s = fence.group(1).strip()
    # 2) 그대로 시도
    try:
        return _coerce_dict(json.loads(s))
    except json.JSONDecodeError:
        pass
    # 3) 첫 '{' 부터 raw_decode — 첫 유효 객체만 취하고 'Extra data' 후행 무시
    start = s.find("{")
    if start != -1:
        try:
            obj, _ = json.JSONDecoder().raw_decode(s[start:])
            return _coerce_dict(obj)
        except json.JSONDecodeError:
            pass
    # 4) 최후: greedy 중괄호 매칭
    m = re.search(r"\{.*\}", s, re.S)
    if m:
        return _coerce_dict(json.loads(m.group(0)))
    raise json.JSONDecodeError("JSON 객체를 찾지 못함", text or "", 0)


def _as_list(v) -> list:
    """LLM 필드가 list 아니면(string·dict·null) 안전하게 list로 정규화.
    list 기대 필드(keywords·hooks·storyboard·hashtags·checks)에 string이 와도
    문자 단위 순회(메트릭 오염)·enumerate 깨짐을 막는다(견고성 감사 발견)."""
    if isinstance(v, list):
        return v
    if v is None or v == "":
        return []
    return [v]  # 단일 문자열/객체 → 1원소 리스트


def _as_str(v) -> str:
    """LLM 필드가 str 아니면(list·dict·null) 안전하게 str로 정규화."""
    if isinstance(v, str):
        return v
    if v is None:
        return ""
    if isinstance(v, list):
        return "\n".join(str(x) for x in v)
    return str(v)


def load(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def load_persona(name: str) -> str:
    return load(PERSONAS / f"{name}.md")


def knowledge_digest() -> str:
    """20-knowledge의 훅·트렌드 노트를 한 묶음으로(에이전트 근거)."""
    parts = []
    for sub in ("hooks", "trends", "scripts"):
        for md in sorted((KNOWLEDGE / sub).glob("*.md")):
            parts.append(f"### {md.stem}\n{load(md)}")
    return "\n\n".join(parts) if parts else "(지식 노트 없음)"


# ── 독창성 검사 (결정론적 — LLM '가정' 대체) ──────────────────────
def _extract_script(md_text: str) -> str:
    """output/*.md에서 '## 🎬 스크립트' 본문만 추출."""
    m = re.search(r"## 🎬 스크립트\s*\n(.+?)(?:\n##|\Z)", md_text, re.S)
    return (m.group(1) if m else md_text).strip()


def existing_scripts(exclude_task_id: str = "") -> list:
    """output/의 기존 기획안 스크립트 목록(자기 자신 제외)."""
    out = []
    if not OUTPUT_DIR.exists():
        return out
    for md in sorted(OUTPUT_DIR.glob("CONTENT_*.md")):
        if exclude_task_id and md.stem == exclude_task_id:
            continue
        out.append(_extract_script(load(md)))
    return out


def originality_score(draft_script: str, prior_scripts: list) -> dict:
    """
    신규 스크립트와 기존들 간 최대 유사도(0~1)를 결정론적으로 계산.
    difflib.SequenceMatcher 기반(표준 라이브러리, 의존성 0).
    반환: {max_similarity, most_similar_to(index), is_original(<0.85)}.
    """
    import difflib
    a = re.sub(r"\s+", " ", draft_script or "").strip()
    best, best_i = 0.0, -1
    for i, prior in enumerate(prior_scripts):
        b = re.sub(r"\s+", " ", prior or "").strip()
        if not a or not b:
            continue
        ratio = difflib.SequenceMatcher(None, a, b).ratio()
        if ratio > best:
            best, best_i = ratio, i
    return {
        "max_similarity": round(best, 4),
        "most_similar_to": best_i,
        "is_original": best < 0.85,
    }


# ── 채널 중복 검사 (제목 토큰 자카드 — difflib보다 어순/조사에 강건) ──
_JOSA = ("으로", "로", "은", "는", "이", "가", "을", "를", "의", "에", "에서", "와", "과", "도", "만")


def _title_tokens(title: str) -> set:
    """제목을 정규화 토큰 집합으로. 공백 split + 한국어 조사 꼬리 제거(형태소 분석기 미사용, 의존성 0)."""
    out = set()
    for raw in re.sub(r"[^\w가-힣\s]", " ", title or "").split():
        t = raw.strip().lower()
        for j in _JOSA:  # 긴 조사 우선
            if len(t) > len(j) and t.endswith(j):
                t = t[: -len(j)]
                break
        if t:
            out.add(t)
    return out


def title_overlap_score(draft_title: str, catalog_titles: list, thresh: float = 0.6) -> dict:
    """
    신규 제목과 채널 기존 영상 제목들 간 최대 토큰 자카드(0~1)를 결정론 계산.
    반환: {max_jaccard, most_similar_title, is_distinct(<thresh)}.
    빈 카탈로그면 max_jaccard=0, is_distinct=True (graceful — 검사 무력화).
    """
    a = _title_tokens(draft_title)
    best, best_title = 0.0, ""
    for t in catalog_titles:
        b = _title_tokens(t)
        if not a or not b:
            continue
        inter = len(a & b)
        jaccard = inter / len(a | b)
        overlap = inter / min(len(a), len(b))  # 한쪽이 다른 쪽에 거의 포함되는 중복 포착
        score = max(jaccard, overlap)
        if score > best:
            best, best_title = score, t
    return {
        "max_jaccard": round(best, 4),
        "most_similar_title": best_title,
        "is_distinct": best < thresh,
    }


def load_channel_titles() -> list:
    """channel_catalog.json의 영상 제목 리스트. 파일 없으면 [] (graceful degrade)."""
    if not CATALOG_PATH.exists():
        return []
    try:
        data = json.loads(load(CATALOG_PATH))
        videos = data.get("videos") or []
        return [v.get("title", "") for v in videos if isinstance(v, dict) and v.get("title")]
    except (json.JSONDecodeError, OSError, ValueError):
        return []


def korean_syllables(text: str) -> int:
    """한글 음절(가-힣) 개수만 결정론 카운트. 공백·영문·숫자·기호 제외."""
    return len(re.findall(r"[가-힣]", text or ""))


def pick_hook(hooks: "list | None", limit: int = 21) -> str:
    """채택 훅을 결정론으로 선택. Trend Analyst가 1~3개 훅을 내면 무조건 [0]을 쓰던 탓에
    [0]이 21음절 초과면 [1]이 짧아도 반려됐다(e2e: korean_syllable_density가 모든 escalated에 등장).
    21음절 이내 훅이 하나라도 있으면 그중 가장 긴 것(정보량↑), 전부 초과면 가장 짧은 것을 고른다."""
    cands = [h for h in (hooks or []) if isinstance(h, str) and h.strip()]
    if not cands:
        return ""
    fits = [h for h in cands if korean_syllables(h) <= limit]
    if fits:
        return max(fits, key=korean_syllables)        # 한계 내에서 가장 정보량 많은 훅
    return min(cands, key=korean_syllables)            # 전부 초과 → 그나마 가장 짧은 것


def script_density_score(hook: str, full_script: str) -> dict:
    """
    한국어 음절 밀도 결정론 측정.
    반환: {hook_syllables, hook_ok(<=21), script_syllables, density_ok(<=600/분 가정 단순화: 전체<=600)}.
    """
    h = korean_syllables(hook)
    s = korean_syllables(full_script)
    return {
        "hook_syllables": h,
        "hook_ok": h <= 21,
        "script_syllables": s,
        "density_ok": s <= 600,  # 60초 기준 600음절 상한(보고서: 초과 시 인지과부하)
    }


def hashtag_count_score(hashtags: list) -> dict:
    """해시태그 개수 결정론 검사(1~5개 최적)."""
    n = len(hashtags or [])
    return {"count": n, "ok": 1 <= n <= 5}


def word_count_score(script: str, min_w: int = 100, max_w: int = 250) -> dict:
    """스크립트 단어 수 결정론 카운트(공백 분리). LLM 눈대중 대체."""
    n = len((script or "").split())
    return {"words": n, "ok": min_w <= n <= max_w}


def expand_script(script: str, target: int = 130, keywords=None, hook: str = "", max_passes: int = 2) -> str:
    """길이 미달 전용 결정론 후처리 — retry_count를 소모하지 않고 '확장만' 요청한다.
    라이브 e2e에서 Creator(flash-lite)가 70→97→90으로 100단어를 못 넘겨 length_bounds 단독
    escalated가 났다(프롬프트로 120 지시해도 변덕). 여기서 분량만 메운다.

    채택은 호출부 책임(키워드·originality 비악화 가드). 헬퍼는 '더 길고 키워드 보존된' 후보만 반환.
    250단어 상한 명시(반대편 length_bounds·음절캡 충돌 방지), 과장단정 추가 금지(overclaim 회귀 차단)."""
    cur = _as_str(script)
    kws = [k for k in (keywords or []) if k]
    best, best_w = cur, len(cur.split())
    if best_w >= target:
        return cur
    for _ in range(max(1, max_passes)):
        sys_p = (
            "너는 한국어 쇼츠 스크립트 '확장 편집기'다. 아래 본문의 메시지·구조·훅·키워드를 100% 보존하면서 분량만 늘린다.\n"
            "## 절대 규칙\n"
            f"- 출력 단어 수: 공백 분리 ★{target}단어 이상★ 250단어 이하(상한 초과 금지).\n"
            "- 기존 문장을 삭제·치환하지 말고, 구체 사례·실행 단계·근거 수치를 '추가'만 하라.\n"
            "- 새 주제·새 결론 도입 금지. 같은 내용을 더 자세히 풀어라.\n"
            "- 아래 키워드 어구는 표기 그대로 본문에 유지/재등장: " + (", ".join(kws) if kws else "(없음)") + "\n"
            + (f"- 첫 3초 훅 문장은 변형 없이 맨 앞에 유지: {hook}\n" if hook else "")
            + "- '무조건·보장·누구나·100%·평생·완전·쌉가능' 등 단정/과장 표현 추가 금지(가능성·사례한정으로).\n"
            "## 출력 형식 (JSON만)\n"
            '{"script": "확장된 본문(기존 보존 + 추가)"}'
        )
        need = target - len(cur.split())
        user = f"확장 대상 본문(현재 {len(cur.split())}단어, 약 {need}단어 더 필요):\n\n{cur}"
        try:
            r = call(sys_p, user, temperature=0.2, max_tokens=1400)  # 감온: 보존성↑ 변덕↓
        except Exception:
            break                                                    # 실패 시 best-effort 반환(Reviewer가 잡음)
        ext = _as_str(r.get("script")).strip()
        ew = len(ext.split())
        kept_kw = all(_keyword_present(k, ext) for k in kws) if kws else True
        if ext and ew > best_w and kept_kw and ew <= 250:            # 더 길고·키워드보존·상한내 → 채택
            best, best_w, cur = ext, ew, ext
        if best_w >= target:                                         # 목표 달성 → 추가 콜 차단
            break
    return best


_COMMON_TOKENS = {"AI"}  # 변별력 없는 초고빈도 공통토큰. 'AI'만. 도메인 빈출어 추가 금지(0.8 임계 케이스 즉시 반려 회귀).


def _keyword_present(keyword: str, script: str, tok_ratio: float = 0.7, window: int = 20) -> bool:
    """키워드 토큰의 근접 부분일치. 한국어 조사·어순 변형은 인정하되,
    흩어진 우연 매칭·공통토큰 스터핑은 차단(결정론 엄정성 보존).
    - 단일 토큰: substring 존재로 충분(기존 엄정성 유지)
    - 복합 토큰: 자기 토큰 70%가 좁은 윈도우 안에 군집해야 통과(근접 요구).
      추가로 공통토큰('AI') 외 고유토큰이 최소 1개 등장해야 통과 — 2토큰 키워드의
      need=round(2*0.7)=1 붕괴로 'AI'만 스터핑해도 통과되던 가짜통과를 차단(e2e 발견)."""
    toks = [t for t in re.split(r"\s+", (keyword or "").strip()) if t]
    if not toks:
        return False
    if len(toks) == 1:
        return toks[0] in script
    # 안티-스터핑: 복합 키워드는 고유토큰(비-공통) 최소 1개가 본문에 있어야 한다.
    # uniq가 비면(키워드 전체가 공통토큰) 이 제약을 건너뛰어 기존 동작 보존.
    uniq = [t for t in toks if t not in _COMMON_TOKENS]
    if uniq and not any(u in script for u in uniq):
        return False
    need = max(1, round(len(toks) * tok_ratio))
    pos = {t: [m.start() for m in re.finditer(re.escape(t), script)] for t in toks}
    present = [t for t in toks if pos[t]]
    if len(present) < need:
        return False
    span = window * len(toks)                 # 토큰들이 좁은 범위에 군집해야 통과(흩어짐 차단)
    starts = sorted({p for t in present for p in pos[t]})
    for s0 in starts:
        cnt = sum(1 for t in present if any(s0 <= p <= s0 + span for p in pos[t]))
        if cnt >= need:
            return True
    return False


def keyword_inclusion_score(script: str, keywords: list, min_ratio: float = 0.8) -> dict:
    """타겟 키워드 본문 포함률 결정론 측정(근접 토큰 부분일치 — 조사/어순 변형 허용,
    흩어진 우연·스터핑 차단). exact-substring은 한국어 굴절을 0점 처리해 반복 반려를 유발했다(ADR)."""
    kws = [k for k in (keywords or []) if k]
    if not kws:
        return {"ratio": 0.0, "included": 0, "total": 0, "ok": False, "missing": [], "matched": []}
    s = script or ""
    matched = [k for k in kws if _keyword_present(k, s)]
    mset = set(matched)
    ratio = len(matched) / len(kws)
    return {"ratio": round(ratio, 3), "included": len(matched), "total": len(kws),
            "ok": ratio >= min_ratio, "matched": matched, "missing": [k for k in kws if k not in mset]}


# ── 팩트체크: 과장·거짓 단정 패턴(결정론) ──
_OVERCLAIM_PATTERNS = [
    (r"100\s*%|100\s*퍼센트|백\s*퍼센트", "100% 단정"),
    (r"무조건", "무조건 단정"),
    (r"누구나\s*(다|반드시)?\s*(\d|성공|가능|벌|할 수)", "누구나 단정"),
    (r"보장", "보장 단정"),
    (r"완전\s*(대체|자동화|해결|보장)", "완전 단정"),
    (r"(절대|틀림없이|확실히|확실하게|반드시)\s*\S{0,4}\s*(됩니다|성공|가능|수익|벌|효과)", "절대/반드시 단정"),
    (r"평생", "평생 단정"),
]


def overclaim_check(script: str) -> dict:
    """
    스크립트의 과장·거짓 단정 패턴을 결정론 탐지(교육채널 신뢰 보호).
    반환: {ok(패턴 없음), flags[탐지된 사유]}. 빈 스크립트는 ok=True.
    """
    flags = []
    for pat, label in _OVERCLAIM_PATTERNS:
        if re.search(pat, script or ""):
            flags.append(label)
    return {"ok": len(flags) == 0, "flags": flags}


def extract_numeric_claims(script: str) -> list:
    """
    스크립트에서 수치+단위 주장을 추출(검증 대상 식별).
    구독자·조회수·원·명·% 등이 붙은 숫자 구절. Reviewer가 채널 실제값과 대조하도록.
    """
    out = []
    for m in re.finditer(r"[\d,]+\s*(만|억|천)?\s*(명|회|원|건|개|%|배|일|주|개월|년|시간)", script or ""):
        out.append(m.group(0).strip())
    return out


def channel_top_topics(n: int = 10) -> list:
    """카탈로그 조회수 상위 N개 영상 제목 — Trend Analyst가 '채널에서 먹힌 주제' 근거로 사용."""
    if not CATALOG_PATH.exists():
        return []
    try:
        data = json.loads(load(CATALOG_PATH))
        videos = data.get("videos") or []
    except (json.JSONDecodeError, OSError, ValueError):
        return []
    vids = sorted(
        [v for v in videos if isinstance(v, dict)],
        key=lambda v: int(v.get("views", 0) or 0), reverse=True,
    )
    return [v.get("title", "") for v in vids[:n] if v.get("title")]


def _parse_trends(text: str) -> list:
    """
    Sonar 응답에서 trends 추출. 전체 JSON 파싱을 먼저 시도하고,
    실패하면 개별 {"keyword":..,"why":..} 객체를 정규식으로 하나씩 건진다(부분 복구).
    """
    # 1차: 정상 JSON 파싱
    try:
        parsed = parse_json(text)
        if isinstance(parsed, dict):
            trends = parsed.get("trends", [])
            if isinstance(trends, list):
                clean = [t for t in trends if isinstance(t, dict) and t.get("keyword")]
                if clean:
                    return clean
    except Exception:
        pass
    # 2차: 정규식으로 개별 객체 부분 추출(깨진 JSON 대비)
    out = []
    for m in re.finditer(r'\{[^{}]*?"keyword"\s*:\s*"([^"]+)"[^{}]*?"why"\s*:\s*"([^"]+)"[^{}]*?\}', text, re.S):
        out.append({"keyword": m.group(1).strip(), "why": m.group(2).strip()})
    return out


def fetch_live_trends(topic: str) -> dict:
    """
    Perplexity Sonar로 실시간 LLM/바이브코딩 트렌드 조사. 출처 포함.
    반환: {trends:[{keyword,why}], sources:[{title,url}]}.
    실패/파싱오류 시 {trends:[], sources:[]} (graceful — 기획은 정적 지식·채널주제로 진행).
    """
    # Sonar는 '사용자 메시지'가 웹 검색 동력 — 구체적·서술적 쿼리가 검색 품질을 결정(ADR-013).
    # 검색결과 없으면 추측 금지(그라운딩). 출처는 응답 metadata.search_results에서 추출(산문 링크 요구 금지).
    today = date.today()
    prompt = (
        f"지금은 {today.year}년 {today.month}월이다. 최근 3개월({today.year}년 기준) 한국의 "
        f"비개발자·바이브코딩·AI 노코드 창업 분야에서 실제로 화제가 된 "
        f"구체적 트렌드 키워드 5개를 웹에서 조사하라. 주제 '{topic}'와 연관되면 우선 포함하라. "
        f"{today.year - 1}년 이전의 낡은 트렌드는 제외하고 최신만. "
        f"검색 결과에 근거가 없으면 추측하지 말고 빈 배열로 두라. "
        f"반드시 순수 JSON만 출력(설명·코드펜스·출처링크 금지, 출처는 시스템이 별도 수집): "
        '{"trends":[{"keyword":"...","why":"검색 근거 한줄"}]}'
    )
    try:
        text, sources = call_text(prompt, model=TREND_MODEL)
        trends = _parse_trends(text)
        return {"trends": trends, "sources": sources}
    except Exception as e:
        print(f"   [trend-live] WARN: Sonar 실패 — {type(e).__name__}: {e}")
        return {"trends": [], "sources": []}


def suggest_topics(n: int = 6) -> dict:
    """
    홈 화면 '동적 주제 제안' — 실시간 Sonar 트렌드 + 채널 인기 주제 + 지식 노트를 재료로
    flash-lite가 '지금 찍으면 먹힐' 쇼츠 주제 n개를 새로 생성한다(과거 산출물 재탕 아님).
    반환: {topics:[{title, why}], trends:[...], sources:[...]}.
    실패/키부재 시 {topics:[], trends:[], sources:[]} (graceful — 프론트가 채널/샘플 폴백).

    비용: Sonar 1콜 + flash-lite 1콜(합 ~0.1원 수준). 접속마다 호출 폭주 방지는
    server.py의 TTL 캐시가 담당(여기선 순수 생성만).
    """
    if not API_KEY:
        return {"topics": [], "trends": [], "sources": []}
    try:
        live = fetch_live_trends("비개발자 AI 노코드 쇼츠 콘텐츠")  # 토픽 무관 일반 트렌드 스캔
    except Exception:
        live = {"trends": [], "sources": []}
    ch_topics = channel_top_topics(n=10)
    kb = knowledge_digest()

    ch = "\n".join(f"- {t}" for t in ch_topics) or "(없음)"
    tr = "\n".join(f"- {x.get('keyword','')}: {x.get('why','')}" for x in live.get("trends", [])) or "(없음)"
    today = date.today()
    sys_p = (
        f"오늘은 {today.year}년 {today.month}월이다. 너는 양실장 바이브코딩대학 채널의 콘텐츠 PD다. "
        "비개발자·노코드·AI 창업 타겟의 쇼츠/틱톡 주제를 발굴한다. 완주율(1순위 신호)과 3초 훅을 노린 "
        "'지금 찍으면 먹힐' 주제를 제안하라. 채널이 이미 다룬 주제와 겹치지 말고, 실시간 트렌드를 반영하라.\n"
        f"★연도 하드룰: 주제 문장에 연도를 넣을 거면 반드시 현재({today.year})·미래 연도만 써라. "
        f"'{today.year - 1}년'·'{today.year - 2}년' 같은 과거 연도를 '최신'이라며 박지 마라(낡아 보임). "
        "연도 없이 '요즘·지금·올해'로 가는 게 더 안전하다.\n"
        "컴플라이언스 하드룰: '무조건/보장/누구나 N원' 같은 수익 단정·과장 클레임 금지(표시광고법). "
        "가능성·호기심 자극으로 정직하게.\n\n"
        "## 출력 형식 (JSON만, 설명·코드펜스 금지)\n"
        '{"topics": [{"title": "클릭하면 그대로 기획에 넣을 쇼츠 주제 한 문장", "why": "지금 이게 먹히는 한 줄 근거"}]}'
    )
    user = (
        f"제안할 주제 개수: {n}개\n\n"
        f"=== 채널에서 이미 먹힌 인기 주제(톤·관심사 참고, 단 중복 금지) ===\n{ch}\n\n"
        f"=== 실시간 업계 트렌드(Perplexity Sonar — 검증 출처 거론분만) ===\n{tr}\n\n"
        f"=== 참고 지식(20-knowledge) ===\n{kb[:4000]}"
    )
    try:
        out = call(sys_p, user, temperature=0.9, max_tokens=800)
    except Exception as e:
        print(f"   [suggest] WARN: 주제 제안 생성 실패 — {type(e).__name__}: {e}")
        return {"topics": [], "trends": live.get("trends", []), "sources": live.get("sources", [])}

    topics = []
    for t in _as_list(out.get("topics")):
        if isinstance(t, dict) and _as_str(t.get("title")).strip():
            topics.append({"title": _as_str(t.get("title")).strip(), "why": _as_str(t.get("why")).strip()})
        elif isinstance(t, str) and t.strip():               # LLM이 문자열 배열만 줘도 흡수
            topics.append({"title": t.strip(), "why": ""})
    return {"topics": topics[:n], "trends": live.get("trends", []), "sources": live.get("sources", [])}


def deterministic_block(orig: dict, channel: dict, density: dict, htag: dict,
                        wc: "dict | None" = None, kw: "dict | None" = None) -> list:
    """
    결정론 검사 위반 사유를 모두 모아 반환. 위반이 여럿이면 모두 반환(retry 낭비 방지).
    빈 리스트면 결정론 차단 없음.

    측정 가능한 메트릭은 LLM verdict 변덕에 맡기지 않고 코드가 강제한다 — e2e에서 LLM이
    checks에 ❌(length/keyword 미달)를 찍고도 최상위 verdict를 approved로 내 Eval이 무력화되는
    모순을 관측했다(verdict-checks 불일치). word_count·keyword_inclusion을 여기서 강제차단해
    "측정으로 떨어지는데 운으로 승인"을 차단한다. density 본문 상한만 Reviewer soft로 둔다(맥락의존).
    """
    reasons = []
    if not orig["is_original"]:
        reasons.append(
            f"독창성 미달: 기존 기획안과 유사도 {orig['max_similarity']}(≥0.85). 새 앵글로 재작성."
        )
    if not channel["is_distinct"]:
        reasons.append(
            f"채널 중복: 기존 채널 영상 '{channel['most_similar_title']}'와 제목 자카드 "
            f"{channel['max_jaccard']}(≥0.6). 채널이 안 다룬 새 앵글로 재작성."
        )
    if not density["hook_ok"]:
        reasons.append(
            f"훅 음절 초과: {density['hook_syllables']}음절(≤21 한계). 3초에 다 읽히게 축약. (한국어 음절 결정론 측정)"
        )
    if not htag["ok"]:
        reasons.append(
            f"해시태그 개수 위반: {htag['count']}개(1~5개 최적). 니치 태그 중심으로 조정."
        )
    if wc is not None and not wc["ok"]:
        reasons.append(
            f"본문 단어 수 위반: {wc['words']}단어(100~250 범위). "
            f"{'구체 사례·단계로 100단어 이상 확장' if wc['words'] < 100 else '250단어 이하로 축약'}. (결정론 측정)"
        )
    if kw is not None and not kw["ok"]:
        reasons.append(
            f"키워드 포함률 미달: {kw['included']}/{kw['total']}({kw['ratio']}, 임계 0.8). "
            f"누락 키워드 {kw.get('missing', [])}를 본문에 자연스럽게 삽입. (결정론 측정)"
        )
    return reasons


# ── State.json 입출력 ──────────────────────────────────────────────
_STATE_DEFAULT = {"max_retries": 3, "tasks": []}

def read_state() -> dict:
    """State.json 읽기. 부재·손상 시 기본 상태로 graceful 복구(컨테이너 재시작·동시쓰기 방어)."""
    if not STATE_PATH.exists():
        return dict(_STATE_DEFAULT)
    try:
        s = json.loads(load(STATE_PATH))
        return s if isinstance(s, dict) else dict(_STATE_DEFAULT)
    except (json.JSONDecodeError, OSError):
        return dict(_STATE_DEFAULT)


def write_state(state: dict):
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def next_task_id(state: dict) -> str:
    n = 0
    for t in state.get("tasks", []):
        m = re.search(r"CONTENT_2026_(\d+)", t["task_id"])
        if m and not t["task_id"].endswith("EXAMPLE"):
            n = max(n, int(m.group(1)))
    return f"CONTENT_2026_{n+1:03d}"


# ── 4 에이전트 ─────────────────────────────────────────────────────
def agent_trend_analyst(topic: str, kb: str, channel_topics: list, live_trends: list) -> dict:
    sys_p = load_persona("trend-analyst") + (
        "\n\n## 출력 형식 (JSON만)\n"
        '{"keywords": ["1~2어절 짧은 핵심 명사구 5개 내외(조사·서술어 없이, 본문에 자연스럽게 박히게). '
        "예: '노코드 창업', 'AI 웹서비스'. '개발 없이 웹서비스를 만드는 법' 같은 완성문장 금지\"], "
        '"hooks": ["3초 훅 3개 — 각 한글 18음절 이내로 짧게(받침·이중모음도 1음절). '
        '3초에 다 읽혀야 한다. 최소 1개는 반드시 18음절 이내로. 예: AI로 웹사이트 5분 완성?(13음절)"]}'
    )
    ch = "\n".join(f"- {t}" for t in channel_topics) or "(없음)"
    tr = "\n".join(f"- {x.get('keyword','')}: {x.get('why','')}" for x in live_trends) or "(없음)"
    user = (
        f"주제: {topic}\n\n"
        f"=== 채널에서 이미 먹힌 인기 주제(조회수 상위 — 톤·관심사 참고, 단 중복 금지) ===\n{ch}\n\n"
        f"=== 실시간 업계 트렌드(Perplexity Sonar — 검증된 출처 거론분만, 단정 금지) ===\n{tr}\n\n"
        f"=== 참고 지식(20-knowledge) ===\n{kb}"
    )
    return call(sys_p, user, temperature=0.8, max_tokens=600)


def agent_creator(topic: str, keywords, hooks, feedback, kb: str, temperature: float = 0.8) -> dict:
    # Creator가 Reviewer와 같은 잣대로 쓰게 — 검수 기준을 선주입(비대칭 제거). e2e 실측상
    # length_bounds·korean_syllable_density 미달이 매 회차 반려의 주범이었다(Creator가 임계를 몰라서).
    sys_p = load_persona("creator") + (
        "\n\n## 검수 통과 필수 기준 — 처음부터 전부 동시 충족하라(하나라도 위반 시 즉시 반려)\n"
        "- 본문(script) 단어 수: 공백 분리 기준 ★120단어 이상★ 250단어 이하를 목표로 써라. "
        "100단어 미만은 자동 반려된다. 여유 있게 120단어를 넘기도록 구체 사례·단계·수치·근거를 채워라 "
        "(95~99단어로 아슬아슬하게 멈추지 말 것 — 실측상 모델이 자주 미달한다).\n"
        "- 해시태그: 1~5개(5개 초과 금지). #fyp·#viral 등 광범위 태그 금지, 본문과 일치하는 니치 태그만.\n"
        "- 수익/효과 단정 금지: '무조건·보장·누구나·쌉가능' 등 단정 대신 가능성·사례한정. 결과는 사람마다 다름.\n"
        "- 완주율 설계: 첫 3초 훅 → 핵심가치 초반 투척(결론 숨기지 말 것) → 본문 정보 사다리 → 마지막 명확 CTA.\n"
        "- 훅 차별화: '5분 만에'류 시간/수치 포화 앵글이면 비개발자 호명(정체성형)·반전 앵글을 우선.\n"
        f"- 연도: 제목·본문에 연도를 쓸 거면 {date.today().year}년(현재) 또는 미래만. 과거 연도를 '최신'처럼 박지 마라.\n"
        "\n## 출력 형식 (JSON만)\n"
        '{"title": "제목", "script": "쇼츠 스크립트 100~250단어(반드시 100단어 이상)", '
        '"storyboard": ["장면 단위 텍스트"], "thumbnail_prompt": "이미지 생성 프롬프트", '
        '"hashtags": ["#니치태그 1~5개"]}'
    )
    fb = ""
    if feedback:
        # 직전 1회가 아니라 누적 제약 전체 — A 고치다 B 깨는 두더지잡기 차단(e2e 확인).
        fb = ("\n\n=== 지금까지 누적된 모든 수정요구(아래를 전부 동시 충족하되, 명시 안 된 통과 부분은 보존) ===\n"
              + "\n".join(f"- {x}" for x in feedback))
    user = (
        f"주제: {topic}\n타겟 키워드: {keywords}\n채택 훅: {hooks}{fb}\n\n"
        f"=== 톤앤매너 근거(20-knowledge) ===\n{kb}"
    )
    return call(sys_p, user, temperature=temperature, max_tokens=1400)


def agent_reviewer(payload: dict, eval_spec: dict, orig: dict, channel: dict) -> dict:
    sys_p = load_persona("reviewer") + (
        "\n\n## 출력 형식 (JSON만)\n"
        '{"verdict": "approved 또는 rejected", "checks": '
        '[{"metric":"...","pass":true,"comment":"..."}], "feedback": ["수정요구(rejected일 때)"]}'
    )
    # originality_check는 메인이 결정론적으로 계산한 실측값을 주입 — LLM은 '가정'하지 말 것.
    orig_fact = (
        f"\n\n=== originality_check 실측(결정론 계산, 추측 금지) ===\n"
        f"기존 기획안과의 최대 유사도 = {orig['max_similarity']} "
        f"(임계 0.85, is_original={orig['is_original']}). "
        f"이 수치를 그대로 사용하라. {'통과' if orig['is_original'] else '0.85 초과 → 반드시 rejected'}."
    )
    channel_fact = (
        f"\n\n=== channel_dup_check 실측(결정론 자카드, 추측 금지) ===\n"
        f"양실장 채널 기존 영상과의 최대 제목 자카드 = {channel['max_jaccard']} "
        f"(임계 0.6, is_distinct={channel['is_distinct']}, 최유사 '{channel['most_similar_title'][:40]}'). "
        f"이 수치를 그대로 사용하라. {'통과' if channel['is_distinct'] else '0.6 초과 → 반드시 rejected'}."
    )
    user = (
        "다음 기획 초안을 eval 기준으로 검수하라.\n\n"
        f"=== 초안 ===\n{json.dumps(payload, ensure_ascii=False, indent=2)}\n\n"
        f"=== eval_scenarios ===\n{json.dumps(eval_spec, ensure_ascii=False, indent=2)}"
        f"{orig_fact}{channel_fact}"
    )
    return call(sys_p, user, temperature=0.2, max_tokens=1800)


# ── 산출물 기록 ────────────────────────────────────────────────────
def write_output(task_id: str, topic: str, payload: dict):
    OUTPUT_DIR.mkdir(exist_ok=True)
    today = date.today().isoformat()
    hashtags = " ".join(payload.get("hashtags", []))
    storyboard = "\n".join(f"{i+1}. {s}" for i, s in enumerate(payload.get("storyboard", [])))
    md = f"""---
title: "{payload.get('title', topic)}"
type: script
status: draft
ai_priority: high
created: {today}
updated: {today}
tags:
  - shorts
  - 승인대기
related:
  - "[[content-pd-agent context]]"
  - "[[바이럴 훅 3초 법칙]]"
---

# {payload.get('title', topic)}  `[승인대기]`

> task_id: {task_id} · 주제: {topic}

## 🎬 스크립트
{payload.get('script', '')}

## 🖼 스토리보드
{storyboard}

## 🎨 썸네일 프롬프트
{payload.get('thumbnail_prompt', '')}

## 🏷 해시태그
{hashtags}
"""
    out = OUTPUT_DIR / f"{task_id}.md"
    out.write_text(md, encoding="utf-8")
    return out


def append_log(line: str):
    """본문 첫 로그 항목 위에 삽입. 프론트매터(--- ... ---)는 건너뛴다.
    컨테이너 배포(번들)엔 볼트 log.md가 없으므로 graceful skip."""
    if not LOG.exists():
        return
    txt = load(LOG)
    body_start = 0
    if txt.startswith("---"):
        end = txt.find("\n---", 3)            # 닫는 프론트매터 구분자
        if end != -1:
            body_start = txt.find("\n", end + 1) + 1
    head, body = txt[:body_start], txt[body_start:]
    m = re.search(r"^- ", body, re.M)         # 본문 첫 불릿
    if m:
        i = m.start()
        body = body[:i] + f"- {line}\n" + body[i:]
    else:
        body = body.rstrip() + f"\n\n- {line}\n"
    LOG.write_text(head + body, encoding="utf-8")


# ── 오케스트레이션 메인 ────────────────────────────────────────────
def run(topic: str, on_step=None):
    task_id = ""  # emit 클로저에서 참조(발급 전 안전 기본값)

    def emit(stage, **data):
        if on_step:
            try:
                on_step({"stage": stage, "task_id": task_id, **data})
            except Exception as e:
                print(f"   [emit WARN] {stage} 콜백 실패 무시: {type(e).__name__}: {e}")

    if not API_KEY:
        if on_step:
            raise RuntimeError("BIZROUTER_API_KEY 미설정")  # server worker except가 error 이벤트로 변환
        sys.exit("[!] BIZROUTER_API_KEY 환경변수가 비어있다. export 후 재시도.")

    state = read_state()
    try:
        eval_spec = json.loads(load(EVAL_PATH))   # 검수 기준 — 부재/손상 시 명확한 에러(데모 무결성)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        raise RuntimeError(f"eval_scenarios.json 로드 실패({EVAL_PATH.name}): {e}")
    max_retries = state.get("max_retries", 3)
    kb = knowledge_digest()
    channel_titles = load_channel_titles()  # 카탈로그는 실행 중 불변 — 루프 밖 1회 로드

    # 0. Supervisor — task 발급
    task_id = next_task_id(state)
    state["current_task_id"] = task_id
    task = {
        "task_id": task_id, "topic": topic,
        "source_agent": "supervisor", "target_agent": "trend-analyst",
        "status": "pending_analysis", "retry_count": 0,
        "content_payload": {}, "wiki_references": [], "feedback_log": [],
    }
    state["tasks"].append(task)
    write_state(state)
    print(f"[Supervisor] {task_id} 발급 — 주제: {topic}")
    emit("supervisor", topic=topic)

    # 1. Trend Analyst (+ 실시간 트렌드 조사)
    print("[Trend] 실시간 트렌드 조사 중(Sonar)…")
    live = fetch_live_trends(topic)
    ch_topics = channel_top_topics(n=10)
    print(f"   [trend-live] {len(live['trends'])}건, 출처 {len(live['sources'])}개")
    emit("trend-live", trends=live["trends"], sources=live["sources"])
    print("[Trend Analyst] 키워드·훅 설계 중…")
    ta = agent_trend_analyst(topic, kb, ch_topics, live["trends"])
    task["content_payload"]["live_trends"] = live  # SSE·기록용
    keywords, hooks = _as_list(ta.get("keywords")), _as_list(ta.get("hooks"))  # LLM이 str 줘도 list 보장
    task["content_payload"].update(keywords=keywords, hooks=hooks)
    task["status"] = "drafting"
    write_state(state)
    print(f"   keywords={keywords}\n   hooks={hooks}")
    emit("trend-analyst", keywords=keywords, hooks=hooks)

    # 2~3. Creator ↔ Reviewer (Eval 루프)
    feedback = []
    while True:
        print(f"[Creator] 스크립트 작성 중… (retry={task['retry_count']})")
        emit("creator", retry=task["retry_count"])
        # 첫 회차는 창의(0.8), retry부터 감온(0.3) — 통과한 부분을 흔들지 않게 안정화(e2e 두더지잡기 차단).
        _cre_temp = 0.8 if task["retry_count"] == 0 else 0.3
        cre = agent_creator(topic, keywords, hooks, feedback, kb, temperature=_cre_temp)
        # LLM 필드 타입 정규화(list 기대 필드에 str/null 와도 메트릭·enumerate 깨짐 방지)
        cre["storyboard"] = _as_list(cre.get("storyboard"))
        cre["hashtags"] = _as_list(cre.get("hashtags"))
        cre["script"] = _as_str(cre.get("script"))
        cre["title"] = _as_str(cre.get("title"))
        cre["thumbnail_prompt"] = _as_str(cre.get("thumbnail_prompt"))

        # 결정론 길이 후처리: 100단어 미만이면 retry 소모 없이 '확장만' 시도(라이브 e2e: length_bounds
        # 단독 escalated 차단). originality 비악화 가드 — 확장본이 표절 임계를 넘기면 원본 유지(롤백).
        if len(cre["script"].split()) < 100:
            before = len(cre["script"].split())
            cand = expand_script(cre["script"], target=130, keywords=keywords,
                                 hook=pick_hook(hooks), max_passes=2)
            others = existing_scripts(exclude_task_id=task_id)
            cand_orig = originality_score(cand, others)
            if len(cand.split()) > before and cand_orig["is_original"]:   # 더 길고 표절 아닐 때만 채택
                cre["script"] = cand
            after = len(cre["script"].split())
            print(f"   [expand] 길이 후처리 {before}→{after}단어 (목표 130, retry 불소모, "
                  f"original={cand_orig['is_original']})")
            emit("creator-expand", before=before, after=after, target=130)

        task["content_payload"].update(cre)
        task["status"] = "pending_review"
        write_state(state)

        # originality_check: 메인이 결정론적으로 실측(LLM '가정' 대체)
        orig = originality_score(
            task["content_payload"].get("script", ""),
            existing_scripts(exclude_task_id=task_id),
        )
        task["content_payload"]["originality"] = orig
        print(f"   [originality] 최대 유사도 {orig['max_similarity']} "
              f"(임계 0.85, original={orig['is_original']})")

        # channel_dup_check: 채널 기존 영상 제목과 자카드 대조(결정론)
        channel = title_overlap_score(
            task["content_payload"].get("title", ""),
            channel_titles,
        )
        task["content_payload"]["channel_dup"] = channel
        print(f"   [channel-dup] 최대 자카드 {channel['max_jaccard']} "
              f"(임계 0.6, distinct={channel['is_distinct']}, ~ {channel['most_similar_title'][:30]})")

        # korean_syllable_density·hashtag_count: 결정론 실측(LLM 추측 대체)
        # 훅은 [0] 무조건이 아니라 21음절 이내 후보를 결정론 선택(e2e: 음절초과가 escalated 주범).
        hook0 = pick_hook(task["content_payload"].get("hooks") or [])
        density = script_density_score(hook0, task["content_payload"].get("script", ""))
        htag = hashtag_count_score(task["content_payload"].get("hashtags", []))
        task["content_payload"]["density"] = density
        task["content_payload"]["hashtag_check"] = htag
        print(f"   [density] 훅 {density['hook_syllables']}음절(ok={density['hook_ok']}), "
              f"본문 {density['script_syllables']}음절 | 해시태그 {htag['count']}개(ok={htag['ok']})")

        # length_bounds·keyword_inclusion: 결정론 실측(LLM 눈대중 대체 — 실측값 주입)
        wc = word_count_score(task["content_payload"].get("script", ""))
        kw = keyword_inclusion_score(task["content_payload"].get("script", ""), keywords)
        task["content_payload"]["word_count"] = wc
        task["content_payload"]["keyword_check"] = kw
        print(f"   [length] {wc['words']}단어(ok={wc['ok']}) | 키워드 {kw['included']}/{kw['total']}({kw['ratio']}, ok={kw['ok']})")

        # 팩트체크: 과장단정 패턴 + 수치주장 추출(결정론 — Reviewer가 채널 실제값과 대조)
        overclaim = overclaim_check(task["content_payload"].get("script", ""))
        num_claims = extract_numeric_claims(task["content_payload"].get("script", ""))
        task["content_payload"]["overclaim"] = overclaim
        task["content_payload"]["numeric_claims"] = num_claims
        print(f"   [factcheck] 과장단정 {'없음' if overclaim['ok'] else overclaim['flags']} | 수치주장 {num_claims}")
        emit("originality", max_similarity=orig["max_similarity"], is_original=orig["is_original"])
        emit("channel-dup", max_jaccard=channel["max_jaccard"], is_distinct=channel["is_distinct"])

        print("[Reviewer] Eval 검수 중…")
        rev = agent_reviewer(task["content_payload"], eval_spec, orig, channel)
        verdict = _as_str(rev.get("verdict")).strip().lower() or "rejected"  # null·비문자열 → 안전 기본 rejected
        for ch in _as_list(rev.get("checks")):                              # checks가 list 아니면 빈 순회
            if not isinstance(ch, dict):
                continue
            mark = "✅" if ch.get("pass") else "❌"
            print(f"   {mark} {ch.get('metric')}: {ch.get('comment','')}")
            emit("reviewer", metric=ch.get("metric"), passed=ch.get("pass"), comment=ch.get("comment", ""))

        # 결정론 강제 차단: 측정 가능한 위반(orig·channel·hook음절·해시태그·단어수·키워드)을 한 번에
        # 모아 반려. LLM verdict 변덕과 무관하게 코드가 강제(verdict-checks 모순 차단).
        block_reasons = deterministic_block(orig, channel, density, htag, wc, kw)
        rev["feedback"] = _as_list(rev.get("feedback"))  # LLM이 str/null 줘도 list 보장(extend·append 안전)
        if block_reasons and verdict == "approved":
            verdict = "rejected"
            rev["feedback"].extend(block_reasons)
            for r in block_reasons:
                print(f"   ⛔ 결정론 강제 반려: {r[:50]}")

        if verdict == "approved":
            task["status"] = "approved"
            task["token_usage"] = dict(token_usage)  # BizRouter usage 실측 누적
            task["cost_krw"] = round(cost_total, 4)
            write_state(state)
            out = write_output(task_id, topic, task["content_payload"])
            append_log(f"{date.today().isoformat()} — /pd '{topic}' → {task_id} 승인. "
                       f"output/{out.name} (비용 {cost_total:.3f}원)")
            print(f"\n✅ 승인 — {out}")
            print(f"   제목: {task['content_payload'].get('title')}")
            print(f"   누적 비용: {cost_total:.4f}원 | 토큰 {token_usage['total']} "
                  f"(in {token_usage['prompt']}/out {token_usage['completion']}, {token_usage['calls']}콜)")
            # 승인 즉시 Gamma 슬라이드 생성요청(블로킹 0 — 생성요청만, 폴링은 클라/프록시).
            # 실패해도 done payload는 그대로(graceful) — gamma 필드로만 상태 전달.
            gamma_info = gamma_generate(task["content_payload"], topic)
            print(f"   📊 Gamma: {gamma_info.get('status')}"
                  + (f" (id={gamma_info.get('id')})" if gamma_info.get("id")
                     else f" — {gamma_info.get('error', '')}"))
            emit("done", verdict="approved", title=task["content_payload"].get("title"),
                 payload=task["content_payload"], cost_krw=round(cost_total, 4),
                 token_usage=dict(token_usage), eval=_as_list(rev.get("checks")),
                 gamma=gamma_info)
            return

        # rejected — 이번 회차 사유를 기록하고, Creator엔 '누적' 제약을 넘긴다.
        # 직전 1회만 넘기면 A 고치다 통과했던 B를 깨는 두더지잡기로 3회 소진→에스컬레이션(e2e 확인).
        this_round = rev["feedback"]  # 위에서 _as_list로 정규화됨
        task["feedback_log"].append({"retry": task["retry_count"], "feedback": this_round})
        feedback = sorted(set(map(str, feedback)) | set(map(str, this_round)))  # 누적 합집합(중복 제거)
        task["retry_count"] += 1
        task["status"] = "rejected"
        write_state(state)
        print(f"   ↩ 반려(누적 {len(feedback)}건): {this_round}")
        emit("rejected", retry=task["retry_count"], feedback=this_round)

        if task["retry_count"] > max_retries:
            task["token_usage"] = dict(token_usage)
            task["cost_krw"] = round(cost_total, 4)
            write_state(state)
            append_log(f"{date.today().isoformat()} — /pd '{topic}' → {task_id} "
                       f"재시도 {max_retries}회 초과 에스컬레이션 (비용 {cost_total:.3f}원)")
            print(f"\n⚠ 재시도 {max_retries}회 초과 — 사용자 에스컬레이션. 중단.")
            print(f"   누적 비용: {cost_total:.4f}원 | 토큰 {token_usage['total']}")
            # 막다른 길 방지(UX): 마지막 초안·누적 반려·마지막 검수 실패항목을 함께 보낸다.
            last_checks = _as_list(rev.get("checks"))
            failed_metrics = [c.get("metric") for c in last_checks
                              if isinstance(c, dict) and not c.get("pass") and c.get("metric")]
            emit("escalated", verdict="escalated", max_retries=max_retries,
                 cost_krw=round(cost_total, 4), token_usage=dict(token_usage),
                 title=task["content_payload"].get("title"),
                 payload=task["content_payload"],          # 마지막(미승인) 초안 — 버리지 않고 노출
                 feedback_log=task["feedback_log"],         # 회차별 반려 사유 누적
                 failed_metrics=failed_metrics,             # 마지막 검수에서 떨어진 항목
                 eval=last_checks)
            return


if __name__ == "__main__":
    topic = " ".join(sys.argv[1:]).strip() or "개발 없이 5일 만에 수익 웹서비스 비법"
    run(topic)
