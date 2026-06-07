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
    choice = data["choices"][0]
    if choice.get("finish_reason") == "length":
        raise RuntimeError(
            f"응답이 max_tokens({max_tokens})에서 잘림 — 토큰 상향 필요. "
            f"completion_tokens={usage.get('completion_tokens')}"
        )
    return parse_json(choice["message"]["content"])


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
    if data["choices"][0].get("finish_reason") == "length":
        raise RuntimeError(
            f"Sonar 응답 잘림(max_tokens={max_tokens}) — 토큰 상향 필요. "
            f"completion_tokens={usage.get('completion_tokens')}"
        )
    msg = data["choices"][0]["message"]
    meta = msg.get("metadata") or {}
    raw_sources = meta.get("search_results") or []
    sources = [{"title": s.get("title") or s.get("url", ""), "url": s.get("url", "")} for s in raw_sources if s.get("url")]
    return msg.get("content", ""), sources


def parse_json(text: str) -> dict:
    """모델 출력에서 첫 JSON 객체를 견고하게 추출.
    코드펜스(```json), 선행 설명, 후행 여분텍스트('Extra data')를 모두 흡수한다.
    Sonar/flash-lite가 JSON 뒤에 산문을 덧붙이는 비결정 출력 방어(공개 배포 검증서 발견)."""
    s = text.strip()
    # 1) 코드펜스 제거: ```json ... ``` 또는 ``` ... ```
    fence = re.search(r"```(?:json)?\s*(.+?)\s*```", s, re.S)
    if fence:
        s = fence.group(1).strip()
    # 2) 그대로 시도
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        pass
    # 3) 첫 '{' 부터 raw_decode — 첫 유효 객체만 취하고 'Extra data' 후행 무시
    start = s.find("{")
    if start != -1:
        try:
            obj, _ = json.JSONDecoder().raw_decode(s[start:])
            return obj
        except json.JSONDecodeError:
            pass
    # 4) 최후: greedy 중괄호 매칭
    m = re.search(r"\{.*\}", s, re.S)
    if m:
        return json.loads(m.group(0))
    raise json.JSONDecodeError("JSON 객체를 찾지 못함", text, 0)


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


def keyword_inclusion_score(script: str, keywords: list, min_ratio: float = 0.8) -> dict:
    """타겟 키워드 본문 포함률 결정론 측정."""
    kws = keywords or []
    if not kws:
        return {"ratio": 0.0, "included": 0, "total": 0, "ok": False}
    s = script or ""
    inc = sum(1 for k in kws if k and k in s)
    ratio = inc / len(kws)
    return {"ratio": round(ratio, 3), "included": inc, "total": len(kws), "ok": ratio >= min_ratio}


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
    prompt = (
        f"최근 3개월 한국의 비개발자·바이브코딩·AI 노코드 창업 분야에서 실제로 화제가 된 "
        f"구체적 트렌드 키워드 5개를 웹에서 조사하라. 주제 '{topic}'와 연관되면 우선 포함하라. "
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


def deterministic_block(orig: dict, channel: dict, density: dict, htag: dict) -> list:
    """
    결정론 검사(originality·channel_dup·hook음절·해시태그) 위반 사유를 모두 모아 반환.
    위반이 여럿이면 모두 반환 — 한 회차에 모든 사유를 Creator에 통보(retry 낭비 방지).
    빈 리스트면 결정론 차단 없음.
    맥락무관 하드위반(hook≤21음절, 해시태그 1~5개)만 강제반려 — 본문 density 상한은
    맥락의존이라 Reviewer soft 판정으로 둔다(여기 추가하지 않음).
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
    return reasons


# ── State.json 입출력 ──────────────────────────────────────────────
def read_state() -> dict:
    return json.loads(load(STATE_PATH))


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
        '{"keywords": ["키워드 5개 내외"], "hooks": ["3초 훅 1~3개"]}'
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


def agent_creator(topic: str, keywords, hooks, feedback, kb: str) -> dict:
    sys_p = load_persona("creator") + (
        "\n\n## 출력 형식 (JSON만)\n"
        '{"title": "제목", "script": "쇼츠 스크립트 100~250단어", '
        '"storyboard": ["장면 단위 텍스트"], "thumbnail_prompt": "이미지 생성 프롬프트", '
        '"hashtags": ["#태그"]}'
    )
    fb = ""
    if feedback:
        fb = "\n\n=== 직전 반려 피드백(이것만 고쳐라) ===\n" + "\n".join(f"- {x}" for x in feedback)
    user = (
        f"주제: {topic}\n타겟 키워드: {keywords}\n채택 훅: {hooks}{fb}\n\n"
        f"=== 톤앤매너 근거(20-knowledge) ===\n{kb}"
    )
    return call(sys_p, user, temperature=0.8, max_tokens=1400)


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
    eval_spec = json.loads(load(EVAL_PATH))
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
    keywords, hooks = ta.get("keywords", []), ta.get("hooks", [])
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
        cre = agent_creator(topic, keywords, hooks, feedback, kb)
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
        hook0 = (task["content_payload"].get("hooks") or [""])[0]
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
        verdict = rev.get("verdict", "rejected")
        for ch in rev.get("checks", []):
            mark = "✅" if ch.get("pass") else "❌"
            print(f"   {mark} {ch.get('metric')}: {ch.get('comment','')}")
            emit("reviewer", metric=ch.get("metric"), passed=ch.get("pass"), comment=ch.get("comment", ""))

        # 결정론 강제 차단: originality·channel 위반 사유를 한 번에 모아 반려(retry 낭비 방지)
        block_reasons = deterministic_block(orig, channel, density, htag)
        if block_reasons and verdict == "approved":
            verdict = "rejected"
            rev.setdefault("feedback", []).extend(block_reasons)
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
            emit("done", verdict="approved", title=task["content_payload"].get("title"),
                 payload=task["content_payload"], cost_krw=round(cost_total, 4),
                 token_usage=dict(token_usage), eval=rev.get("checks", []))
            return

        # rejected
        feedback = rev.get("feedback", [])
        task["feedback_log"].append({"retry": task["retry_count"], "feedback": feedback})
        task["retry_count"] += 1
        task["status"] = "rejected"
        write_state(state)
        print(f"   ↩ 반려: {feedback}")
        emit("rejected", retry=task["retry_count"], feedback=feedback)

        if task["retry_count"] > max_retries:
            task["token_usage"] = dict(token_usage)
            task["cost_krw"] = round(cost_total, 4)
            write_state(state)
            append_log(f"{date.today().isoformat()} — /pd '{topic}' → {task_id} "
                       f"재시도 {max_retries}회 초과 에스컬레이션 (비용 {cost_total:.3f}원)")
            print(f"\n⚠ 재시도 {max_retries}회 초과 — 사용자 에스컬레이션. 중단.")
            print(f"   누적 비용: {cost_total:.4f}원 | 토큰 {token_usage['total']}")
            emit("escalated", verdict="escalated", max_retries=max_retries, cost_krw=round(cost_total, 4))
            return


if __name__ == "__main__":
    topic = " ".join(sys.argv[1:]).strip() or "개발 없이 5일 만에 수익 웹서비스 비법"
    run(topic)
