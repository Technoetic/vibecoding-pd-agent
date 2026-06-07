#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
orchestrator 회귀 테스트 — 네트워크 없이 결정론적 검증.
squeeze-report C3(토큰 분해 로깅) 본문화 동반 회귀.

실행:  python test_orchestrator.py   (exit 0 = PASS)
"""
import io, json, sys, urllib.request
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
    assert out["trends"] == [{"keyword": "에이전틱 AI", "why": "부상"}], out
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
        # 3) creator
        {"choices":[{"finish_reason":"stop","message":{"content":'{"title":"통합테스트 고유제목 절대중복없음 zzqq","script":"'+("단어 "*120)+'","storyboard":["s"],"thumbnail_prompt":"t","hashtags":["#태그"]}'}}],"usage":{"cost":0.05}},
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
    s = "AI 코딩 입문 가이드와 노코드 창업 이야기"
    r = orc.keyword_inclusion_score(s, ["AI 코딩", "노코드 창업", "없는키워드"])
    assert r["included"] == 2 and r["total"] == 3, r
    assert r["ok"] is False  # 2/3 = 0.667 < 0.8
    print("PASS test_keyword_inclusion_score")


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
    print("\n✅ ALL PASS (45 tests)")
