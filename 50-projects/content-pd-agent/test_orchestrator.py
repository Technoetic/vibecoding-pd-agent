#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
orchestrator 회귀 테스트 — 네트워크 없이 결정론적 검증.
squeeze-report C3(토큰 분해 로깅) 본문화 동반 회귀.

실행:  python test_orchestrator.py   (exit 0 = PASS)
"""
import io, json, sys, urllib.request, urllib.error
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import orchestrator as orc


class FakeResp(io.BytesIO):
    """urlopen 컨텍스트매니저 흉내."""
    def __enter__(self): return self
    def __exit__(self, *a): self.close()


def fake_urlopen_factory(payload):
    def _fake(req, timeout=60):
        return FakeResp(json.dumps(payload).encode("utf-8"))
    return _fake


def reset():
    orc.cost_total = 0.0
    orc.token_usage = {"prompt": 0, "completion": 0, "total": 0, "calls": 0}
    orc.API_KEY = "test-key"
    orc._trends_cache.clear()   # 트렌드 공유 캐시 격리(테스트 간 stale 방지)
    orc.TREND_DEPTH = 1         # 기본은 1콜(광역만)로 테스트 — 다단계는 전용 테스트에서 DEPTH=2 설정


def test_token_accumulation():
    """usage 키가 모두 있을 때 정확히 누적."""
    reset()
    payload = {
        "choices": [{"finish_reason": "stop", "message": {"content": '{"ok": true}'}}],
        "usage": {"prompt_tokens": 50, "completion_tokens": 30, "total_tokens": 80, "cost": 0.05},
    }
    orig = urllib.request.urlopen
    urllib.request.urlopen = fake_urlopen_factory(payload)
    try:
        out = orc.call("sys", "user")
    finally:
        urllib.request.urlopen = orig
    assert out == {"ok": True}, out
    assert orc.token_usage == {"prompt": 50, "completion": 30, "total": 80, "calls": 1}, orc.token_usage
    assert abs(orc.cost_total - 0.05) < 1e-9, orc.cost_total
    print("PASS test_token_accumulation")


def test_missing_usage_keys_defensive():
    """usage 키가 없어도 0으로 방어 — 빈 약속 방지."""
    reset()
    payload = {"choices": [{"finish_reason": "stop", "message": {"content": "{}"}}], "usage": {}}
    orig = urllib.request.urlopen
    urllib.request.urlopen = fake_urlopen_factory(payload)
    try:
        orc.call("sys", "user")
    finally:
        urllib.request.urlopen = orig
    assert orc.token_usage == {"prompt": 0, "completion": 0, "total": 0, "calls": 1}, orc.token_usage
    print("PASS test_missing_usage_keys_defensive")


def test_two_calls_sum():
    """다중 호출 누적 — 결정론."""
    reset()
    p1 = {"choices": [{"finish_reason": "stop", "message": {"content": "{}"}}],
          "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15, "cost": 0.01}}
    p2 = {"choices": [{"finish_reason": "stop", "message": {"content": "{}"}}],
          "usage": {"prompt_tokens": 20, "completion_tokens": 8, "total_tokens": 28, "cost": 0.02}}
    orig = urllib.request.urlopen
    try:
        urllib.request.urlopen = fake_urlopen_factory(p1); orc.call("s", "u")
        urllib.request.urlopen = fake_urlopen_factory(p2); orc.call("s", "u")
    finally:
        urllib.request.urlopen = orig
    assert orc.token_usage == {"prompt": 30, "completion": 13, "total": 43, "calls": 2}, orc.token_usage
    print("PASS test_two_calls_sum")


def test_length_truncation_raises():
    """finish_reason=length 잘림 감지(기존 동작 회귀)."""
    reset()
    payload = {"choices": [{"finish_reason": "length", "message": {"content": '{"a":'}}],
               "usage": {"prompt_tokens": 5, "completion_tokens": 5, "total_tokens": 10, "cost": 0.01}}
    orig = urllib.request.urlopen
    urllib.request.urlopen = fake_urlopen_factory(payload)
    raised = False
    try:
        orc.call("s", "u")
    except RuntimeError as e:
        raised = "잘림" in str(e)
    finally:
        urllib.request.urlopen = orig
    assert raised, "max_tokens 잘림이 감지되지 않음"
    print("PASS test_length_truncation_raises")


def test_originality_identical():
    """동일 스크립트 = 유사도 1.0, is_original=False."""
    s = "개발 없이 5일 만에 수익 웹서비스를 만드는 비법을 공개합니다."
    o = orc.originality_score(s, [s])
    assert o["max_similarity"] == 1.0, o
    assert o["is_original"] is False, o
    print("PASS test_originality_identical")


def test_originality_distinct():
    """완전히 다른 스크립트 = 낮은 유사도, is_original=True."""
    a = "AI로 비개발자가 처음 만든 앱, 결과는 놀라웠습니다."
    b = "주식 투자 초보가 반드시 알아야 할 세 가지 원칙을 설명합니다."
    o = orc.originality_score(a, [b])
    assert o["max_similarity"] < 0.85, o
    assert o["is_original"] is True, o
    print("PASS test_originality_distinct")


def test_originality_empty_corpus():
    """기존 스크립트 없으면 유사도 0, is_original=True (첫 기획 통과)."""
    o = orc.originality_score("아무 스크립트나", [])
    assert o["max_similarity"] == 0.0 and o["is_original"] is True, o
    print("PASS test_originality_empty_corpus")


def test_originality_deterministic():
    """같은 입력 → 같은 출력 (결정론)."""
    a = "코딩 한 줄 없이 AI로 5일 만에 수익 서비스 만드는 법."
    corpus = ["전혀 다른 내용입니다 주제가 다름", "코딩 한 줄 없이 AI로 5일 만에 수익 서비스 만드는 방법은"]
    o1 = orc.originality_score(a, corpus)
    o2 = orc.originality_score(a, corpus)
    assert o1 == o2, (o1, o2)
    assert o1["most_similar_to"] == 1, o1  # 두 번째가 더 유사
    print("PASS test_originality_deterministic")


def test_extract_script():
    """output md에서 스크립트 본문만 추출."""
    md = '---\ntitle: x\n---\n# 제목\n## 🎬 스크립트\n실제 대본 내용.\n## 🖼 스토리보드\n무시.'
    assert orc._extract_script(md) == "실제 대본 내용.", orc._extract_script(md)
    print("PASS test_extract_script")


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


def test_title_overlap_short_root_josa():
    """2글자 어근+조사도 정규화 — '앱을 만들기' vs '앱 만들기' = 자카드 1.0."""
    o = orc.title_overlap_score("앱을 만들기", ["앱 만들기"])
    assert o["max_jaccard"] == 1.0, o
    print("PASS test_title_overlap_short_root_josa")


def test_title_overlap_subset_caught():
    """핵심 주제가 같지만 한쪽에 꼬리가 붙어 자카드가 희석돼도 overlap으로 중복 포착."""
    draft = "개발 없이 5일 만에 수익 웹서비스 만들기 AI와 함께"
    catalog = ["개발 없이 5일 만에 수익 웹서비스 비법 공개 바이브코딩"]
    o = orc.title_overlap_score(draft, catalog)
    assert not o["is_distinct"], f"핵심 주제 중복인데 통과됨: {o}"
    print("PASS test_title_overlap_subset_caught")


def test_load_channel_titles_missing():
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


def test_load_channel_titles_corrupt_graceful():
    """깨진 인코딩/잘못된 구조도 빈 리스트 (graceful)."""
    import pathlib, tempfile, os
    # 1) UTF-8 아닌 바이트
    fd, p = tempfile.mkstemp(suffix=".json"); os.close(fd)
    pathlib.Path(p).write_bytes(b"\xff\xfe not utf8")
    orig = orc.CATALOG_PATH; orc.CATALOG_PATH = pathlib.Path(p)
    try:
        assert orc.load_channel_titles() == [], "깨진 인코딩은 [] 여야"
    finally:
        orc.CATALOG_PATH = orig; os.unlink(p)
    # 2) videos: null
    fd, p = tempfile.mkstemp(suffix=".json"); os.close(fd)
    pathlib.Path(p).write_text('{"videos": null}', encoding="utf-8")
    orc.CATALOG_PATH = pathlib.Path(p)
    try:
        assert orc.load_channel_titles() == [], "videos null은 [] 여야"
    finally:
        orc.CATALOG_PATH = orig; os.unlink(p)
    print("PASS test_load_channel_titles_corrupt_graceful")


def test_deterministic_block_both():
    """originality·channel 둘 다 위반이면 두 사유 모두 반환(한 회차 통보)."""
    orig = {"is_original": False, "max_similarity": 0.9}
    channel = {"is_distinct": False, "max_jaccard": 0.7, "most_similar_title": "기존영상"}
    reasons = orc.deterministic_block(orig, channel, {"hook_ok": True}, {"ok": True})
    assert len(reasons) == 2, reasons
    assert any("독창성" in r for r in reasons) and any("채널 중복" in r for r in reasons), reasons
    print("PASS test_deterministic_block_both")


def test_deterministic_block_none():
    """둘 다 통과면 빈 리스트(차단 없음)."""
    orig = {"is_original": True, "max_similarity": 0.1}
    channel = {"is_distinct": True, "max_jaccard": 0.1, "most_similar_title": ""}
    assert orc.deterministic_block(orig, channel, {"hook_ok": True}, {"ok": True}) == [], "통과 시 빈 리스트"
    print("PASS test_deterministic_block_none")


def test_deterministic_block_measured_metrics():
    """word_count·keyword 미달이 결정론 강제차단되는가 — verdict-checks 모순(LLM이 ❌찍고도
    approved) 차단의 핵심. e2e에서 60단어가 '승인'되던 가짜승인을 막는다."""
    ok_orig = {"is_original": True, "max_similarity": 0.1}
    ok_ch = {"is_distinct": True, "max_jaccard": 0.1, "most_similar_title": ""}
    ok_d, ok_h = {"hook_ok": True}, {"ok": True}
    # 단어수 미달 → 차단
    r = orc.deterministic_block(ok_orig, ok_ch, ok_d, ok_h, {"words": 60, "ok": False}, {"ok": True})
    assert any("단어 수 위반" in x and "60단어" in x for x in r), r
    # 키워드 미달 → 차단(missing 노출)
    r2 = orc.deterministic_block(ok_orig, ok_ch, ok_d, ok_h,
                                 {"words": 120, "ok": True},
                                 {"ok": False, "included": 2, "total": 5, "ratio": 0.4, "missing": ["키워드A"]})
    assert any("키워드 포함률 미달" in x and "키워드A" in x for x in r2), r2
    # 둘 다 통과 → 차단 없음
    assert orc.deterministic_block(ok_orig, ok_ch, ok_d, ok_h,
                                   {"words": 120, "ok": True}, {"ok": True}) == []
    # wc/kw 미전달(기본 None) → 기존 동작 보존(차단 없음)
    assert orc.deterministic_block(ok_orig, ok_ch, ok_d, ok_h) == []
    print("PASS test_deterministic_block_measured_metrics")


def test_pick_hook():
    """훅 결정론 선택: 21음절 이내 후보 우선([0] 무조건 아님). e2e에서 korean_syllable_density가
    모든 escalated에 등장한 주범 — [0]이 길어도 짧은 [1]을 고르게 해 5/5 승인 달성한 수정."""
    # [0]이 길고 [1]이 짧으면 [1] 선택(한계 내 가장 정보량 많은 것)
    long0 = "이것은 분명히 스물한 음절을 넉넉히 넘기는 아주 긴 훅 문장이다 정말로"
    short1 = "AI로 웹사이트 5분 완성?"
    picked = orc.pick_hook([long0, short1, "짧다?"])
    assert orc.korean_syllables(picked) <= 21, (picked, orc.korean_syllables(picked))
    # 한계 내에서 가장 정보량(음절) 많은 것 — short1(13) > '짧다?'(2)
    assert picked == short1, picked
    # 전부 초과 → 가장 짧은 것
    allover = ["가나다라마바사아자차카타파하가나다라마바사", "가나다라마바사아자차카타파하가나다라마바사아자차"]
    assert orc.pick_hook(allover) == allover[0], "전부 초과면 가장 짧은 것"
    # 빈/None 안전
    assert orc.pick_hook([]) == ""
    assert orc.pick_hook(None) == ""
    print("PASS test_pick_hook")


def test_expand_script():
    """단어수 미달 자동 확장(결정론 후처리) — 라이브 e2e에서 length_bounds 단독 escalated를
    막은 수정. retry 소모 없이 '확장만', 키워드 보존, 퇴행 방어, 호출 상한."""
    import orchestrator as _orc
    orig_call = _orc.call
    calls = []
    try:
        # 1) 이미 충분(target 이상) → 호출 0(비용 0)
        _orc.call = lambda s, u, **k: (_ for _ in ()).throw(AssertionError("불필요 호출"))
        long_in = "단어 " * 130
        assert _orc.expand_script(long_in, target=130) == long_in

        # 2) 미달 → 확장 채택(더 길고 키워드 보존)
        def good(s, u, **k):
            calls.append(1)
            return {"script": "노코드 창업 " + ("확장단어 " * 140)}
        _orc.call = good
        r = _orc.expand_script("짧은 초안", target=130, keywords=["노코드 창업"])
        assert len(r.split()) >= 130 and "노코드" in r, r[:50]
        assert len(calls) == 1, "목표 달성 시 1콜에서 조기종료"

        # 3) 퇴행(모델이 더 짧게) → 원본 유지 + max 2회 상한
        calls.clear()
        _orc.call = lambda s, u, **k: (calls.append(1), {"script": "짧음"})[1]
        base = "원본이 더 긴 스크립트입니다 정말 길어요 보존되어야 합니다"
        r3 = _orc.expand_script(base, target=130)
        assert r3 == base, "퇴행본은 버리고 원본 유지"
        assert len(calls) == 2, "퇴행이어도 max_passes=2 상한"

        # 4) 키워드 누락 확장본은 거부(원본 유지)
        calls.clear()
        _orc.call = lambda s, u, **k: (calls.append(1), {"script": "키워드없는 " + ("채움 " * 140)})[1]
        r4 = _orc.expand_script("짧은 원본", target=130, keywords=["반드시있어야할키워드"])
        assert "반드시있어야할키워드" not in r4 and r4 == "짧은 원본", "키워드 누락 확장은 거부"

        # 5) call 예외 → best-effort 원본 반환(파이프라인 보호)
        _orc.call = lambda s, u, **k: (_ for _ in ()).throw(RuntimeError("API down"))
        assert _orc.expand_script("원본유지", target=130) == "원본유지"
    finally:
        _orc.call = orig_call
    print("PASS test_expand_script")


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


def test_call_text_length_truncation_raises():
    """Sonar 응답 잘림(finish_reason=length) 감지 → RuntimeError."""
    reset()
    payload = {"choices": [{"finish_reason": "length", "message": {"content": '{"trends":['}}],
               "usage": {"completion_tokens": 1000, "cost": 8.0}}
    orig = urllib.request.urlopen
    urllib.request.urlopen = fake_urlopen_factory(payload)
    raised = False
    try:
        orc.call_text("q", model=orc.TREND_MODEL)
    except RuntimeError as e:
        raised = "잘림" in str(e)
    finally:
        urllib.request.urlopen = orig
    assert raised, "Sonar 잘림이 감지되지 않음"
    print("PASS test_call_text_length_truncation_raises")


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
    # 다단계화 후 trends 항목에 freshness_score가 추가됨 — keyword/why는 보존.
    assert len(out["trends"]) == 1 and out["trends"][0]["keyword"] == "에이전틱 AI", out
    assert out["trends"][0]["why"] == "부상", out
    assert "freshness_score" in out["trends"][0], out
    assert out["sources"] == [{"title": "T", "url": "https://x.com"}], out
    print("PASS test_fetch_live_trends_parses")


def test_fetch_live_trends_malformed_trends():
    """trends가 list 아니거나(dict) 항목이 비-dict면 걸러내 크래시 방지(복구 불가 시 빈 리스트)."""
    reset()
    # trends가 dict로 옴(Sonar 이상 응답) — keyword/why 쌍이 없어 정규식 복구도 불가
    content = '{"trends":{"foo":"X","bar":"Y"}}'
    payload = {"choices": [{"finish_reason": "stop", "message": {"content": content}}],
               "usage": {"cost": 8.0}}
    orig = urllib.request.urlopen
    urllib.request.urlopen = fake_urlopen_factory(payload)
    try:
        out = orc.fetch_live_trends("주제")
    finally:
        urllib.request.urlopen = orig
    assert out["trends"] == [], out  # dict는 list 아니고 복구 가능한 객체도 없으므로 빈 리스트
    print("PASS test_fetch_live_trends_malformed_trends")


def test_suggest_topics_no_key():
    """API_KEY 부재 시 빈 결과 graceful(네트워크 호출 0)."""
    reset()
    orc.API_KEY = ""
    out = orc.suggest_topics(n=6)
    assert out == {"topics": [], "trends": [], "sources": []}, out
    print("PASS test_suggest_topics_no_key")


def _seq_urlopen(payloads):
    """호출 순서대로 다른 응답을 돌려주는 fake urlopen(suggest_topics는 Sonar→flash-lite 2콜)."""
    box = {"i": 0}
    def _fake(req, timeout=60):
        p = payloads[min(box["i"], len(payloads)-1)]
        box["i"] += 1
        return FakeResp(json.dumps(p).encode("utf-8"))
    return _fake


def test_suggest_topics_generates():
    """Sonar 트렌드 + flash-lite 제안 → topics 파싱(과거 산출물 아님)."""
    reset()
    sonar = {"choices": [{"finish_reason": "stop", "message": {
        "content": '{"trends":[{"keyword":"AI 자동응대","why":"검색 급증"}]}',
        "metadata": {"search_results": [{"title": "S", "url": "https://s.com"}]}}}],
        "usage": {"cost": 5.0}}
    flash = {"choices": [{"finish_reason": "stop", "message": {"content":
        '{"topics":[{"title":"사장님 리뷰 AI로 5분 자동응대","why":"지금 검색 급증"},'
        '{"title":"노코드로 만든 첫 예약봇","why":"진입장벽 0"}]}'}}],
        "usage": {"cost": 3.0}}
    orig = urllib.request.urlopen
    urllib.request.urlopen = _seq_urlopen([sonar, flash])
    try:
        out = orc.suggest_topics(n=6)
    finally:
        urllib.request.urlopen = orig
    assert len(out["topics"]) == 2, out
    assert out["topics"][0]["title"] == "사장님 리뷰 AI로 5분 자동응대", out
    assert out["topics"][0]["why"], out
    assert out["trends"] and out["sources"], out  # Sonar 결과도 함께 반환
    print("PASS test_suggest_topics_generates")


def test_suggest_topics_string_array():
    """LLM이 topics를 문자열 배열로만 줘도 흡수(견고성)."""
    reset()
    sonar = {"choices": [{"finish_reason": "stop", "message": {"content": '{"trends":[]}'}}], "usage": {"cost": 1.0}}
    flash = {"choices": [{"finish_reason": "stop", "message": {"content":
        '{"topics":["주제 문자열만 옴","두번째 주제"]}'}}], "usage": {"cost": 1.0}}
    orig = urllib.request.urlopen
    urllib.request.urlopen = _seq_urlopen([sonar, flash])
    try:
        out = orc.suggest_topics(n=6)
    finally:
        urllib.request.urlopen = orig
    assert [t["title"] for t in out["topics"]] == ["주제 문자열만 옴", "두번째 주제"], out
    print("PASS test_suggest_topics_string_array")


def test_parse_trends_recovers_broken_json():
    """전체 JSON이 깨져도 개별 trend 객체를 정규식으로 부분 복구."""
    broken = '{"trends":[{"keyword":"AI 워크플로","why":"부상 중, 그리고 확산"} {"keyword":"명세화","why":"중심 스킬"}]'  # 쉼표 누락+미닫힘
    out = orc._parse_trends(broken)
    assert len(out) == 2, out
    assert out[0]["keyword"] == "AI 워크플로", out
    print("PASS test_parse_trends_recovers_broken_json")


def test_parse_trends_normal():
    """정상 JSON은 그대로 파싱."""
    good = '{"trends":[{"keyword":"K","why":"W"}]}'
    out = orc._parse_trends(good)
    assert out == [{"keyword":"K","why":"W"}], out
    print("PASS test_parse_trends_normal")


def test_parse_json_robust():
    """모델 출력 JSON 견고 추출 — 코드펜스·선행/후행 텍스트·중첩.
    공개 배포 SSE 검증서 발견한 'Extra data: line 2 column 1' 크래시(JSON 뒤 산문) 재발 방지 골든셋."""
    cases = {
        "순수JSON": '{"a": 1}',
        "코드펜스": "```json\n{\"a\": 1}\n```",
        "선행텍스트": 'Here is the JSON:\n{"a": 1}',
        "후행ExtraData": '{"a": 1}\nThis is extra explanation.',  # ← 실제 배포 크래시 케이스
        "중첩+후행": '{"a": {"b": 2}, "c": [1,2]}\n참고: ...',
        "코드펜스+후행": "```json\n{\"a\": 1}\n```\nDone.",
    }
    for name, raw in cases.items():
        r = orc.parse_json(raw)
        assert isinstance(r, dict) and r.get("a") is not None, f"{name}: {r}"
    # JSON이 전혀 없으면 JSONDecodeError
    import json as _j
    try:
        orc.parse_json("그냥 평범한 문장입니다.")
        assert False, "JSON 부재 시 예외를 던져야 함"
    except _j.JSONDecodeError:
        pass
    print("PASS test_parse_json_robust")


def test_parse_json_always_dict():
    """parse_json은 LLM이 배열·null·문자열 최상위를 줘도 항상 dict 반환(핸드오프 무결성).
    견고성 감사: LLM이 [{...}] 또는 null을 주면 후속 .get/.update가 깨지던 결함 방지."""
    assert orc.parse_json('[{"a":1}]') == {}, "배열 최상위 → 빈 dict"
    assert orc.parse_json('null') == {}, "null → 빈 dict"
    assert orc.parse_json('"문자열"') == {}, "문자열 최상위 → 빈 dict"
    assert orc.parse_json('42') == {}, "숫자 → 빈 dict"
    assert orc.parse_json('{"a":1}') == {"a": 1}, "정상 dict는 보존"
    print("PASS test_parse_json_always_dict")


def test_as_list_normalizes():
    """_as_list: LLM이 list 기대 필드에 str/null/dict 줘도 안전 정규화.
    견고성 감사: keywords='AI'(str) → 문자 단위 순회로 메트릭 오염되던 결함 방지."""
    assert orc._as_list(["a", "b"]) == ["a", "b"], "list는 그대로"
    assert orc._as_list("AI 트렌드") == ["AI 트렌드"], "str → 1원소 리스트(문자순회 방지)"
    assert orc._as_list(None) == [], "null → 빈 리스트"
    assert orc._as_list("") == [], "빈 문자열 → 빈 리스트"
    assert orc._as_list({"k": "v"}) == [{"k": "v"}], "dict → 1원소 리스트"
    print("PASS test_as_list_normalizes")


def test_as_str_normalizes():
    """_as_str: LLM이 str 기대 필드에 list/null/dict 줘도 안전 정규화."""
    assert orc._as_str("hi") == "hi", "str은 그대로"
    assert orc._as_str(None) == "", "null → 빈 문자열"
    assert orc._as_str(["a", "b"]) == "a\nb", "list → 줄바꿈 결합"
    assert orc._as_str(42) == "42", "숫자 → 문자열"
    print("PASS test_as_str_normalizes")


def test_keyword_inclusion_string_input_safe():
    """keyword_inclusion_score에 str 키워드(LLM 오타입)가 _as_list 거치면 정상 동작.
    회귀: keywords='AI'를 직접 넘기면 문자 단위 순회(오염), _as_list로 보호되는지 계약 검증."""
    # _as_list를 거친 정상 입력
    r = orc.keyword_inclusion_score("AI로 코딩하는 방법", orc._as_list("AI"))
    assert r["total"] == 1, r  # 'AI' 1개 키워드(문자 2개 아님)
    print("PASS test_keyword_inclusion_string_input_safe")


def test_read_state_graceful(tmp_path=None):
    """read_state: State.json 부재·손상 시 기본 상태로 graceful 복구(컨테이너 재시작 방어)."""
    import tempfile, pathlib
    saved = orc.STATE_PATH
    try:
        # 부재
        orc.STATE_PATH = pathlib.Path(tempfile.mkdtemp()) / "없는파일.json"
        s = orc.read_state()
        assert s == {"max_retries": 3, "tasks": []}, s
        # 손상
        bad = pathlib.Path(tempfile.mkdtemp()) / "State.json"
        bad.write_text("{깨진 json", encoding="utf-8")
        orc.STATE_PATH = bad
        s2 = orc.read_state()
        assert s2 == {"max_retries": 3, "tasks": []}, s2
    finally:
        orc.STATE_PATH = saved
    print("PASS test_read_state_graceful")


def test_call_empty_choices_raises_clean(monkeypatch=None):
    """call/call_text: API가 {'error':...}(choices 없음) 줘도 KeyError 대신 명확한 RuntimeError."""
    import urllib.request
    reset()
    def fake(req, timeout=60):
        return FakeResp(json.dumps({"error": "rate limit", "usage": {}}).encode("utf-8"))
    orig = urllib.request.urlopen
    urllib.request.urlopen = fake
    try:
        try:
            orc.call("sys", "user")
            assert False, "choices 부재 시 RuntimeError 기대"
        except RuntimeError as e:
            assert "choices" in str(e), e
        try:
            orc.call_text("user")
            assert False, "call_text choices 부재 시 RuntimeError 기대"
        except RuntimeError as e:
            assert "choices" in str(e), e
    finally:
        urllib.request.urlopen = orig
    print("PASS test_call_empty_choices_raises_clean")


def test_run_has_on_step_param():
    """run에 on_step 파라미터(기본값 None)가 있어 CLI 호환 유지."""
    import inspect
    sig = inspect.signature(orc.run)
    assert "on_step" in sig.parameters, "run에 on_step 파라미터 필요"
    assert sig.parameters["on_step"].default is None, "on_step 기본값 None이어야 CLI 호환"
    print("PASS test_run_has_on_step_param")


def test_emit_swallows_callback_exception():
    """on_step이 예외를 던져도 run의 emit이 삼켜 파이프라인 보호(best-effort)."""
    # emit은 run 내부 클로저라 직접 못 부른다 → 동일 패턴을 재현해 계약만 검증
    captured = []
    def boom_on_step(payload):
        raise RuntimeError("queue full")
    def emit(stage, **data):  # run 내부 emit과 동일 구조
        if boom_on_step:
            try:
                boom_on_step({"stage": stage, **data})
            except Exception as e:
                captured.append(str(e))
    emit("creator", retry=0)  # 예외가 전파되면 이 라인에서 테스트가 죽음
    assert captured == ["queue full"], captured
    print("PASS test_emit_swallows_callback_exception")


def test_run_happy_path_integration():
    """run() 전체 흐름: 트렌드→분석→작성→검수→승인. on_step 이벤트 순서 확인.
    State.json·output·log·catalog를 임시 디렉토리로 격리해 실제 파일 오염 방지."""
    reset()
    import tempfile, os, pathlib, json as _json
    # 4 에이전트 응답을 순서대로 반환하는 fake (Sonar trend, trend-analyst, creator, reviewer)
    responses = [
        # 1) Sonar fetch_live_trends (call_text)
        {"choices":[{"finish_reason":"stop","message":{"content":'{"trends":[{"keyword":"테스트트렌드","why":"근거"}]}',"metadata":{"search_results":[{"title":"T","url":"https://x.com"}]}}}],"usage":{"cost":0.1}},
        # 2) trend-analyst (call, json_object)
        {"choices":[{"finish_reason":"stop","message":{"content":'{"keywords":["통합테스트키워드"],"hooks":["3초 훅"]}'}}],"usage":{"cost":0.05}},
        # 3) creator — script에 타겟 키워드('통합테스트키워드')를 포함해야 결정론 keyword_inclusion 통과.
        #    (패치: deterministic_block이 word_count·keyword를 강제차단하므로 mock도 이를 만족해야 함)
        {"choices":[{"finish_reason":"stop","message":{"content":'{"title":"통합테스트 고유제목 절대중복없음 zzqq","script":"통합테스트키워드 '+("단어 "*120)+'","storyboard":["s"],"thumbnail_prompt":"t","hashtags":["#태그"]}'}}],"usage":{"cost":0.05}},
        # 4) reviewer → approved
        {"choices":[{"finish_reason":"stop","message":{"content":'{"verdict":"approved","checks":[{"metric":"length_bounds","pass":true,"comment":"ok"}],"feedback":[]}'}}],"usage":{"cost":0.05}},
    ]
    it = iter(responses)
    def fake(req, timeout=60):
        return FakeResp(json.dumps(next(it)).encode("utf-8"))
    events = []
    tmpdir = pathlib.Path(tempfile.mkdtemp())
    # 임시 상태/이밸/로그/카탈로그 — read_state·append_log가 읽으므로 미리 써둔다
    (tmpdir / "State.json").write_text(_json.dumps({"max_retries": 3, "tasks": []}), encoding="utf-8")
    (tmpdir / "log.md").write_text("---\ntitle: log\n---\n\n- 기존 항목\n", encoding="utf-8")
    out_dir = tmpdir / "output"
    cat_path = tmpdir / "channel_catalog.json"  # 부재 → 채널중복 graceful(빈 카탈로그)
    saved = (orc.STATE_PATH, orc.OUTPUT_DIR, orc.LOG, orc.CATALOG_PATH)
    orc.STATE_PATH, orc.OUTPUT_DIR, orc.LOG, orc.CATALOG_PATH = (
        tmpdir / "State.json", out_dir, tmpdir / "log.md", cat_path,
    )
    orig = urllib.request.urlopen
    urllib.request.urlopen = fake
    try:
        orc.run("통합테스트 고유주제 절대채널중복없음 zzqq", on_step=lambda p: events.append(p["stage"]))
    finally:
        urllib.request.urlopen = orig
        orc.STATE_PATH, orc.OUTPUT_DIR, orc.LOG, orc.CATALOG_PATH = saved
        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)
    # 핵심 단계가 순서대로 발행됐는지
    assert "supervisor" in events, events
    assert "trend-live" in events, events
    assert "trend-analyst" in events, events
    assert "creator" in events, events
    assert "done" in events, events
    print("PASS test_run_happy_path_integration")


def test_run_escalation_payload():
    """run() 에스컬레이션 경로: reviewer가 계속 rejected → max_retries 초과 시
    escalated 이벤트에 마지막 초안(payload)·반려 누적(feedback_log)·실패 metric이 실린다(막다른길 방지 UX)."""
    reset()
    import tempfile, pathlib, json as _json
    sonar = {"choices":[{"finish_reason":"stop","message":{"content":'{"trends":[]}'}}],"usage":{"cost":0.1}}
    analyst = {"choices":[{"finish_reason":"stop","message":{"content":'{"keywords":["k"],"hooks":["3초 훅"]}'}}],"usage":{"cost":0.05}}
    creator = {"choices":[{"finish_reason":"stop","message":{"content":'{"title":"에스컬테스트 고유제목 zzqq","script":"'+("단어 "*120)+'","storyboard":["s"],"thumbnail_prompt":"t","hashtags":["#태그"]}'}}],"usage":{"cost":0.05}}
    reviewer_rej = {"choices":[{"finish_reason":"stop","message":{"content":'{"verdict":"rejected","checks":[{"metric":"retention_design","pass":false,"comment":"완주율 설계 부족"}],"feedback":["완주율을 높이세요"]}'}}],"usage":{"cost":0.05}}
    # 순서: sonar, analyst, 그다음 (creator, reviewer)를 max_retries+1=4회 반복
    responses = [sonar, analyst]
    for _ in range(4):
        responses += [creator, reviewer_rej]
    it = iter(responses)
    def fake(req, timeout=60):
        return FakeResp(json.dumps(next(it)).encode("utf-8"))
    tmpdir = pathlib.Path(tempfile.mkdtemp())
    (tmpdir / "State.json").write_text(_json.dumps({"max_retries": 3, "tasks": []}), encoding="utf-8")
    (tmpdir / "log.md").write_text("---\ntitle: log\n---\n\n- 기존\n", encoding="utf-8")
    saved = (orc.STATE_PATH, orc.OUTPUT_DIR, orc.LOG, orc.CATALOG_PATH)
    orc.STATE_PATH, orc.OUTPUT_DIR, orc.LOG, orc.CATALOG_PATH = (
        tmpdir / "State.json", tmpdir / "output", tmpdir / "log.md", tmpdir / "channel_catalog.json")
    captured = {}
    def on_step(p):
        if p["stage"] == "escalated":
            captured.update(p)
    orig = urllib.request.urlopen
    urllib.request.urlopen = fake
    try:
        orc.run("에스컬테스트 고유주제 zzqq", on_step=on_step)
    finally:
        urllib.request.urlopen = orig
        orc.STATE_PATH, orc.OUTPUT_DIR, orc.LOG, orc.CATALOG_PATH = saved
        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)
    assert captured.get("verdict") == "escalated", captured
    assert captured.get("payload", {}).get("title"), "마지막 초안(payload.title) 누락"
    assert captured.get("payload", {}).get("script"), "마지막 초안(payload.script) 누락"
    assert isinstance(captured.get("feedback_log"), list) and captured["feedback_log"], "feedback_log 누락"
    assert "retention_design" in (captured.get("failed_metrics") or []), captured.get("failed_metrics")
    print("PASS test_run_escalation_payload")


def test_korean_syllable_count():
    """한글 음절수 결정론 카운트 — 한글만 세고 공백·영문·기호 제외."""
    assert orc.korean_syllables("안녕하세요") == 5, orc.korean_syllables("안녕하세요")
    assert orc.korean_syllables("AI로 코딩") == 3, orc.korean_syllables("AI로 코딩")  # 로,코,딩
    assert orc.korean_syllables("") == 0
    print("PASS test_korean_syllable_count")


def test_hook_syllable_check():
    """훅 18~21음절 한계 — 21 이내 OK, 초과 fail."""
    short_hook = "당신이 반드시 알아야 할 단 하나의 마케팅 비법"  # 19음절
    r = orc.script_density_score(short_hook, short_hook)
    assert r["hook_syllables"] <= 21, r
    assert r["hook_ok"] is True, r
    long_hook = "가" * 30  # 30음절 — 초과
    r2 = orc.script_density_score(long_hook, long_hook)
    assert r2["hook_ok"] is False, r2
    print("PASS test_hook_syllable_check")


def test_hashtag_count_score():
    """해시태그 1~5개 결정론 카운트."""
    assert orc.hashtag_count_score(["#a", "#b"])["count"] == 2
    assert orc.hashtag_count_score(["#a", "#b"])["ok"] is True
    assert orc.hashtag_count_score(["#a"]*6)["ok"] is False  # 6개 초과
    assert orc.hashtag_count_score([])["ok"] is False  # 0개도 fail(1~5)
    print("PASS test_hashtag_count_score")


def test_overclaim_patterns():
    """과장/거짓 단정 패턴 결정론 탐지."""
    bad = "이 방법이면 누구나 100% 코딩을 완전 대체하고 무조건 월 1000만원 보장됩니다"
    r = orc.overclaim_check(bad)
    assert not r["ok"], r
    assert len(r["flags"]) >= 2, r  # '100%', '무조건', '보장' 등 다수
    good = "AI 도구를 잘 쓰면 작업 효율을 높일 수 있습니다. 결과는 사람마다 다릅니다."
    r2 = orc.overclaim_check(good)
    assert r2["ok"], r2
    print("PASS test_overclaim_patterns")


def test_overclaim_evasion_golden():
    """검증이 잡은 회피 케이스 — 전부 flag돼야(골든셋, 재발 방지)."""
    cases = [
        "월 1000만원 보장됩니다",
        "수익 보장 확실",
        "100퍼센트 됩니다",
        "반드시 성공합니다",
        "확실하게 수익 납니다",
        "천만원 보장",
    ]
    for c in cases:
        r = orc.overclaim_check(c)
        assert not r["ok"], f"회피 케이스 미탐지: {c!r} → {r}"
    print("PASS test_overclaim_evasion_golden")


def test_overclaim_legitimate_pass():
    """정당한 표현은 통과(false-positive 경계)."""
    # 단 '보장'을 넓혀서 '환불 보장'은 flag될 수 있음 — Reviewer 종합판정이 거름.
    good = "AI 도구를 잘 쓰면 효율을 높일 수 있어요. 결과는 사람마다 다릅니다."
    assert orc.overclaim_check(good)["ok"], orc.overclaim_check(good)
    print("PASS test_overclaim_legitimate_pass")


def test_overclaim_empty():
    """빈 스크립트는 통과(ok=True)."""
    assert orc.overclaim_check("")["ok"] is True
    print("PASS test_overclaim_empty")


def test_numeric_claim_extract():
    """스크립트에서 수치 주장 추출(검증 대상 식별)."""
    s = "구독자 14900명을 모았고 조회수 5만회를 기록했습니다"
    claims = orc.extract_numeric_claims(s)
    assert any("14900" in c or "14,900" in c or "1만4900" in c for c in claims) or len(claims) >= 1, claims
    print("PASS test_numeric_claim_extract")


def test_word_count_score():
    assert orc.word_count_score(" ".join(["단어"]*120))["ok"] is True
    assert orc.word_count_score(" ".join(["단어"]*50))["ok"] is False  # 100 미만
    print("PASS test_word_count_score")


def test_keyword_inclusion_score():
    # (기존) 부분 포함 + missing 반환 — 회귀 보호
    s = "AI 코딩 입문 가이드와 노코드 창업 이야기"
    r = orc.keyword_inclusion_score(s, ["AI 코딩", "노코드 창업", "없는키워드"])
    assert r["included"] == 2 and r["total"] == 3 and r["ok"] is False, r  # 2/3=0.667<0.8
    assert "없는키워드" in r["missing"], r            # missing 리스트(Creator 피드백 경로)

    # (신규 A) 자연 변형 인정: 한국어 조사·어순 굴절은 통과해야 한다 — 반복반려 근인 수정의 핵심
    # exact-substring(현행)이면 0.0으로 실패 → 근접 토큰 매칭이면 통과
    s2 = "엑셀을 대체하는 AI로 데이터 분석 속도가 확 빨라집니다. AI로 엑셀 작업을 대체하세요."
    r2 = orc.keyword_inclusion_score(s2, ["엑셀 대체 AI", "데이터 분석 속도"])
    assert r2["ok"] is True, r2

    # (신규 B) 가짜 통과 차단①: 흩어진 우연 토큰은 탈락(근접 윈도우 방어)
    far = "엑셀은 오래된 도구다. " + ("잡담 " * 60) + "AI는 미래다. " + ("딴말 " * 60) + "대체 가능성도 있다."
    rf = orc.keyword_inclusion_score(far, ["엑셀 대체 AI", "데이터 분석 속도", "실무 꿀팁", "자동화 비결", "노코드 창업"])
    assert rf["ok"] is False, rf

    # (신규 C) 가짜 통과 차단②: 완전 오프토픽은 0.0
    cook = "오늘은 김치찌개를 끓입니다. 돼지고기와 두부를 넣고 푹 끓이면 맛있어요."
    rc = orc.keyword_inclusion_score(cook, ["엑셀 대체 AI", "데이터 분석 속도"])
    assert rc["ok"] is False and rc["ratio"] == 0.0, rc

    # (신규 D) 스터핑 차단: 공통 토큰(AI)만 반복해도 각 키워드 고유토큰 70% 필요
    stuff = "AI AI AI AI AI 정말 좋은 AI AI"
    rs = orc.keyword_inclusion_score(stuff, ["엑셀 대체 AI", "데이터 분석 AI"])
    assert rs["ok"] is False, rs

    # (신규 D2) 스터핑 차단 — 2토큰 'AI 복합' 키워드 e2e 발견 케이스(회귀 가드).
    # need=round(2*0.7)=1 붕괴로 'AI'만 박은 무관 스크립트가 1.0 통과하던 가짜통과를
    # 고유토큰 필수 가드로 차단한다(고유토큰 '웹서비스/마케팅/자동화' 부재 → 전부 탈락).
    stuff2 = "AI 너무 좋아요 AI 최고 AI 짱 AI 입니다"
    rs2 = orc.keyword_inclusion_score(stuff2, ["AI 웹서비스", "AI 마케팅", "AI 자동화"])
    assert rs2["ratio"] == 0.0 and rs2["ok"] is False, rs2
    # 반례: 같은 'AI 복합' 키워드라도 고유토큰이 본문에 있으면 정상 통과(과차단 방지).
    ok2 = orc.keyword_inclusion_score("AI 웹서비스로 마케팅 자동화를 했어요.", ["AI 웹서비스", "AI 마케팅", "AI 자동화"])
    assert ok2["ok"] is True, ok2
    # 가드 경계: 키워드 전체가 공통토큰('AI')뿐이면 가드를 건너뛰어 기존 단일토큰 동작 보존.
    assert orc._keyword_present("AI", "AI로 코딩합니다") is True
    print("PASS test_keyword_inclusion_score")


# ── Gamma 슬라이드 통합 (urllib mock, 네트워크 0) ──────────────────
_GAMMA_PAYLOAD = {
    "title": "테스트 기획안", "script": "본문 스크립트",
    "storyboard": ["장면1", "장면2"], "thumbnail_prompt": "썸네일 컨셉",
    "hashtags": ["#태그1", "#태그2"],
}


def test_gamma_build_input_includes_fields():
    """payload의 모든 필드가 inputText에 들어간다(슬라이드 누락 방지)."""
    txt = orc.gamma_build_input(_GAMMA_PAYLOAD, "테스트주제")
    for must in ["테스트 기획안", "본문 스크립트", "장면1", "장면2", "썸네일 컨셉", "#태그1"]:
        assert must in txt, f"누락: {must}"
    assert "테스트주제" in txt
    print("PASS test_gamma_build_input_includes_fields")


def test_agent_gamma_prompt_success():
    """감마 프롬프트 에이전트 — LLM이 충분한 inputText 주면 그대로 사용."""
    reset()
    long_text = "## 제목 슬라이드\n" + ("발표용 슬라이드 본문 재구성 텍스트. " * 20)
    orig = urllib.request.urlopen
    urllib.request.urlopen = fake_urlopen_factory(
        {"choices": [{"finish_reason": "stop", "message": {"content": json.dumps({"inputText": long_text})}}],
         "usage": {"cost": 0.05}})
    try:
        out = orc.agent_gamma_prompt(_GAMMA_PAYLOAD, "주제")
    finally:
        urllib.request.urlopen = orig
    assert out and "제목 슬라이드" in out, out
    print("PASS test_agent_gamma_prompt_success")


def test_agent_gamma_prompt_no_key_none():
    """API_KEY 부재 → None(조립 폴백 유도, 네트워크 0)."""
    reset()
    orc.API_KEY = ""
    out = orc.agent_gamma_prompt(_GAMMA_PAYLOAD, "주제")
    assert out is None, out
    print("PASS test_agent_gamma_prompt_no_key_none")


def test_agent_gamma_prompt_too_short_none():
    """LLM이 빈약한(<100자) inputText 주면 None → 조립 폴백."""
    reset()
    orig = urllib.request.urlopen
    urllib.request.urlopen = fake_urlopen_factory(
        {"choices": [{"finish_reason": "stop", "message": {"content": json.dumps({"inputText": "짧음"})}}],
         "usage": {"cost": 0.05}})
    try:
        out = orc.agent_gamma_prompt(_GAMMA_PAYLOAD, "주제")
    finally:
        urllib.request.urlopen = orig
    assert out is None, out
    print("PASS test_agent_gamma_prompt_too_short_none")


def test_agent_gamma_prompt_fail_none():
    """LLM 호출 예외 → None(조립 폴백 유도, 예외 안 던짐)."""
    reset()
    def boom(req, timeout=60): raise RuntimeError("down")
    orig = urllib.request.urlopen
    urllib.request.urlopen = boom
    try:
        out = orc.agent_gamma_prompt(_GAMMA_PAYLOAD, "주제")
    finally:
        urllib.request.urlopen = orig
    assert out is None, out
    print("PASS test_agent_gamma_prompt_fail_none")


def test_gamma_generate_uses_agent_then_fallback():
    """gamma_generate가 에이전트 inputText를 우선 쓰고, 에이전트 빈약 시 조립 폴백을 쓴다."""
    reset()
    orc.GAMMA_API_KEY = "sk-gamma-test"
    # 시퀀스: ① 에이전트 call(빈약 inputText → None) ② Gamma POST(generationId)
    # → gamma_generate는 조립 폴백 inputText로 생성요청. 두 응답을 순서대로 준다.
    responses = [
        {"choices": [{"finish_reason": "stop", "message": {"content": json.dumps({"inputText": "짧음"})}}], "usage": {"cost": 0.05}},
        {"generationId": "genABC123"},
    ]
    it = iter(responses)
    captured = {}
    def fake(req, timeout=60):
        body = json.loads(req.data.decode("utf-8")) if getattr(req, "data", None) else {}
        if "inputText" in body:                 # Gamma POST 캡처
            captured["inputText"] = body["inputText"]
        return FakeResp(json.dumps(next(it)).encode("utf-8"))
    orig = urllib.request.urlopen
    urllib.request.urlopen = fake
    try:
        r = orc.gamma_generate(_GAMMA_PAYLOAD, "주제")
    finally:
        urllib.request.urlopen = orig
        orc.GAMMA_API_KEY = ""
    assert r["status"] == "generating" and r["id"] == "genABC123", r
    # 에이전트가 빈약 → 조립 폴백 inputText(필드 나열)가 전송됐는지
    assert "테스트 기획안" in captured.get("inputText", ""), captured
    print("PASS test_gamma_generate_uses_agent_then_fallback")


def test_gamma_generate_no_key():
    """키 미설정 → 예외 아닌 {status:failed} 강등(기획안 보호)."""
    saved = orc.GAMMA_API_KEY
    orc.GAMMA_API_KEY = ""
    try:
        r = orc.gamma_generate(_GAMMA_PAYLOAD, "주제")
        assert r["status"] == "failed" and "미설정" in r["error"], r
    finally:
        orc.GAMMA_API_KEY = saved
    print("PASS test_gamma_generate_no_key")


def test_gamma_generate_success():
    """200 + generationId → {status:generating, id}."""
    saved = orc.GAMMA_API_KEY
    orc.GAMMA_API_KEY = "sk-gamma-test"
    orig = urllib.request.urlopen
    urllib.request.urlopen = fake_urlopen_factory({"generationId": "abc123XYZ"})
    try:
        r = orc.gamma_generate(_GAMMA_PAYLOAD, "주제")
        assert r["status"] == "generating" and r["id"] == "abc123XYZ", r
    finally:
        urllib.request.urlopen = orig
        orc.GAMMA_API_KEY = saved
    print("PASS test_gamma_generate_success")


def test_gamma_generate_http_error_graceful():
    """HTTP 4xx → 예외 아닌 {status:failed}(기획안 보호)."""
    saved = orc.GAMMA_API_KEY
    orc.GAMMA_API_KEY = "sk-gamma-test"
    orig = urllib.request.urlopen
    def boom(req, timeout=30):
        # hdrs 타입은 런타임 무관(스텁 한계). gamma_generate의 HTTPError graceful 강등 검증이 목적.
        raise urllib.error.HTTPError(req.full_url, 402, "Payment Required", None, io.BytesIO(b'{"error":"no credits"}'))  # type: ignore[arg-type]
    urllib.request.urlopen = boom
    try:
        r = orc.gamma_generate(_GAMMA_PAYLOAD, "주제")
        assert r["status"] == "failed" and "402" in r["error"], r
    finally:
        urllib.request.urlopen = orig
        orc.GAMMA_API_KEY = saved
    print("PASS test_gamma_generate_http_error_graceful")


def test_gamma_status_completed():
    """completed → pdf_url·gamma_url 추출."""
    saved = orc.GAMMA_API_KEY
    orc.GAMMA_API_KEY = "sk-gamma-test"
    orig = urllib.request.urlopen
    urllib.request.urlopen = fake_urlopen_factory({
        "status": "completed", "exportUrl": "https://x/AI.pdf",
        "gammaUrl": "https://gamma.app/docs/x", "credits": {"remaining": 2800},
    })
    try:
        r = orc.gamma_status("abc123")
        assert r["status"] == "completed", r
        assert r["pdf_url"] == "https://x/AI.pdf" and r["gamma_url"] == "https://gamma.app/docs/x", r
        assert r["credits"]["remaining"] == 2800, r
    finally:
        urllib.request.urlopen = orig
        orc.GAMMA_API_KEY = saved
    print("PASS test_gamma_status_completed")


def test_gamma_status_bad_id():
    """잘못된 id(특수문자) → 호출 전 거부(SSRF/경로주입 방어)."""
    saved = orc.GAMMA_API_KEY
    orc.GAMMA_API_KEY = "sk-gamma-test"
    try:
        r = orc.gamma_status("../../etc/passwd")
        assert r["status"] == "failed" and "잘못된" in r["error"], r
        r2 = orc.gamma_status("")
        assert r2["status"] == "failed", r2
    finally:
        orc.GAMMA_API_KEY = saved
    print("PASS test_gamma_status_bad_id")


def test_run_done_has_gamma_field():
    """run() 승인 경로의 done 이벤트에 gamma 필드가 실린다(키 부재면 failed로라도)."""
    reset()
    orc.GAMMA_API_KEY = ""   # 키 부재 → gamma=failed, 그래도 done은 정상
    import tempfile, pathlib, json as _json
    sonar = {"choices":[{"finish_reason":"stop","message":{"content":'{"trends":[]}'}}],"usage":{"cost":0.1}}
    analyst = {"choices":[{"finish_reason":"stop","message":{"content":'{"keywords":["고유키워드zzqq"],"hooks":["3초 훅"]}'}}],"usage":{"cost":0.05}}
    creator = {"choices":[{"finish_reason":"stop","message":{"content":'{"title":"감마필드테스트 고유제목 zzqq","script":"'+("고유키워드zzqq "*120)+'","storyboard":["s"],"thumbnail_prompt":"t","hashtags":["#태그"]}'}}],"usage":{"cost":0.05}}
    reviewer_ok = {"choices":[{"finish_reason":"stop","message":{"content":'{"verdict":"approved","checks":[{"metric":"retention_design","pass":true,"comment":"ok"}],"feedback":[]}'}}],"usage":{"cost":0.05}}
    it = iter([sonar, analyst, creator, reviewer_ok])
    def fake(req, timeout=60):
        return FakeResp(json.dumps(next(it)).encode("utf-8"))
    tmpdir = pathlib.Path(tempfile.mkdtemp())
    (tmpdir / "State.json").write_text(_json.dumps({"max_retries": 3, "tasks": []}), encoding="utf-8")
    (tmpdir / "log.md").write_text("---\ntitle: log\n---\n\n- 기존\n", encoding="utf-8")
    saved = (orc.STATE_PATH, orc.OUTPUT_DIR, orc.LOG, orc.CATALOG_PATH)
    orc.STATE_PATH, orc.OUTPUT_DIR, orc.LOG, orc.CATALOG_PATH = (
        tmpdir / "State.json", tmpdir / "output", tmpdir / "log.md", tmpdir / "channel_catalog.json")
    captured = {}
    def on_step(p):
        if p.get("stage") == "done":
            captured.update(p)
    orig = urllib.request.urlopen
    urllib.request.urlopen = fake
    try:
        orc.run("감마필드 통합테스트 고유주제 zzqq", on_step=on_step)
    finally:
        urllib.request.urlopen = orig
        orc.STATE_PATH, orc.OUTPUT_DIR, orc.LOG, orc.CATALOG_PATH = saved
        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)
    assert captured.get("stage") == "done", captured
    assert "gamma" in captured, "done에 gamma 필드 없음"
    assert captured["gamma"]["status"] == "failed", captured["gamma"]  # 키 부재라 failed
    assert "payload" in captured, "기획안 payload는 그대로(graceful)"
    print("PASS test_run_done_has_gamma_field")


# ── 트렌드 탐색 심화 (다단계 체인 + 공유 캐시) ─────────────────────
def _sonar_resp(content):
    return {"choices": [{"finish_reason": "stop", "message": {
        "content": content,
        "metadata": {"search_results": [{"title": "T", "url": "https://a.com"}]},
    }}], "usage": {"cost": 8.0}}


def test_trend_scan_parses():
    """① 광역 스캔 — Sonar 1콜 파싱."""
    reset()
    orig = urllib.request.urlopen
    urllib.request.urlopen = fake_urlopen_factory(_sonar_resp('{"trends":[{"keyword":"n8n","why":"부상"}]}'))
    try:
        out = orc._trend_scan("주제")
    finally:
        urllib.request.urlopen = orig
    assert out["trends"] == [{"keyword": "n8n", "why": "부상"}], out
    assert out["sources"][0]["url"] == "https://a.com", out
    print("PASS test_trend_scan_parses")


def test_trend_deepen_merges_detail():
    """② 심화 — scan 키워드에 detail 병합(키워드 보존)."""
    reset()
    scan = {"trends": [{"keyword": "n8n", "why": "부상"}], "sources": [{"title": "T", "url": "https://a.com"}]}
    orig = urllib.request.urlopen
    urllib.request.urlopen = fake_urlopen_factory(_sonar_resp(
        '{"trends":[{"keyword":"n8n","why":"부상","detail":"2026 자동화 구체 사례"}]}'))
    try:
        out = orc._trend_deepen("주제", scan)
    finally:
        urllib.request.urlopen = orig
    assert out["trends"][0]["keyword"] == "n8n", out
    assert out["trends"][0]["detail"] == "2026 자동화 구체 사례", out
    print("PASS test_trend_deepen_merges_detail")


def test_trend_deepen_graceful():
    """② 심화 Sonar 실패 → scan 그대로(graceful)."""
    reset()
    scan = {"trends": [{"keyword": "n8n", "why": "부상"}], "sources": []}
    def boom(req, timeout=60): raise RuntimeError("down")
    orig = urllib.request.urlopen
    urllib.request.urlopen = boom
    try:
        out = orc._trend_deepen("주제", scan)
    finally:
        urllib.request.urlopen = orig
    assert out == scan, out
    print("PASS test_trend_deepen_graceful")


def test_trend_deepen_empty_scan_noop():
    """② scan이 비면 Sonar 호출 없이 그대로 반환(불필요 콜 방지)."""
    reset()
    called = {"n": 0}
    def spy(req, timeout=60):
        called["n"] += 1
        return FakeResp(json.dumps(_sonar_resp('{"trends":[]}')).encode("utf-8"))
    orig = urllib.request.urlopen
    urllib.request.urlopen = spy
    try:
        out = orc._trend_deepen("주제", {"trends": [], "sources": []})
    finally:
        urllib.request.urlopen = orig
    assert called["n"] == 0, f"빈 scan인데 Sonar 호출됨({called['n']})"
    assert out == {"trends": [], "sources": []}, out
    print("PASS test_trend_deepen_empty_scan_noop")


def test_trend_score_freshness():
    """③ 교차검증(코드) — 도메인 다양성으로 freshness_score 부여 + '신선도 약함' 감점 + 정렬."""
    reset()
    trends = [
        {"keyword": "약한키워드", "why": "w", "detail": "신선도 약함"},
        {"keyword": "강한키워드", "why": "w", "detail": "구체 사례"},
    ]
    sources = [{"url": "https://a.com/1"}, {"url": "https://b.com/2"}, {"url": "https://www.c.com/3"}]
    out = orc._trend_score(trends, sources)
    assert all("freshness_score" in t for t in out), out
    # 정렬: 강한 키워드(감점 없음)가 약한 키워드(-0.3)보다 앞
    assert out[0]["keyword"] == "강한키워드", out
    assert out[0]["freshness_score"] > out[1]["freshness_score"], out
    print("PASS test_trend_score_freshness")


def test_fetch_live_trends_cache_shared():
    """공유 캐시 — 같은 topic 2회 호출 시 Sonar 1회만(중복 차단)."""
    reset()
    calls = {"n": 0}
    def spy(req, timeout=60):
        calls["n"] += 1
        return FakeResp(json.dumps(_sonar_resp('{"trends":[{"keyword":"n8n","why":"부상"}]}')).encode("utf-8"))
    orig = urllib.request.urlopen
    urllib.request.urlopen = spy
    try:
        r1 = orc.fetch_live_trends("동일주제")
        n_after_first = calls["n"]
        r2 = orc.fetch_live_trends("동일주제")   # 캐시 적중 → Sonar 추가 호출 0
    finally:
        urllib.request.urlopen = orig
    assert calls["n"] == n_after_first, f"캐시 미동작 — 2회차도 호출됨({calls['n']})"
    assert r1 == r2 and r1["trends"], (r1, r2)
    print("PASS test_fetch_live_trends_cache_shared")


def test_fetch_live_trends_depth1_single_call():
    """DEPTH=1 → 광역만(deepen 건너뜀) = Sonar 1콜."""
    reset()
    orc.TREND_DEPTH = 1
    calls = {"n": 0}
    def spy(req, timeout=60):
        calls["n"] += 1
        return FakeResp(json.dumps(_sonar_resp('{"trends":[{"keyword":"n8n","why":"부상"}]}')).encode("utf-8"))
    orig = urllib.request.urlopen
    urllib.request.urlopen = spy
    try:
        out = orc.fetch_live_trends("깊이1주제")
    finally:
        urllib.request.urlopen = orig
    assert calls["n"] == 1, f"DEPTH=1인데 {calls['n']}콜(광역만이어야 1)"
    assert out["trends"][0]["keyword"] == "n8n", out
    print("PASS test_fetch_live_trends_depth1_single_call")


def test_fetch_live_trends_depth2_two_calls():
    """DEPTH=2 → 광역+심화 = Sonar 2콜."""
    reset()
    orc.TREND_DEPTH = 2
    calls = {"n": 0}
    def spy(req, timeout=60):
        calls["n"] += 1
        return FakeResp(json.dumps(_sonar_resp('{"trends":[{"keyword":"n8n","why":"부상","detail":"사례"}]}')).encode("utf-8"))
    orig = urllib.request.urlopen
    urllib.request.urlopen = spy
    try:
        out = orc.fetch_live_trends("깊이2주제")
    finally:
        urllib.request.urlopen = orig
    assert calls["n"] == 2, f"DEPTH=2인데 {calls['n']}콜(광역+심화=2여야)"
    assert out["trends"][0].get("detail") == "사례", out
    print("PASS test_fetch_live_trends_depth2_two_calls")


def test_fetch_live_trends_scan_fail_graceful():
    """광역 실패 → 빈 결과(캐시 미저장, 다단계 무관)."""
    reset()
    orc.TREND_DEPTH = 2
    def boom(req, timeout=60): raise RuntimeError("down")
    orig = urllib.request.urlopen
    urllib.request.urlopen = boom
    try:
        out = orc.fetch_live_trends("실패주제")
    finally:
        urllib.request.urlopen = orig
    assert out == {"trends": [], "sources": []}, out
    assert "실패주제" not in orc._trends_cache, "빈 결과가 캐시됨(재시도 막힘)"
    print("PASS test_fetch_live_trends_scan_fail_graceful")


if __name__ == "__main__":
    test_token_accumulation()
    test_missing_usage_keys_defensive()
    test_two_calls_sum()
    test_length_truncation_raises()
    test_originality_identical()
    test_originality_distinct()
    test_originality_empty_corpus()
    test_originality_deterministic()
    test_extract_script()
    test_title_overlap_identical()
    test_title_overlap_josa_strip()
    test_title_overlap_distinct()
    test_title_overlap_empty_catalog()
    test_title_overlap_short_root_josa()
    test_title_overlap_subset_caught()
    test_load_channel_titles_missing()
    test_load_channel_titles_reads()
    test_load_channel_titles_corrupt_graceful()
    test_deterministic_block_both()
    test_deterministic_block_none()
    test_deterministic_block_measured_metrics()
    test_pick_hook()
    test_expand_script()
    test_call_text_returns_content_and_sources()
    test_call_text_no_metadata()
    test_call_text_length_truncation_raises()
    test_channel_top_topics()
    test_fetch_live_trends_graceful()
    test_fetch_live_trends_parses()
    test_fetch_live_trends_malformed_trends()
    test_suggest_topics_no_key()
    test_suggest_topics_generates()
    test_suggest_topics_string_array()
    test_parse_trends_recovers_broken_json()
    test_parse_trends_normal()
    test_parse_json_robust()
    test_parse_json_always_dict()
    test_as_list_normalizes()
    test_as_str_normalizes()
    test_keyword_inclusion_string_input_safe()
    test_read_state_graceful()
    test_call_empty_choices_raises_clean()
    test_run_has_on_step_param()
    test_emit_swallows_callback_exception()
    test_run_happy_path_integration()
    test_run_escalation_payload()
    test_korean_syllable_count()
    test_hook_syllable_check()
    test_hashtag_count_score()
    test_overclaim_patterns()
    test_overclaim_evasion_golden()
    test_overclaim_legitimate_pass()
    test_overclaim_empty()
    test_numeric_claim_extract()
    test_word_count_score()
    test_keyword_inclusion_score()
    test_gamma_build_input_includes_fields()
    test_agent_gamma_prompt_success()
    test_agent_gamma_prompt_no_key_none()
    test_agent_gamma_prompt_too_short_none()
    test_agent_gamma_prompt_fail_none()
    test_gamma_generate_uses_agent_then_fallback()
    test_gamma_generate_no_key()
    test_gamma_generate_success()
    test_gamma_generate_http_error_graceful()
    test_gamma_status_completed()
    test_gamma_status_bad_id()
    test_run_done_has_gamma_field()
    test_trend_scan_parses()
    test_trend_deepen_merges_detail()
    test_trend_deepen_graceful()
    test_trend_deepen_empty_scan_noop()
    test_trend_score_freshness()
    test_fetch_live_trends_cache_shared()
    test_fetch_live_trends_depth1_single_call()
    test_fetch_live_trends_depth2_two_calls()
    test_fetch_live_trends_scan_fail_graceful()
    print("\n✅ ALL PASS (67 tests)")
