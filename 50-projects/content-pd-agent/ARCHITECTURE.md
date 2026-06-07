---
title: "오케스트레이션 아키텍처 종합"
type: concept
status: active
ai_priority: high
created: 2026-06-07
updated: 2026-06-07
tags:
  - project
  - architecture
related:
  - "[[ORCHESTRATION]]"
  - "[[decisions]]"
  - "[[content-pd-agent context]]"
---

# 오케스트레이션 아키텍처 종합

AI 콘텐츠 PD 에이전트의 **현재 전체 구조 한눈에 보기**. 상세 설계 근거는 [[ORCHESTRATION]], 결정 이력은 [[decisions]](ADR 17개) 참조. 본 문서는 "무엇이 어디서 어떻게 흐르는가"의 종합 지도.

## 1. 한 줄 정의

> 양실장 바이브코딩대학 채널용 쇼츠/틱톡 기획안을 **4-에이전트가 생산하고 12종 Eval로 검수**하는 자율 오케스트레이터. BizRouter × gemini-2.5-flash-lite 단일모델 + Perplexity Sonar 실시간 트렌드. **표준 라이브러리만(의존성 0).**

## 2. 시스템 다이어그램

```
사용자: /pd "주제"  또는  POST /api/pd {topic}
        │
        ▼
┌─────────────────────────────────────────────────────────────┐
│ orchestrator.py  run(topic, on_step)   [상태머신: State.json] │
│                                                               │
│  0. Supervisor ── task 발급(CONTENT_2026_NNN), 라우팅          │
│        │ emit("supervisor")                                    │
│        ▼                                                       │
│  1. 트렌드 조사 ── fetch_live_trends() → Perplexity Sonar      │
│        │ 실시간 웹검색 트렌드 + 출처(metadata.search_results)  │
│        │ + channel_top_topics() 채널 조회수 상위               │
│        │ emit("trend-live", trends, sources)                  │
│        ▼                                                       │
│  2. Trend Analyst ── agent_trend_analyst() [temp 0.8]         │
│        │ 채널주제+트렌드+20-knowledge → keywords[]·hooks[]     │
│        │ emit("trend-analyst")                                 │
│        ▼                                                       │
│  ┌── while (Eval 루프, max_retries=3) ──────────────────┐    │
│  │ 3. Creator ── agent_creator() [temp 0.8]              │    │
│  │      script·storyboard·thumbnail·hashtags            │    │
│  │      emit("creator", retry)                           │    │
│  │      ▼                                                 │    │
│  │ 4. 결정론 측정 (코드 실측 — LLM 추측 대체):           │    │
│  │      originality_score()  난독 difflib                │    │
│  │      title_overlap_score() 채널 73영상 자카드+overlap │    │
│  │      script_density_score() 한국어 음절               │    │
│  │      hashtag_count_score() 해시태그 개수              │    │
│  │      overclaim_check()·extract_numeric_claims() 팩트  │    │
│  │      → 전부 content_payload에 저장(Reviewer가 받음)    │    │
│  │      emit("originality"/"channel-dup")                │    │
│  │      ▼                                                 │    │
│  │ 5. Reviewer ── agent_reviewer() [temp 0.2]            │    │
│  │      eval_scenarios.json 12종 검수 + 실측값 주입       │    │
│  │      emit("reviewer", metric, passed, comment) ×12    │    │
│  │      ▼                                                 │    │
│  │ 6. deterministic_block(orig, channel)                │    │
│  │      originality·channel_dup 임계 초과면 강제 rejected │    │
│  └──────────────────────────────────────────────────────┘    │
│        │                                                       │
│   approved ──→ write_output() output/CONTENT_*.md [승인대기]   │
│        │       append_log() 00-meta/log.md                    │
│        │       emit("done", payload, cost, tokens, eval)      │
│   rejected ──→ feedback_log → retry++ → Creator 복귀          │
│   3회 초과 ──→ emit("escalated") 사용자 에스컬레이션           │
└─────────────────────────────────────────────────────────────┘
        │
        ▼ (웹 데모일 때)
server.py [http.server SSE] ── 단계별 진행 → web/index.html 렌더
```

## 3. 4-에이전트 (페르소나 = 00-meta/personas/)

| 에이전트 | temp | 역할 | 산출 |
| :-- | :-- | :-- | :-- |
| **Supervisor** | — | task 분해·State 발급·라우팅 (창작 안 함) | task_id, 상태 전이 |
| **Trend Analyst** | 0.8 | 채널주제+Sonar트렌드+지식 분석 → 발상 | keywords[]·hooks[] |
| **Creator** | 0.8 | 톤앤매너+훅 융합 작성 | script·storyboard·thumbnail·hashtags |
| **Reviewer** | 0.2 | Eval 12종 판정 (수렴) | verdict·checks[]·feedback |

**핵심: 모델이 아니라 프롬프트(페르소나 .md)가 전문성을 만든다.** 같은 flash-lite를 온도 차등(발산 0.8 / 수렴 0.2)으로 분리.

## 4. Eval 12종 (eval_scenarios.json) — 결정론 측정 vs LLM 판정 분리

| 측정 방식 | 메트릭 |
| :-- | :-- |
| **코드 실측(LLM 추측 차단)** | originality_check·channel_dup_check·korean_syllable_density·hashtag_count·**word_count·keyword_inclusion**·factual_accuracy(overclaim 패턴+수치) |
| **LLM 종합 판정** | format_compliance·security_check·income_claim_compliance·hook_concreteness_context·retention_design |
| **강제 반려(2-티어, 맥락무관 하드위반)** | originality(≥0.85)·channel_dup(≥0.6)·**hook 음절(>21)·해시태그(범위 밖)** (deterministic_block 4인자) |
| **soft(맥락의존, Reviewer 종합)** | 본문 음절 상한·overclaim flag(false-positive 거름) |

> ADR-018: 적대적 검증이 "측정했으나 무시됨" 누수(009 hook 22음절 승인)·overclaim 회피·length LLM위임을 잡아 수정. length/keyword 결정론화, 강제반려 2→4종(하드위반만), overclaim 회피 6종 골든셋 고정.

→ 선정 근거·ADR 매핑은 [[ORCHESTRATION]] "Eval 설계철학" 절.

## 5. 파일 맵

| 파일 | 역할 |
| :-- | :-- |
| `orchestrator.py` | 4-에이전트 + 12 측정함수 + run() 상태머신 + on_step SSE 콜백 |
| `eval_scenarios.json` | Eval 12종 정의(Reviewer 검수 기준) |
| `State.json` | 오케스트레이션 상태 머신(tasks[] 핸드오프 페이로드) |
| `channel_catalog.json` | 양실장 채널 73개 영상 제목·조회수(중복검사·트렌드용) |
| `youtube_fetch.py` | 카탈로그 갱신(YouTube Data API, urllib) |
| `server.py` | http.server SSE 데모 서버 + 폴백 + 키 격리 |
| `web/index.html` | 데모 UI(단계표시·트렌드·검수표·아키텍처) |
| `Dockerfile`·`railway.json` | Railway 배포 |
| `test_orchestrator.py`·`test_server.py` | 회귀 45건 |
| `00-meta/personas/*.md` | 4-에이전트 페르소나(system 프롬프트) |
| `20-knowledge/{hooks,scripts,trends}/` | LLM 위키(검수 근거 지식) |
| `output/CONTENT_*.md` | 승인 기획안 산출물 |
| `decisions.md` | ADR 17개(설계 결정 이력) |
| `PORTFOLIO.md`·`SESSION_LOG.md` | 채용 제출물(대표작·실행 증빙) |

## 6. 외부 의존 (API)

- **BizRouter** (OpenAI 호환): `gemini-2.5-flash-lite`(4-에이전트, json_object) + `perplexity/sonar`(트렌드, 웹검색). 키 `BIZROUTER_API_KEY`.
- **YouTube Data API v3**: 채널 카탈로그 수집. 키 `YOUTUBE_API_KEY`(카탈로그 갱신 시만).
- 키는 **서버 환경변수에서만** — 브라우저 노출 0.

## 7. 불변 원칙 (설계 철학)

1. **의존성 0** — 표준 라이브러리만(urllib·http.server·difflib·json·re). pip install 금지.
2. **결정론 측정 + LLM 분리** — 코드가 실측해 주입, LLM은 "가정" 금지(가짜 통과 차단).
3. **Eval 통과 전 노출 금지** — 12종 전부 Pass + `[승인대기]`만 output 기록.
4. **컴플라이언스** — 수익 단정·가짜 인용 금지(FTC·한국 표시광고법, 교육채널 신뢰).
5. **graceful degrade** — 카탈로그·트렌드 없어도 파이프라인 안 깨짐.
6. **비용 투명성** — token_usage·cost_krw 실측 기록(BizRouter usage).

## 8. 진화 요약 (ADR)

eval 8종 → 12종(+채널중복·음절·해시태그·팩트체크). 모델 2.5-flash-lite 유지(3.1 단가 2.85배라 보류). Sonar 트렌드 추가. 4종 외부 딥리서치 + 8종 _가이드 전부 처리. → [[decisions]]
