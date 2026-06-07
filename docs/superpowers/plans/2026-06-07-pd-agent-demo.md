# AI 콘텐츠 PD 에이전트 데모 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 양실장 바이브코딩대학 PD 채용 과제용 — 채널 중복 방지 + 실시간 트렌드(Perplexity Sonar) + 웹 실시간 구동 데모를 갖춘 4-에이전트 오케스트레이터를 Railway에 배포한다.

**Architecture:** 기존 `orchestrator.py`(BizRouter × gemini-2.5-flash-lite, 4-에이전트, 의존성 0)에 최소 침습으로 (A)채널 제목 자카드 중복검사 (C)Sonar 실시간 트렌드 주입 (B)`on_step` 콜백을 추가한다. `server.py`(표준 라이브러리 `http.server`)가 정적 페이지 서빙 + SSE로 단계 진행을 흘려보내고 API 키를 서버 환경변수에 격리한다. Railway에 Dockerfile로 배포.

**Tech Stack:** Python 3.12 표준 라이브러리만(urllib, http.server, json, difflib), 바닐라 JS/HTML/CSS, BizRouter API(gemini-2.5-flash-lite + perplexity/sonar), YouTube Data API v3, Railway + Docker.

**작업 순서:** A(채널 중복방지) → C(트렌드) → B(데모/배포). A·C는 백엔드 강화, B는 그 결과를 화면에 표시.

**공통 규칙:**
- 작업 디렉토리: `c:\Users\Admin\Desktop\바코\50-projects\content-pd-agent`
- 테스트 실행: `python -m pytest test_orchestrator.py -q` (기존 9건 + 신규). 직접 실행도 가능: `python test_orchestrator.py`
- 기존 회귀 9건은 **절대 깨지면 안 됨**. 매 태스크 후 전체 테스트 통과 확인.
- 의존성 0 유지(pip install 금지). 키는 환경변수로만.

---

## 작업 A — 채널 중복 방지

### Task A1: `title_overlap_score` — 제목 토큰 자카드 함수

**Files:**
- Modify: `50-projects/content-pd-agent/orchestrator.py` (originality_score 함수 뒤, ~158줄 이후)
- Test: `50-projects/content-pd-agent/test_orchestrator.py`

- [ ] **Step 1: 실패 테스트 작성** — `test_orchestrator.py`의 `test_extract_script` 함수(143줄) 뒤, `if __name__` 앞에 추가:

```python
def test_title_overlap_identical():
    """동일 주제(어순만 다름) = 자카드 1.0, is_distinct=False."""
    o = orc.title_overlap_score("AI로 비개발자가 만든 첫 앱", ["비개발자가 AI로 만든 첫 앱"])
    assert o["max_jaccard"] == 1.0, o
    assert o["is_distinct"] is False, o
    print("PASS test_title_overlap_identical")


def test_title_overlap_josa_strip():
    """한국어 조사 차이를 무시 — '웹서비스를' vs '웹서비스'."""
    o = orc.title_overlap_score("개발 없이 웹서비스를 만들기", ["개발 없이 웹서비스 만들기"])
    assert o["max_jaccard"] == 1.0, o
    print("PASS test_title_overlap_josa_strip")


def test_title_overlap_distinct():
    """완전히 다른 제목 = 낮은 자카드, is_distinct=True."""
    o = orc.title_overlap_score("주식 투자 초보 3원칙", ["AI로 첫 앱 만들기"])
    assert o["max_jaccard"] < 0.6, o
    assert o["is_distinct"] is True, o
    print("PASS test_title_overlap_distinct")


def test_title_overlap_empty_catalog():
    """카탈로그 비면 자카드 0, is_distinct=True (graceful)."""
    o = orc.title_overlap_score("아무 제목", [])
    assert o["max_jaccard"] == 0.0 and o["is_distinct"] is True, o
    print("PASS test_title_overlap_empty_catalog")
```

그리고 `if __name__ == "__main__":` 블록(146줄)의 `test_extract_script()` 뒤에 4줄 추가:

```python
    test_title_overlap_identical()
    test_title_overlap_josa_strip()
    test_title_overlap_distinct()
    test_title_overlap_empty_catalog()
```

마지막 print를 `"\n✅ ALL PASS (13 tests)"` 로 변경.

- [ ] **Step 2: 테스트 실패 확인**

Run: `python -m pytest test_orchestrator.py -q`
Expected: FAIL — `AttributeError: module 'orchestrator' has no attribute 'title_overlap_score'`

- [ ] **Step 3: 최소 구현** — `orchestrator.py`의 `originality_score` 함수 끝(157줄 `}` 다음 빈 줄) 뒤에 추가:

```python
# ── 채널 중복 검사 (제목 토큰 자카드 — difflib보다 어순/조사에 강건) ──
_JOSA = ("으로", "로", "은", "는", "이", "가", "을", "를", "의", "에", "에서", "와", "과", "도", "만")


def _title_tokens(title: str) -> set:
    """제목을 정규화 토큰 집합으로. 공백 split + 한국어 조사 꼬리 제거(형태소 분석기 미사용, 의존성 0)."""
    out = set()
    for raw in re.sub(r"[^\w가-힣\s]", " ", title or "").split():
        t = raw.strip().lower()
        for j in _JOSA:  # 긴 조사 우선
            if len(t) > len(j) + 1 and t.endswith(j):
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
        jac = len(a & b) / len(a | b)
        if jac > best:
            best, best_title = jac, t
    return {
        "max_jaccard": round(best, 4),
        "most_similar_title": best_title,
        "is_distinct": best < thresh,
    }
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest test_orchestrator.py -q`
Expected: PASS (13 passed)

- [ ] **Step 5: 커밋**

```bash
git add 50-projects/content-pd-agent/orchestrator.py 50-projects/content-pd-agent/test_orchestrator.py
git commit -m "feat(바코): 채널 제목 자카드 중복검사 title_overlap_score (A1)"
```

---

### Task A2: `load_channel_titles` — 카탈로그 로더 (graceful)

**Files:**
- Modify: `50-projects/content-pd-agent/orchestrator.py` (경로 상수부 ~26줄, 그리고 title_overlap_score 근처)
- Test: `50-projects/content-pd-agent/test_orchestrator.py`

- [ ] **Step 1: 실패 테스트 작성** — `test_orchestrator.py`에 추가(`test_title_overlap_empty_catalog` 뒤):

```python
def test_load_channel_titles_missing(tmp_path=None):
    """카탈로그 파일 없으면 빈 리스트 (graceful — 파이프라인 안 깨짐)."""
    import pathlib
    orig = orc.CATALOG_PATH
    orc.CATALOG_PATH = pathlib.Path("__definitely_not_exist__.json")
    try:
        assert orc.load_channel_titles() == [], "파일 부재 시 빈 리스트여야"
    finally:
        orc.CATALOG_PATH = orig
    print("PASS test_load_channel_titles_missing")


def test_load_channel_titles_reads():
    """카탈로그가 있으면 videos[].title 리스트 추출."""
    import pathlib, json as _json, tempfile, os
    fd, p = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    pathlib.Path(p).write_text(_json.dumps({"videos": [{"title": "영상1"}, {"title": "영상2"}]}), encoding="utf-8")
    orig = orc.CATALOG_PATH
    orc.CATALOG_PATH = pathlib.Path(p)
    try:
        assert orc.load_channel_titles() == ["영상1", "영상2"], orc.load_channel_titles()
    finally:
        orc.CATALOG_PATH = orig
        os.unlink(p)
    print("PASS test_load_channel_titles_reads")
```

`if __name__` 블록에 2줄 추가, 카운트 `(15 tests)`로:

```python
    test_load_channel_titles_missing()
    test_load_channel_titles_reads()
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `python -m pytest test_orchestrator.py -q`
Expected: FAIL — `AttributeError: ... has no attribute 'CATALOG_PATH'`

- [ ] **Step 3: 최소 구현** — `orchestrator.py` 경로 상수부, `OUTPUT_DIR = HERE / "output"` 줄(26) 바로 뒤에 추가:

```python
CATALOG_PATH = HERE / "channel_catalog.json"     # 양실장 채널 영상 카탈로그(중복검사·트렌드용)
```

그리고 `title_overlap_score` 함수 뒤에 추가:

```python
def load_channel_titles() -> list:
    """channel_catalog.json의 영상 제목 리스트. 파일 없으면 [] (graceful degrade)."""
    if not CATALOG_PATH.exists():
        return []
    try:
        data = json.loads(load(CATALOG_PATH))
    except (json.JSONDecodeError, OSError):
        return []
    return [v.get("title", "") for v in data.get("videos", []) if v.get("title")]
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest test_orchestrator.py -q`
Expected: PASS (15 passed)

- [ ] **Step 5: 커밋**

```bash
git add 50-projects/content-pd-agent/orchestrator.py 50-projects/content-pd-agent/test_orchestrator.py
git commit -m "feat(바코): 채널 카탈로그 로더 load_channel_titles graceful (A2)"
```

---

### Task A3: run()에 채널 중복검사 통합 + 강제 반려

**Files:**
- Modify: `50-projects/content-pd-agent/orchestrator.py` (run() originality 계산부 ~328-335, 강제반려부 ~344-350)
- Modify: `50-projects/content-pd-agent/eval_scenarios.json` (channel_dup_check 메트릭 추가)
- Modify: `50-projects/content-pd-agent/agent_reviewer` (~205-224, channel_fact 주입)

이 태스크는 LLM 호출이 얽혀 단위 테스트가 어렵다. **검증은 Task B 종단 데모에서 실제 /pd 1회로 한다.** 여기서는 코드 통합 + 기존 회귀 유지만 확인.

- [ ] **Step 1: eval_scenarios.json에 메트릭 추가** — `asserts` 배열의 `originality_check` 객체(25줄 `}`) 뒤에 콤마 후 추가:

```json
    {
      "metric": "channel_dup_check",
      "rule": "양실장 채널 기존 73개 영상 제목과 최대 토큰 자카드 0.6 미만 (채널 중복 방지). 메인이 title_overlap_score로 결정론 계산해 주입 — Reviewer는 추측 금지",
      "max_jaccard": 0.6,
      "source": "channel_catalog.json",
      "implementation": "orchestrator.title_overlap_score() — 결정론, 의존성 0. 임계 초과 시 메인이 강제 rejected",
      "on_fail": "채널에 이미 있는 주제. 채널이 안 다룬 새 앵글로 재작성 요망"
    },
```
(originality_check 객체 끝 `}` 뒤에 `,`를 붙이는 것 주의 — JSON 유효성)

- [ ] **Step 2: JSON 유효성 확인**

Run: `python -c "import json; json.load(open('eval_scenarios.json', encoding='utf-8')); print('JSON OK', len(json.load(open('eval_scenarios.json', encoding='utf-8'))['asserts']), 'metrics')"`
Expected: `JSON OK 9 metrics`

- [ ] **Step 3: run()에 채널검사 통합** — `orchestrator.py` run() 내 originality 계산 블록을 찾는다. 현재(328-335줄):

```python
        # originality_check: 메인이 결정론적으로 실측(LLM '가정' 대체)
        orig = originality_score(
            task["content_payload"].get("script", ""),
            existing_scripts(exclude_task_id=task_id),
        )
        task["content_payload"]["originality"] = orig
        print(f"   [originality] 최대 유사도 {orig['max_similarity']} "
              f"(임계 0.85, original={orig['is_original']})")
```

이 블록 **뒤에** 채널 중복검사 추가:

```python
        # channel_dup_check: 채널 기존 영상 제목과 자카드 대조(결정론)
        channel = title_overlap_score(
            task["content_payload"].get("title", ""),
            load_channel_titles(),
        )
        task["content_payload"]["channel_dup"] = channel
        print(f"   [channel-dup] 최대 자카드 {channel['max_jaccard']} "
              f"(임계 0.6, distinct={channel['is_distinct']}, ~ {channel['most_similar_title'][:30]})")
```

- [ ] **Step 4: 강제 반려에 OR 분기** — 현재 강제반려 블록(344-350줄):

```python
        # 결정론적 강제 차단: 유사도 임계 초과면 LLM 판정과 무관하게 rejected
        if not orig["is_original"] and verdict == "approved":
            verdict = "rejected"
            rev.setdefault("feedback", []).append(
                f"독창성 미달: 기존 기획안과 유사도 {orig['max_similarity']}(≥0.85). 새 앵글로 재작성."
            )
            print(f"   ⛔ originality 강제 반려 (유사도 {orig['max_similarity']})")
```

이 블록 **뒤에** (originality와 분리된 별도 사유) 추가:

```python
        # 결정론적 강제 차단: 채널 중복(제목 자카드 ≥0.6)이면 rejected
        if not channel["is_distinct"] and verdict == "approved":
            verdict = "rejected"
            rev.setdefault("feedback", []).append(
                f"채널 중복: 기존 채널 영상 '{channel['most_similar_title']}'와 제목 자카드 "
                f"{channel['max_jaccard']}(≥0.6). 채널이 안 다룬 새 앵글로 재작성."
            )
            print(f"   ⛔ channel-dup 강제 반려 (자카드 {channel['max_jaccard']})")
```

- [ ] **Step 5: agent_reviewer에 channel_fact 주입** — `agent_reviewer` 함수(205줄)의 시그니처를 `orig`에 더해 `channel`도 받도록 변경. 현재 시그니처(205줄):

```python
def agent_reviewer(payload: dict, eval_spec: dict, orig: dict) -> dict:
```

변경:

```python
def agent_reviewer(payload: dict, eval_spec: dict, orig: dict, channel: dict) -> dict:
```

`orig_fact` 문자열(212-217줄) 정의 뒤에 `channel_fact` 추가:

```python
    channel_fact = (
        f"\n\n=== channel_dup_check 실측(결정론 자카드, 추측 금지) ===\n"
        f"양실장 채널 기존 영상과의 최대 제목 자카드 = {channel['max_jaccard']} "
        f"(임계 0.6, is_distinct={channel['is_distinct']}, 최유사 '{channel['most_similar_title'][:40]}'). "
        f"이 수치를 그대로 사용하라. {'통과' if channel['is_distinct'] else '0.6 초과 → 반드시 rejected'}."
    )
```

`user` 변수의 `f"{orig_fact}"` 부분(223줄 근처)을 `f"{orig_fact}{channel_fact}"`로 변경.

- [ ] **Step 6: agent_reviewer 호출부 수정** — run() 내 호출(338줄): `rev = agent_reviewer(task["content_payload"], eval_spec, orig)` 를:

```python
        rev = agent_reviewer(task["content_payload"], eval_spec, orig, channel)
```

- [ ] **Step 7: 회귀 + 구문 확인**

Run: `python -m pytest test_orchestrator.py -q && python -c "import orchestrator; print('import OK')"`
Expected: PASS (15 passed) + `import OK`

- [ ] **Step 8: 커밋**

```bash
git add 50-projects/content-pd-agent/orchestrator.py 50-projects/content-pd-agent/eval_scenarios.json
git commit -m "feat(바코): run()에 채널 중복검사 통합 + 강제반려 + eval 메트릭 (A3)"
```

---

## 작업 C — 트렌드 에이전트

### Task C1: `call_text` — Sonar용 비-JSON 호출 (metadata 반환)

**Files:**
- Modify: `50-projects/content-pd-agent/orchestrator.py` (call 함수 ~37-87 근처, TREND_MODEL 상수 + call_text 추가)
- Test: `50-projects/content-pd-agent/test_orchestrator.py`

- [ ] **Step 1: 실패 테스트 작성** — `test_orchestrator.py`에 추가:

```python
def test_call_text_returns_content_and_sources():
    """call_text: json_object 없이 본문 + metadata.search_results 반환."""
    reset()
    payload = {
        "choices": [{"finish_reason": "stop", "message": {
            "content": "본문 텍스트",
            "metadata": {"search_results": [{"title": "출처1", "url": "https://a.com", "snippet": "s"}]},
        }}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15, "cost": 8.0},
    }
    orig = urllib.request.urlopen
    urllib.request.urlopen = fake_urlopen_factory(payload)
    try:
        text, sources = orc.call_text("물어봐", model=orc.TREND_MODEL)
    finally:
        urllib.request.urlopen = orig
    assert text == "본문 텍스트", text
    assert sources == [{"title": "출처1", "url": "https://a.com"}], sources
    print("PASS test_call_text_returns_content_and_sources")


def test_call_text_no_metadata():
    """metadata 없어도 빈 sources (graceful)."""
    reset()
    payload = {"choices": [{"finish_reason": "stop", "message": {"content": "x"}}],
               "usage": {"cost": 8.0}}
    orig = urllib.request.urlopen
    urllib.request.urlopen = fake_urlopen_factory(payload)
    try:
        text, sources = orc.call_text("q", model=orc.TREND_MODEL)
    finally:
        urllib.request.urlopen = orig
    assert text == "x" and sources == [], (text, sources)
    print("PASS test_call_text_no_metadata")
```

`if __name__` 블록에 2줄 + 카운트 `(17 tests)`:

```python
    test_call_text_returns_content_and_sources()
    test_call_text_no_metadata()
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `python -m pytest test_orchestrator.py -q`
Expected: FAIL — `AttributeError: ... 'TREND_MODEL'` 또는 `'call_text'`

- [ ] **Step 3: 구현** — `orchestrator.py` MODEL 상수(29줄) 뒤에 추가:

```python
TREND_MODEL = "perplexity/sonar"  # 실시간 트렌드 조사(웹검색 내장). json_object 미지원, 출처는 metadata.search_results
```

`parse_json` 함수(90줄) **앞에** `call_text` 추가:

```python
def call_text(user: str, model: str = TREND_MODEL, temperature: float = 0.2, max_tokens: int = 700):
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
    msg = data["choices"][0]["message"]
    meta = msg.get("metadata") or {}
    raw_sources = meta.get("search_results") or []
    sources = [{"title": s.get("title", ""), "url": s.get("url", "")} for s in raw_sources if s.get("url")]
    return msg.get("content", ""), sources
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest test_orchestrator.py -q`
Expected: PASS (17 passed)

- [ ] **Step 5: 커밋**

```bash
git add 50-projects/content-pd-agent/orchestrator.py 50-projects/content-pd-agent/test_orchestrator.py
git commit -m "feat(바코): Sonar용 call_text — 본문+출처 metadata 추출 (C1)"
```

---

### Task C2: `fetch_live_trends` + `channel_top_topics` + Trend Analyst 주입

**Files:**
- Modify: `50-projects/content-pd-agent/orchestrator.py` (신규 함수 2개 + agent_trend_analyst + run())
- Test: `50-projects/content-pd-agent/test_orchestrator.py`

- [ ] **Step 1: 실패 테스트 작성** — `test_orchestrator.py`에 추가:

```python
def test_channel_top_topics():
    """카탈로그 조회수 상위 N개 제목."""
    import pathlib, json as _json, tempfile, os
    fd, p = tempfile.mkstemp(suffix=".json"); os.close(fd)
    pathlib.Path(p).write_text(_json.dumps({"videos": [
        {"title": "낮은조회", "views": 10},
        {"title": "높은조회", "views": 1000},
        {"title": "중간조회", "views": 100},
    ]}), encoding="utf-8")
    orig = orc.CATALOG_PATH; orc.CATALOG_PATH = pathlib.Path(p)
    try:
        top = orc.channel_top_topics(n=2)
        assert top == ["높은조회", "중간조회"], top
    finally:
        orc.CATALOG_PATH = orig; os.unlink(p)
    print("PASS test_channel_top_topics")


def test_fetch_live_trends_graceful():
    """Sonar 실패 시 빈 결과 (파이프라인 안 깨짐)."""
    reset()
    def boom(req, timeout=60):
        raise RuntimeError("network down")
    orig = urllib.request.urlopen
    urllib.request.urlopen = boom
    try:
        out = orc.fetch_live_trends("주제")
    finally:
        urllib.request.urlopen = orig
    assert out == {"trends": [], "sources": []}, out
    print("PASS test_fetch_live_trends_graceful")


def test_fetch_live_trends_parses():
    """Sonar 정상 응답 파싱 — trends + sources."""
    reset()
    content = '{"trends":[{"keyword":"에이전틱 AI","why":"부상"}]}'
    payload = {"choices": [{"finish_reason": "stop", "message": {
        "content": content,
        "metadata": {"search_results": [{"title": "T", "url": "https://x.com"}]},
    }}], "usage": {"cost": 8.0}}
    orig = urllib.request.urlopen
    urllib.request.urlopen = fake_urlopen_factory(payload)
    try:
        out = orc.fetch_live_trends("주제")
    finally:
        urllib.request.urlopen = orig
    assert out["trends"] == [{"keyword": "에이전틱 AI", "why": "부상"}], out
    assert out["sources"] == [{"title": "T", "url": "https://x.com"}], out
    print("PASS test_fetch_live_trends_parses")
```

`if __name__` 블록에 3줄 + 카운트 `(20 tests)`:

```python
    test_channel_top_topics()
    test_fetch_live_trends_graceful()
    test_fetch_live_trends_parses()
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `python -m pytest test_orchestrator.py -q`
Expected: FAIL — `AttributeError: ... 'channel_top_topics'`

- [ ] **Step 3: 구현 — 신규 함수 2개** — `load_channel_titles` 함수 뒤에 추가:

```python
def channel_top_topics(n: int = 10) -> list:
    """카탈로그 조회수 상위 N개 영상 제목 — Trend Analyst가 '채널에서 먹힌 주제' 근거로 사용."""
    if not CATALOG_PATH.exists():
        return []
    try:
        data = json.loads(load(CATALOG_PATH))
    except (json.JSONDecodeError, OSError):
        return []
    vids = sorted(data.get("videos", []), key=lambda v: int(v.get("views", 0) or 0), reverse=True)
    return [v.get("title", "") for v in vids[:n] if v.get("title")]


def fetch_live_trends(topic: str) -> dict:
    """
    Perplexity Sonar로 실시간 LLM/바이브코딩 트렌드 조사. 출처 포함.
    반환: {trends:[{keyword,why}], sources:[{title,url}]}.
    실패/파싱오류 시 {trends:[], sources:[]} (graceful — 기획은 정적 지식·채널주제로 진행).
    """
    prompt = (
        f"2026년 한국 비개발자/바이브코딩 분야에서 지금 화제인 LLM·바이브코딩 트렌드 키워드 5개. "
        f"주제 '{topic}'와 연결되면 우선. 반드시 순수 JSON만 출력(설명·코드펜스 금지): "
        '{"trends":[{"keyword":"...","why":"한줄 근거"}]}'
    )
    try:
        text, sources = call_text(prompt, model=TREND_MODEL)
        parsed = parse_json(text)
        trends = parsed.get("trends", []) if isinstance(parsed, dict) else []
        return {"trends": trends, "sources": sources}
    except Exception:
        return {"trends": [], "sources": []}
```

- [ ] **Step 4: agent_trend_analyst 확장** — 현재(179-185줄):

```python
def agent_trend_analyst(topic: str, kb: str) -> dict:
    sys_p = load_persona("trend-analyst") + (
        "\n\n## 출력 형식 (JSON만)\n"
        '{"keywords": ["키워드 5개 내외"], "hooks": ["3초 훅 1~3개"]}'
    )
    user = f"주제: {topic}\n\n=== 참고 지식(20-knowledge) ===\n{kb}"
    return call(sys_p, user, temperature=0.8, max_tokens=600)
```

변경(채널주제 + 라이브트렌드 인자 추가):

```python
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
```

- [ ] **Step 5: run()에서 트렌드 조사 + 호출부 수정** — run() Trend Analyst 단계(311-313줄):

```python
    # 1. Trend Analyst
    print("[Trend Analyst] 키워드·훅 설계 중…")
    ta = agent_trend_analyst(topic, kb)
```

변경:

```python
    # 1. Trend Analyst (+ 실시간 트렌드 조사)
    print("[Trend] 실시간 트렌드 조사 중(Sonar)…")
    live = fetch_live_trends(topic)
    ch_topics = channel_top_topics(n=10)
    print(f"   [trend-live] {len(live['trends'])}건, 출처 {len(live['sources'])}개")
    print("[Trend Analyst] 키워드·훅 설계 중…")
    ta = agent_trend_analyst(topic, kb, ch_topics, live["trends"])
    task["content_payload"]["live_trends"] = live  # SSE·기록용
```

- [ ] **Step 6: 회귀 + 구문 확인**

Run: `python -m pytest test_orchestrator.py -q && python -c "import orchestrator; print('import OK')"`
Expected: PASS (20 passed) + `import OK`

- [ ] **Step 7: 커밋**

```bash
git add 50-projects/content-pd-agent/orchestrator.py 50-projects/content-pd-agent/test_orchestrator.py
git commit -m "feat(바코): 실시간 트렌드 fetch_live_trends + 채널주제 주입 (C2)"
```

---

## 작업 B — 데모 (콜백 + 서버 + UI + 배포)

### Task B1: orchestrator run()에 on_step 콜백 주입

**Files:**
- Modify: `50-projects/content-pd-agent/orchestrator.py` (run 시그니처 + emit 헬퍼 + 키부재 분기)
- Test: `50-projects/content-pd-agent/test_orchestrator.py`

- [ ] **Step 1: 실패 테스트 작성** — `test_orchestrator.py`에 추가:

```python
def test_emit_callback_no_op_when_none():
    """on_step 없으면 emit이 조용히 통과(기존 CLI 호환)."""
    # emit 헬퍼는 run 내부 클로저라 직접 테스트 불가 → run 시그니처 확인으로 대체
    import inspect
    sig = inspect.signature(orc.run)
    assert "on_step" in sig.parameters, "run에 on_step 파라미터 필요"
    assert sig.parameters["on_step"].default is None, "on_step 기본값 None이어야 CLI 호환"
    print("PASS test_emit_callback_no_op_when_none")
```

`if __name__` 블록에 1줄 + 카운트 `(21 tests)`:

```python
    test_emit_callback_no_op_when_none()
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `python -m pytest test_orchestrator.py -q`
Expected: FAIL — `AssertionError: run에 on_step 파라미터 필요`

- [ ] **Step 3: run 시그니처 + emit 헬퍼** — run() 정의(288줄) `def run(topic: str):` 를:

```python
def run(topic: str, on_step=None):
```

run() 본문 맨 앞(키 체크 전, 288줄 docstring/첫 줄)에 emit 헬퍼 추가. 현재 289-290줄:

```python
    if not API_KEY:
        sys.exit("[!] BIZROUTER_API_KEY 환경변수가 비어있다. export 후 재시도.")
```

변경(서버 경로는 sys.exit 대신 예외):

```python
    task_id = ""  # emit 클로저에서 참조(발급 전 안전 기본값)

    def emit(stage, **data):
        if on_step:
            on_step({"stage": stage, "task_id": task_id, **data})

    if not API_KEY:
        emit("error", reason="no_api_key")
        if on_step:
            raise RuntimeError("BIZROUTER_API_KEY 미설정")
        sys.exit("[!] BIZROUTER_API_KEY 환경변수가 비어있다. export 후 재시도.")
```

(주의: `task_id`는 298줄에서 `task_id = next_task_id(state)`로 재대입됨. emit이 클로저로 최신 값을 읽도록, 재대입 시 `nonlocal` 불필요 — 같은 스코프 지역변수이므로 자동 반영. 단 emit 함수 정의가 task_id 첫 대입보다 앞에 오므로 `task_id = ""` 기본값을 먼저 두는 것이 핵심.)

- [ ] **Step 4: 단계별 emit 호출 추가** — run() 내 각 단계 print 뒤에 emit 병행 추가:

Supervisor(308줄 print 뒤):
```python
    emit("supervisor", topic=topic)
```

Trend(C2에서 추가한 trend-live print 뒤):
```python
    emit("trend-live", trends=live["trends"], sources=live["sources"])
```

Trend Analyst 결과(317줄 print 뒤):
```python
    emit("trend-analyst", keywords=keywords, hooks=hooks)
```

Creator(322줄 print 뒤):
```python
        emit("creator", retry=task["retry_count"])
```

originality print 뒤(A3에서 추가한 channel-dup print 뒤):
```python
        emit("originality", max_similarity=orig["max_similarity"], is_original=orig["is_original"])
        emit("channel-dup", max_jaccard=channel["max_jaccard"], is_distinct=channel["is_distinct"])
```

Reviewer check 루프(340-342줄 `for ch in ...` 내부 print 뒤):
```python
            emit("reviewer", metric=ch.get("metric"), passed=ch.get("pass"), comment=ch.get("comment", ""))
```

approved(360-363줄 print들 뒤, return 전):
```python
            emit("done", verdict="approved", title=task["content_payload"].get("title"),
                 payload=task["content_payload"], cost_krw=round(cost_total, 4),
                 token_usage=dict(token_usage),
                 eval=rev.get("checks", []))
```

rejected(372줄 print 뒤):
```python
        emit("rejected", retry=task["retry_count"], feedback=feedback)
```

escalated(380-381줄 print 뒤, return 전):
```python
            emit("escalated", max_retries=max_retries, cost_krw=round(cost_total, 4))
```

- [ ] **Step 5: 회귀 + 구문 확인**

Run: `python -m pytest test_orchestrator.py -q && python -c "import orchestrator; print('import OK')"`
Expected: PASS (21 passed) + `import OK`

- [ ] **Step 6: 커밋**

```bash
git add 50-projects/content-pd-agent/orchestrator.py 50-projects/content-pd-agent/test_orchestrator.py
git commit -m "feat(바코): run()에 on_step SSE 콜백 주입 (B1)"
```

---

### Task B2: youtube_fetch.py — 카탈로그 갱신 스크립트

**Files:**
- Create: `50-projects/content-pd-agent/youtube_fetch.py`

검증은 채널 카탈로그가 이미 존재하므로 선택적. 재현성을 위해 스크립트화.

- [ ] **Step 1: 작성** — 새 파일 `youtube_fetch.py`:

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
양실장 바이브코딩대학 채널 영상 카탈로그 갱신 — channel_catalog.json 생성.
YouTube Data API v3, 표준 라이브러리만(의존성 0).

실행:  YOUTUBE_API_KEY=... python youtube_fetch.py
"""
import os, json, urllib.request
from pathlib import Path

KEY = os.environ.get("YOUTUBE_API_KEY", "")
HANDLE = "@VibecodingUniversity"
BASE = "https://www.googleapis.com/youtube/v3"
OUT = Path(__file__).resolve().parent / "channel_catalog.json"


def get(url):
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def main():
    if not KEY:
        raise SystemExit("[!] YOUTUBE_API_KEY 미설정")
    ch = get(f"{BASE}/channels?part=snippet,statistics,contentDetails&forHandle={HANDLE}&key={KEY}")
    item = ch["items"][0]
    uploads = item["contentDetails"]["relatedPlaylists"]["uploads"]
    title = item["snippet"]["title"]

    videos, page = [], ""
    while True:
        url = f"{BASE}/playlistItems?part=snippet,contentDetails&maxResults=50&playlistId={uploads}&key={KEY}"
        if page:
            url += f"&pageToken={page}"
        d = get(url)
        for it in d.get("items", []):
            sn = it["snippet"]
            videos.append({
                "video_id": it["contentDetails"]["videoId"],
                "title": sn["title"],
                "published": sn.get("publishedAt", "")[:10],
            })
        page = d.get("nextPageToken")
        if not page:
            break

    ids = [v["video_id"] for v in videos]
    for i in range(0, len(ids), 50):
        d = get(f"{BASE}/videos?part=statistics&id={','.join(ids[i:i+50])}&key={KEY}")
        stat = {it["id"]: int(it.get("statistics", {}).get("viewCount", 0) or 0) for it in d.get("items", [])}
        for v in videos:
            if v["video_id"] in stat:
                v["views"] = stat[v["video_id"]]

    videos.sort(key=lambda x: x["published"], reverse=True)
    cache = {
        "channel": title, "handle": HANDLE, "channel_id": item["id"],
        "fetched_count": len(videos), "videos": videos,
    }
    OUT.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"SAVED {OUT.name}: {len(videos)} videos")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 구문 확인** (네트워크 호출 없이 import만)

Run: `python -c "import ast; ast.parse(open('youtube_fetch.py', encoding='utf-8').read()); print('syntax OK')"`
Expected: `syntax OK`

- [ ] **Step 3: 커밋**

```bash
git add 50-projects/content-pd-agent/youtube_fetch.py
git commit -m "feat(바코): YouTube 카탈로그 갱신 스크립트 youtube_fetch.py (B2)"
```

---

### Task B3: server.py — http.server SSE + 정적 서빙 + 폴백

**Files:**
- Create: `50-projects/content-pd-agent/server.py`
- Test: `50-projects/content-pd-agent/test_server.py`

- [ ] **Step 1: 실패 테스트 작성** — 새 파일 `test_server.py`:

```python
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
    # 002는 없으므로 최소 1건 이상, 각 항목에 title·script 키
    for s in samples:
        assert "title" in s and "script" in s, s
    print(f"PASS test_load_samples ({len(samples)} samples)")


if __name__ == "__main__":
    test_sse_format()
    test_load_samples()
    print("\n✅ ALL PASS (server: 2 tests)")
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `python -m pytest test_server.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'server'`

- [ ] **Step 3: server.py 작성** — 새 파일:

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI 콘텐츠 PD 에이전트 — 웹 데모 서버.
표준 라이브러리 http.server만(의존성 0). 정적 페이지 + /api/pd SSE + /api/samples 폴백.
API 키는 서버 환경변수에서만 읽어 브라우저 노출 0.

실행:  BIZROUTER_API_KEY=... python server.py     (PORT 환경변수 또는 8000)
"""
import os, re, json, queue, threading, traceback
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import orchestrator as orc

HERE = Path(__file__).resolve().parent
WEB = HERE / "web"
OUTPUT = HERE / "output"
PORT = int(os.environ.get("PORT", 8000))

# 데모 동시성: 모델 호출 직렬화(전역 cost_total/State 레이스 회피)
_run_lock = threading.Lock()


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
        if path == "/api/health":
            self._send(200, "application/json", b'{"ok":true}')
            return
        self._send(404, "text/plain", b"not found")

    def do_POST(self):
        if self.path.split("?", 1)[0] != "/api/pd":
            self._send(404, "text/plain", b"not found")
            return
        length = int(self.headers.get("Content-Length", 0))
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
            try:
                with _run_lock:  # 직렬화: 전역 cost/State 레이스 회피
                    orc.run(topic, on_step=on_step)
            except Exception as e:
                q.put({"stage": "error", "reason": str(e)[:200], "trace": traceback.format_exc()[:300]})
            finally:
                q.put(SENTINEL)

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
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest test_server.py -q`
Expected: PASS (2 passed)

- [ ] **Step 5: 커밋**

```bash
git add 50-projects/content-pd-agent/server.py 50-projects/content-pd-agent/test_server.py
git commit -m "feat(바코): http.server SSE 데모 서버 + 폴백 + 키격리 (B3)"
```

---

### Task B4: web/index.html — 데모 UI

**Files:**
- Create: `50-projects/content-pd-agent/web/index.html`

UI는 시각 검증이 필요하므로 종단(B6)에서 브라우저로 확인. 여기서는 파일 생성 + 정적 서빙 확인.

- [ ] **Step 1: 작성** — 새 파일 `web/index.html` (바닐라 JS, fetch+ReadableStream으로 SSE 수신, 인라인 CSS):

```html
<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AI 콘텐츠 PD 에이전트 — 양실장 바이브코딩대학</title>
<style>
  :root { --bg:#0d1117; --card:#161b22; --bd:#30363d; --fg:#e6edf3; --mut:#8b949e; --ok:#3fb950; --no:#f85149; --ac:#58a6ff; }
  * { box-sizing:border-box; }
  body { margin:0; background:var(--bg); color:var(--fg); font-family:'Pretendard',-apple-system,system-ui,sans-serif; line-height:1.6; }
  .wrap { max-width:880px; margin:0 auto; padding:32px 20px 80px; }
  h1 { font-size:24px; margin:0 0 4px; }
  .sub { color:var(--mut); margin:0 0 24px; font-size:14px; }
  .card { background:var(--card); border:1px solid var(--bd); border-radius:12px; padding:20px; margin:16px 0; }
  .inrow { display:flex; gap:8px; }
  input { flex:1; background:#0d1117; border:1px solid var(--bd); border-radius:8px; color:var(--fg); padding:12px; font-size:15px; }
  button { background:var(--ac); color:#fff; border:0; border-radius:8px; padding:12px 20px; font-size:15px; font-weight:600; cursor:pointer; }
  button:disabled { opacity:.5; cursor:wait; }
  .chips { display:flex; gap:6px; flex-wrap:wrap; margin-top:10px; }
  .chip { background:#21262d; border:1px solid var(--bd); border-radius:16px; padding:4px 12px; font-size:13px; color:var(--mut); cursor:pointer; }
  .step { display:flex; align-items:center; gap:10px; padding:6px 0; color:var(--mut); }
  .step.active { color:var(--fg); } .step.done { color:var(--ok); }
  .dot { width:18px; height:18px; border-radius:50%; border:2px solid var(--bd); flex:none; }
  .step.active .dot { border-color:var(--ac); } .step.done .dot { background:var(--ok); border-color:var(--ok); }
  .trend { font-size:13px; padding:8px 0; border-bottom:1px solid var(--bd); }
  .trend b { color:var(--ac); } .trend a { color:var(--mut); font-size:12px; }
  table { width:100%; border-collapse:collapse; font-size:13px; }
  td, th { text-align:left; padding:6px 8px; border-bottom:1px solid var(--bd); vertical-align:top; }
  .pass { color:var(--ok); } .fail { color:var(--no); }
  .badge { display:inline-block; background:#1f6feb33; color:var(--ac); border:1px solid var(--ac); border-radius:6px; padding:2px 8px; font-size:12px; }
  .script { white-space:pre-wrap; background:#0d1117; border-radius:8px; padding:14px; font-size:14px; }
  .muted { color:var(--mut); font-size:13px; }
  .hidden { display:none; }
  .arch { display:grid; grid-template-columns:1fr 1fr; gap:10px; }
  .arch .a { background:#0d1117; border:1px solid var(--bd); border-radius:8px; padding:10px; font-size:13px; }
</style>
</head>
<body>
<div class="wrap">
  <h1>🎬 AI 콘텐츠 PD 에이전트</h1>
  <p class="sub">양실장의 바이브코딩대학 · 4-에이전트 오케스트레이션 · 채널 73개 영상 중복검사 + 실시간 트렌드(Sonar)</p>

  <div class="card">
    <div class="inrow">
      <input id="topic" placeholder="쇼츠 주제를 입력하세요 (예: AI로 사장님 매출 올리는 법)">
      <button id="go">기획 생성</button>
    </div>
    <div class="chips" id="chips"></div>
  </div>

  <div class="card hidden" id="progress">
    <div id="steps"></div>
  </div>

  <div class="card hidden" id="trendPanel">
    <b>📈 실시간 트렌드 (Perplexity Sonar)</b>
    <div id="trends"></div>
  </div>

  <div class="card hidden" id="result">
    <h2 id="rTitle"></h2>
    <p><span class="badge">승인대기</span> <span class="muted" id="rCost"></span></p>
    <h3>🎬 스크립트</h3><div class="script" id="rScript"></div>
    <h3>🏷 해시태그</h3><div class="muted" id="rTags"></div>
  </div>

  <div class="card hidden" id="evalPanel">
    <b>✅ 검수표 (Eval 8종 + 채널 중복)</b>
    <table id="evalTable"><tbody></tbody></table>
  </div>

  <div class="card">
    <b>🏗 아키텍처</b>
    <div class="arch" style="margin-top:10px">
      <div class="a"><b>Supervisor</b><br>주제 분해·라우팅 (창작 안 함)</div>
      <div class="a"><b>Trend Analyst</b> · temp 0.8<br>채널주제+Sonar 트렌드→키워드·3초훅</div>
      <div class="a"><b>Creator</b> · temp 0.8<br>스크립트·스토리보드·썸네일</div>
      <div class="a"><b>Reviewer</b> · temp 0.2<br>Eval 8종+채널중복 판정</div>
    </div>
    <p class="muted" style="margin-top:12px">
      flash-lite 단일모델(호출당 ~0.05원) · originality·채널중복 코드 실측 주입(LLM 추측 아님) ·
      한국 표시광고법·뒷광고 규제 차단 · 트렌드는 Sonar 실시간 웹검색(출처 포함)
    </p>
  </div>
</div>

<script>
const $ = s => document.querySelector(s);
const STEPS = [["supervisor","Supervisor"],["trend-live","트렌드 조사"],["trend-analyst","Trend Analyst"],["creator","Creator"],["reviewer","Reviewer"]];
const SAMPLE_CHIPS = ["AI로 사장님 매출 올리는 법","비개발자가 알아야 할 백엔드 한 가지","노코드로 만드는 첫 자동화"];

function renderChips(){ $("#chips").innerHTML = SAMPLE_CHIPS.map(c=>`<span class="chip">${c}</span>`).join(""); 
  document.querySelectorAll(".chip").forEach(el=>el.onclick=()=>{ $("#topic").value=el.textContent; }); }
function renderSteps(){ $("#steps").innerHTML = STEPS.map(([k,l])=>`<div class="step" data-k="${k}"><span class="dot"></span>${l}</div>`).join(""); }
function setStep(k, state){ const el=$(`.step[data-k="${k}"]`); if(el){ el.classList.remove("active","done"); el.classList.add(state);} }

async function run(topic){
  $("#go").disabled=true;
  ["#progress","#trendPanel","#result","#evalPanel"].forEach(s=>$(s).classList.add("hidden"));
  $("#progress").classList.remove("hidden"); renderSteps();
  $("#evalTable").querySelector("tbody").innerHTML="";
  const evalRows = {};

  const res = await fetch("/api/pd",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({topic})});
  const reader = res.body.getReader(); const dec = new TextDecoder(); let buf="";
  while(true){
    const {value,done} = await reader.read(); if(done) break;
    buf += dec.decode(value,{stream:true});
    const parts = buf.split("\n\n"); buf = parts.pop();
    for(const p of parts){
      const ev = (p.match(/^event: (.+)$/m)||[])[1];
      const dm = p.match(/^data: (.+)$/m); if(!dm) continue;
      const d = JSON.parse(dm[1]); handle(ev, d, evalRows);
    }
  }
  $("#go").disabled=false;
}

function handle(ev, d, evalRows){
  const stage = d.stage;
  if(stage==="supervisor"){ setStep("supervisor","done"); setStep("trend-live","active"); }
  else if(stage==="trend-live"){ setStep("trend-live","done"); setStep("trend-analyst","active");
    if(d.trends && d.trends.length){ $("#trendPanel").classList.remove("hidden");
      $("#trends").innerHTML = d.trends.map(t=>`<div class="trend"><b>${t.keyword}</b> — ${t.why}</div>`).join("") +
        (d.sources&&d.sources.length? `<div class="trend">출처: ${d.sources.map(s=>`<a href="${s.url}" target="_blank">${s.title}</a>`).join(" · ")}</div>`:""); } }
  else if(stage==="trend-analyst"){ setStep("trend-analyst","done"); setStep("creator","active"); }
  else if(stage==="creator"){ setStep("creator","active"); setStep("reviewer","active"); }
  else if(stage==="reviewer"){ const tb=$("#evalTable").querySelector("tbody");
    if(!evalRows[d.metric]){ const tr=document.createElement("tr"); evalRows[d.metric]=tr; tb.appendChild(tr); }
    evalRows[d.metric].innerHTML = `<td>${d.metric}</td><td class="${d.passed?'pass':'fail'}">${d.passed?'✅':'❌'}</td><td class="muted">${d.comment||''}</td>`;
    $("#evalPanel").classList.remove("hidden"); }
  else if(stage==="done"){ STEPS.forEach(([k])=>setStep(k,"done"));
    const p=d.payload||{};
    $("#result").classList.remove("hidden");
    $("#rTitle").textContent = d.title || p.title || "";
    $("#rScript").textContent = p.script || "";
    $("#rTags").textContent = (p.hashtags||[]).join(" ");
    $("#rCost").textContent = `비용 ${d.cost_krw}원 · 토큰 ${(d.token_usage||{}).total||0} · ${d.verdict==="escalated"?"검수 미달(반려)":"승인"}`; }
  else if(stage==="error"){ alert("에러: "+(d.reason||"unknown")); loadSamples(); }
}

async function loadSamples(){
  const s = await (await fetch("/api/samples")).json();
  if(!s.length) return;
  $("#result").classList.remove("hidden");
  $("#rTitle").textContent = "[샘플] "+s[0].title;
  $("#rScript").textContent = s[0].script;
  $("#rTags").textContent = s[0].hashtags;
  $("#rCost").textContent = `사전 생성 샘플 ${s.length}건 · API 키 없거나 오류 시 폴백`;
}

renderChips();
$("#go").onclick = ()=>{ const t=$("#topic").value.trim(); if(t) run(t); };
$("#topic").addEventListener("keydown", e=>{ if(e.key==="Enter") $("#go").click(); });
</script>
</body>
</html>
```

- [ ] **Step 2: HTML 존재 + 서버 정적 서빙 확인** (서버를 백그라운드로 잠깐 띄워 확인하지 말고 파일 존재만)

Run: `python -c "from pathlib import Path; assert Path('web/index.html').stat().st_size > 2000; print('html OK')"`
Expected: `html OK`

- [ ] **Step 3: 커밋**

```bash
git add 50-projects/content-pd-agent/web/index.html
git commit -m "feat(바코): 데모 UI index.html — SSE 단계표시+트렌드+검수표+아키텍처 (B4)"
```

---

### Task B5: Dockerfile + railway.json + README

**Files:**
- Create: `50-projects/content-pd-agent/Dockerfile`
- Create: `50-projects/content-pd-agent/railway.json`
- Create: `50-projects/content-pd-agent/README.md`

- [ ] **Step 1: Dockerfile 작성** — 새 파일 `Dockerfile`:

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY . .
# 의존성 0 — pip install 없음. PORT는 Railway가 주입(코드에서 os.environ 읽음).
CMD python server.py
```

- [ ] **Step 2: railway.json 작성** — 새 파일 `railway.json`:

```json
{
  "$schema": "https://railway.com/railway.schema.json",
  "build": { "builder": "DOCKERFILE", "dockerfilePath": "./Dockerfile" },
  "deploy": { "startCommand": "python server.py", "healthcheckPath": "/api/health", "restartPolicyType": "ON_FAILURE" }
}
```

- [ ] **Step 3: README 작성** — 새 파일 `README.md`:

```markdown
# AI 콘텐츠 PD 에이전트 — 데모

양실장의 바이브코딩대학 PD 채용 과제. 4-에이전트 오케스트레이션으로 쇼츠 기획안을 실시간 생성한다.

## 핵심
- **4-에이전트:** Supervisor → Trend Analyst → Creator → Reviewer (BizRouter × gemini-2.5-flash-lite 단일 모델, 온도 차등)
- **채널 중복 방지:** 채널 73개 영상 제목과 토큰 자카드 대조 → 중복이면 강제 반려
- **실시간 트렌드:** Perplexity Sonar로 LLM/바이브코딩 최신 트렌드 + 출처 주입
- **Eval 8종:** 길이·키워드·독창성·양식·보안·한국수익규제·훅·완주율 전부 통과해야 승인
- **의존성 0:** 표준 라이브러리만(urllib, http.server, difflib)

## 로컬 실행
```bash
export BIZROUTER_API_KEY="sk-br-..."
export YOUTUBE_API_KEY="AIza..."   # 카탈로그 갱신 시에만(이미 channel_catalog.json 있음)
python server.py                    # http://localhost:8000
```

## 배포 (Railway)
1. 이 디렉토리를 Railway 서비스로 연결(Dockerfile 자동 감지).
2. Variables 탭에 `BIZROUTER_API_KEY` 등록(`YOUTUBE_API_KEY`는 카탈로그 재생성 시에만).
3. 배포 후 공개 URL 접속.

## 카탈로그 갱신
```bash
YOUTUBE_API_KEY=... python youtube_fetch.py   # channel_catalog.json 재생성
```

## 테스트
```bash
python -m pytest test_orchestrator.py test_server.py -q
```
```

- [ ] **Step 4: 커밋**

```bash
git add 50-projects/content-pd-agent/Dockerfile 50-projects/content-pd-agent/railway.json 50-projects/content-pd-agent/README.md
git commit -m "feat(바코): Railway 배포 설정 Dockerfile/railway.json + README (B5)"
```

---

### Task B6: 종단 검증 — 로컬 실제 구동 (A·C·B 통합)

**Files:** 없음(검증 전용)

이 태스크가 **A3·C2의 LLM 통합을 실제로 검증**한다. API 키 필요.

- [ ] **Step 1: 전체 단위 테스트**

Run: `python -m pytest test_orchestrator.py test_server.py -q`
Expected: PASS (orchestrator 21 + server 2)

- [ ] **Step 2: 서버 백그라운드 기동**

Run: `BIZROUTER_API_KEY="<키>" python server.py` (백그라운드)
Expected: `PD 에이전트 데모 서버 — http://0.0.0.0:8000`

- [ ] **Step 3: 채널 중복 강제 반려 검증** — 채널에 이미 있는 주제로 SSE 호출:

Run:
```bash
curl -N -X POST http://localhost:8000/api/pd -H "Content-Type: application/json" \
  -d '{"topic":"개발 없이 5일 만에 수익 웹서비스 만드는 비법"}' | head -40
```
Expected: SSE 스트림에 `event: step` `"stage":"channel-dup"`이 `"is_distinct":false` 또는 reviewer 단계에서 channel_dup 반려 → retry 발생. (채널 영상과 제목 자카드 ≥0.6이면 강제 반려)

- [ ] **Step 4: 정상 신규 주제 종단 검증** — 채널이 안 다룬 주제:

Run:
```bash
curl -N -X POST http://localhost:8000/api/pd -H "Content-Type: application/json" \
  -d '{"topic":"AI로 동네 카페 단골 만드는 인스타 자동화"}' | tail -20
```
Expected: SSE 마지막에 `event: done` `"verdict":"approved"`, payload에 script·hashtags, cost_krw에 Sonar(~8원)+flash-lite 합산. trend-live 이벤트에 trends·sources 포함.

- [ ] **Step 5: 브라우저 시각 확인** — `http://localhost:8000` 접속:
  - 주제 입력 → 단계바 진행(Supervisor→트렌드→Analyst→Creator→Reviewer)
  - 실시간 트렌드 패널에 키워드 + 출처 링크 표시
  - 결과 카드(제목·스크립트·해시태그·[승인대기] 뱃지)
  - 검수표에 Eval 메트릭 ✅/❌
  - 비용 표시

스크린샷은 `step_archive/` 또는 프로젝트 루트에 저장(`.claude/`·`90-assets/` 금지).

- [ ] **Step 6: 서버 종료 + 폴백 검증** — 키 없이 기동해 폴백 확인:

Run: `python server.py` (키 없이) → 브라우저에서 주제 생성 시도
Expected: error 이벤트 → `/api/samples` 폴백으로 샘플 5건 중 1건 표시(빈 화면 안 됨).

- [ ] **Step 7: 최종 커밋(검증 산출물 있으면)**

```bash
git add -A 50-projects/content-pd-agent/
git commit -m "test(바코): 데모 종단 검증 — 채널중복 반려·트렌드·SSE 동작 확인 (B6)" || echo "변경 없음"
```

---

## Self-Review 체크리스트 (작성자 확인 완료)

**Spec 커버리지:**
- 작업 A(채널 중복) → A1(자카드)·A2(로더)·A3(통합) ✅
- 작업 C(트렌드) → C1(call_text)·C2(fetch_live_trends+주입) ✅
- 작업 B(데모) → B1(콜백)·B2(youtube_fetch)·B3(server)·B4(UI)·B5(배포)·B6(종단) ✅
- 샘플 폴백 5건(002 없음) → B3 load_samples·B4 loadSamples ✅
- 의존성 0 → 전 태스크 표준 라이브러리만 ✅
- 키 격리 → B3 환경변수, B5 Railway Variables ✅
- graceful(카탈로그·Sonar 부재) → A2·C2 빈 결과 반환 ✅
- 가짜 인용 금지 → C1 실제 출처만, C2 "거론분만/단정 금지" ✅

**타입 일관성:**
- `title_overlap_score` → {max_jaccard, most_similar_title, is_distinct} (A1·A3·C 일관)
- `fetch_live_trends` → {trends, sources} (C2·B1·B4 일관)
- `call_text` → (content, sources) 튜플 (C1·C2 일관)
- `agent_reviewer(payload, eval_spec, orig, channel)` (A3 시그니처·호출부 일관)
- `agent_trend_analyst(topic, kb, channel_topics, live_trends)` (C2 시그니처·호출부 일관)
- SSE stage 값: supervisor/trend-live/trend-analyst/creator/originality/channel-dup/reviewer/done/rejected/escalated/error (B1 emit·B4 handle 일관)

**Placeholder 스캔:** 모든 코드 스텝에 실제 코드 포함, TBD/TODO 없음 ✅
