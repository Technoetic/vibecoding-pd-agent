---
description: 4-에이전트 오케스트레이션으로 쇼츠/틱톡 기획안을 생산한다
argument-hint: "기획 주제 (예: 개발 없이 5일 만에 수익 웹서비스 비법)"
---

# /pd — AI 콘텐츠 PD 오케스트레이션

주제: **$ARGUMENTS**

## 실행 방식 — 두 모드

### 모드 A: 자동 오케스트레이터 (BizRouter 키가 있을 때, 권장)
`google/gemini-2.5-flash-lite`로 4-에이전트를 실제 호출하는 `orchestrator.py`를 돌린다.

```bash
python "50-projects/content-pd-agent/orchestrator.py" "$ARGUMENTS"
```

- 사전조건: `BIZROUTER_API_KEY` 환경변수. 비어 있으면 스크립트가 안내 후 종료 → 모드 B로 전환.
- 스크립트가 Supervisor→Trend Analyst→Creator→Reviewer(Eval 루프)를 자동 수행하고,
  `State.json` 갱신·`output/CONTENT_2026_NNN.md` 기록·`00-meta/log.md` 로깅·비용 집계까지 끝낸다.
- 실행 후 산출물 경로와 핵심 결과(제목·훅·비용)를 사용자에게 브리핑한다.
- 동작 원리는 [[오케스트레이션 아키텍처]] 참조.

### 모드 B: 인-세션 연기 (키 없이, Claude가 직접)
키가 없으면 네가 [[supervisor]]로서 4개 페르소나를 순차 연기한다. 각 단계 사이 `State.json`을 읽고/쓰며 핸드오프:

1. **초기화** — `context.md`·`handoff.md` 읽고, `task_id` 발급, `status: pending_analysis`.
2. **[[trend-analyst]]** — `20-knowledge/` 분석 → `keywords[]`·`hooks[]` → `drafting`.
3. **[[creator]]** — 스크립트(100~250단어)+스토리보드+썸네일 프롬프트+해시태그 → `pending_review`.
4. **[[reviewer]]** — `eval_scenarios.json` 5종 assert. 전부 Pass→`approved`+`output/`기록(`[승인대기]`), Fail→`rejected`+`feedback_log`→Creator 복귀(`retry_count` > `max_retries`면 에스컬레이션).
5. **마무리** — `00-meta/log.md` 최상단 1줄 기록, 사용자 브리핑.

**그로스 해커 원칙:** 예술이 아니라 CTR·체류시간·수익 전환. 모든 결과물은 클릭과 수익 메시지가 명확해야 한다.
