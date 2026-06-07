# AI 콘텐츠 PD 에이전트 — 실시간 구동 데모 + 채널 중복 방지 (설계)

> 작성: 2026-06-07 · 목적: 양실장의 바이브코딩대학 **PD/영상편집 채용 과제** 제출용
> 과제 = "AI 콘텐츠 PD 에이전트". 이 데모는 심사자가 링크 하나로 시스템 전체를 이해하게 만드는 **실시간 구동 쇼케이스**다.

## 0. 배경 — 왜 이걸 만드는가

채널 `@VibecodingUniversity`(양실장의 바이브코딩대학, 구독자 14,900, 영상 73개)의 PD 채용 과제다.
- 2026-05-31 "콘텐츠 PD 구인 영상", 2026-06-06 "PD 지원자에게 내준 과제 나도 해보기" — 과제 맥락 확인됨.
- 제출물은 우리가 만든 4-에이전트 오케스트레이터(`orchestrator.py`)이고, 데모는 그 작동을 심사자에게 **눈앞에서 증명**한다.

### 🚨 데이터로 증명된 핵심 결함 (이 설계의 출발점)
실제 채널 73개 영상 제목과 우리 기획안을 대조하니:
- 기획안 CONTENT_2026_001 **"개발 없이 5일 만에 수익 웹서비스 만드는 비법"** ↔ 채널 실제 영상 **"개발 없이 5일 만에 수익 웹서비스 비법 공개! #바이브코딩"** = 제목 유사도 **0.746**.

즉 **현재 시스템은 채널에 이미 있는 콘텐츠를 중복 생성한다.** 현 `originality_check`는 "우리가 만든 기획안끼리만" 비교하고 **채널 실제 영상은 전혀 안 본다.** 채용 과제에서 이건 치명적이다("이 PD는 우리 채널을 모른다"). → **채널 중복 방지를 반드시 추가한다.**

---

## 1. 범위 — 세 개의 작업

| # | 작업 | 한 줄 |
|:--|:--|:--|
| **A** | 채널 중복 방지 | YouTube 채널 카탈로그 수집 → 제목 자카드 대조 → 중복이면 강제 반려(별도 메트릭) |
| **C** | 트렌드 에이전트 | 채널 인기 주제(조회수) + Perplexity Sonar 실시간 LLM/바이브코딩 트렌드(출처 포함)를 Trend Analyst에 주입 |
| **B** | 실시간 구동 데모 | 주제 입력 → `orchestrator.py` 실시간 구동 → 단계 진행 + 결과 + 아키텍처 표시 → Railway 배포 |

순서: A·C(백엔드 강화) 먼저 → B(데모가 A·C 결과를 화면에 보여줌). A와 C는 같은 `channel_catalog.json`을 공유해 시너지.

---

## 2. 작업 A — 채널 중복 방지

### 2.1 데이터 소스 (이미 확보됨)
- `channel_catalog.json` — **이미 생성됨**(YouTube Data API v3, 73개 영상 제목·게시일·조회수). 키 `YOUTUBE_API_KEY` 검증 완료.
- 갱신 스크립트 `youtube_fetch.py`(신규) — 핸들→uploads playlist→playlistItems 페이지네이션→videos.list로 조회수 병합. urllib만(의존성 0). 재실행하면 카탈로그 최신화.
- **컴플라이언스:** 카탈로그엔 검증된 **제목·게시일·조회수만**. 구독자수·법인정보 등 미검증 수치 절대 금지([[수익 강조 콘텐츠 법적 신뢰 리스크]] 하드룰).

### 2.2 알고리즘 — 제목은 자카드, 스크립트는 difflib (분리)
조사 실측으로 검증:
- 어순만 바뀐 동일 주제("AI로 비개발자가 만든 첫 앱" vs "비개발자가 AI로 만든 첫 앱"): **char-level SequenceMatcher = 0.75 (놓침)**, 토큰 자카드 = 1.0 (포착).
- 따라서 **제목 대조는 토큰 자카드**로 별도 구현. 기존 스크립트 대조(difflib)는 그대로 둔다.

신규 함수 `title_overlap_score(draft_title, catalog_titles, thresh=0.6)`:
- 반환 `{max_jaccard, most_similar_title, is_distinct}` (is_distinct = max_jaccard < thresh)
- 토큰화: 공백 split + 한국어 조사 꼬리 제거 정규식(은/는/이/가/을/를/의 등). **형태소 분석기 금지**(의존성 0 ADR 위반).
- 임계 0.6~0.7 (자카드 기준. char용 0.85 재사용 금지).

### 2.3 통합 지점 (orchestrator.py — 검증된 줄번호)
| 위치 | 변경 |
|:--|:--|
| 상수부(~24-26) | `CATALOG_PATH = HERE / "channel_catalog.json"` 추가 |
| 신규 함수 | `load_channel_titles()` — **파일 없으면 `[]` 반환(graceful: 검사 무력화, 파이프라인 안 깨짐)**. `title_overlap_score()` |
| run() originality 계산 직후(~329-335) | `channel = title_overlap_score(title, load_channel_titles())` 호출, payload에 `channel_dup` 저장, print 1줄 |
| 결정론 강제 반려 블록(~344-350) | OR 분기 추가: `if (not orig['is_original'] or not channel['is_distinct']) and verdict=='approved': rejected`. **사유 메시지는 originality와 channel_dup을 분리**해 append(Creator가 뭘 고칠지 명확하게) |
| agent_reviewer() orig_fact 주입부(~211-217) | `channel_fact` 문자열 추가 주입(최대 자카드·임계·is_distinct, "추측 금지"). **카탈로그 전체가 아니라 상위 1~3개 유사 제목만**(토큰·비용 절약) |
| eval_scenarios.json | **`channel_dup_check` 별도 메트릭 신규 추가**(originality_check에 합치지 않음 — rule/알고리즘/필드가 달라 합치면 자기모순) |

### 2.4 함정 (조사에서 확인)
- 카탈로그 없을 때 예외/강제반려로 빠지면 **모든 task가 막힘** → 반드시 빈 리스트 graceful degrade.
- 채널 "검증된 앵글 풀"(예: "개발 없이 N일 만에 수익 X")은 [[양실장 바이브코딩대학 채널 분석]]이 **의도적 재사용을 권장** → 제목 전체 유사도만 보고, 앵글 키워드 포함 자체는 페널티화 금지.

---

## 2-C. 작업 C — 트렌드 에이전트 (Trend Analyst 강화)

### 2-C.1 문제
현 Trend Analyst는 `20-knowledge/`의 **정적 지식만** 읽어 "개발 없이 수익" 같은 일반론에 머문다. 실제 채널 인기작은 "젬마4 RAG 챗봇", "GPT/제미나이 이해 강의" 같은 **최신 기술 트렌드**다. → 두 종류의 실시간 신호 주입.

### 2-C.2 두 신호 소스 (둘 다 검증 완료)
| 신호 | 소스 | 검증 |
|:--|:--|:--|
| **채널 인기 주제** | `channel_catalog.json` 조회수 상위 N개 제목 | ✅ 확보(상위: 외주창업 64.5k, 프론트엔드 기초 50.7k, DB/스토리지 32.7k…) |
| **외부 LLM/바이브코딩 트렌드** | **Perplexity Sonar**(`perplexity/sonar` via BizRouter) | ✅ 가용. 키 추가 불필요 |

### 2-C.3 Perplexity Sonar — 검증된 사실 (라이브 probe)
- BizRouter에서 `perplexity/sonar`·`perplexity/sonar-pro` **둘 다 가용**(추가 키 0).
- **`response_format: json_object` 미지원**(400) → 프롬프트로 순수 JSON 유도(안정적으로 동작 확인).
- **출처는 `choices[0].message.metadata.search_results`에 있음** — `{title, url, snippet}` 배열. 최상위 `citations`/`search_results`는 None이니 **metadata에서 꺼낸다.**
- **비용: 호출당 ~8원**(sonar), ~10.6원(sonar-pro). flash-lite(0.05원)의 약 150~200배.
- 실측 트렌드 예: "에이전틱 AI", "AI 네이티브 개발 플랫폼", "팀 협업 바이브코딩", "n8n·Make 자동화", "자동 보안 검증" — 2026 실제 화두 + 실제 출처 URL.

### 2-C.4 호출 전략 — **매 /pd마다 호출** (사용자 결정)
- 매 기획마다 Sonar 실시간 호출 → 가장 신선한 트렌드. 데모 "진짜 실시간" 임팩트 최대.
- **비용 영향: 기획 1건당 ~8원(Sonar) + flash-lite ~3원 = ~11원.** State.json `cost_krw`에 합산 기록(투명).
- 모델 상수는 `orchestrator.py`에 `TREND_MODEL = "perplexity/sonar"`로 분리(flash-lite MODEL과 별개).

### 2-C.5 통합 지점 (orchestrator.py)
| 위치 | 변경 |
|:--|:--|
| 상수부 | `TREND_MODEL = "perplexity/sonar"` 추가 |
| 신규 함수 | `fetch_live_trends(topic) -> {trends:[{keyword,why}], sources:[{title,url}]}` — Sonar 호출, **metadata.search_results에서 출처 추출**. 실패/타임아웃 시 `{trends:[], sources:[]}` graceful(파이프라인 안 깸) |
| 신규 함수 | `channel_top_topics(n=10) -> [제목]` — catalog 조회수 상위 |
| `call()` 재사용 | Sonar는 json_object 미지원이라 **call()에 `use_json=False` 분기 추가** 또는 별도 `call_text()`. 출처 metadata 반환 위해 응답에서 metadata도 꺼내야 함 |
| `agent_trend_analyst()`(179-185) | user 프롬프트에 채널 인기주제 + 라이브 트렌드(+출처) 주입. **출처는 그대로 전달하되 "검증된 출처만 인용, 없으면 단정 금지"** 명시 |
| `run()` Trend Analyst 단계(311-317) | `fetch_live_trends` 먼저 호출 → emit('trend-live', trends, sources) → agent_trend_analyst에 전달 |

### 2-C.6 함정·원칙
- **가짜 인용 금지(하드룰):** Sonar 출처(metadata.search_results)는 진짜 URL이라 OK. 단 출처 없는 트렌드를 기획 근거로 단정 금지 → "트렌드로 거론됨" 수준 프레이밍.
- **비용 투명성:** Sonar 비용을 cost_krw에 합산하고 데모 화면에 "트렌드 조사(Sonar) X원 + 생성(flash-lite) Y원" 분리 표시.
- **graceful:** Sonar 실패해도 채널 인기주제 + 정적 지식으로 기획은 진행(트렌드 0건이어도 안 깨짐).
- **온도:** Sonar는 사실조사라 temperature 0.2.

---

## 3. 작업 B — 실시간 구동 데모

### 3.1 아키텍처
```
[브라우저] web/index.html (바닐라 JS, 인라인 CSS, 의존성 0)
   │ ① POST /api/pd {topic}  ② SSE로 단계 수신  ③ done에 결과 렌더
   ▼
[server.py] http.server.ThreadingHTTPServer (표준 라이브러리만)
   │ - 정적 서빙(/)  - /api/pd SSE  - /api/samples(폴백)
   │ - BIZROUTER_API_KEY·YOUTUBE_API_KEY는 서버 환경변수에서만 (브라우저 노출 0)
   ▼
[orchestrator.py] 4-에이전트 (gemini-2.5-flash-lite) + on_step 콜백 1개 주입
   ▼
[Railway] Dockerfile(python:3.12-slim) → 공개 URL
```

**3대 원칙:**
1. **의존성 0 유지** — `http.server`로 SSE 직접 구현. Flask/FastAPI 안 씀(orchestrator 철학 일관).
2. **키는 server 환경변수에만** — 브라우저는 키를 못 봄(CardForge 프록시 선례).
3. **orchestrator 최소 침습** — `on_step` 콜백 하나만. 검증된 4-에이전트·Eval·originality 로직 불변(회귀 9건 보존).

### 3.2 orchestrator.py 콜백 주입 (검증된 줄번호)
- `run(topic, on_step=None)`로 확장 — 기본값 None이라 **기존 CLI 호출(387줄) 무수정 동작**.
- 내부 헬퍼 `emit(stage, **data)` — 모든 진행 알림 한 곳 통일. on_step 없으면 no-op.
- 14개 print 위치를 emit로 병행/대체: `supervisor`(308) `trend-analyst`(311/317) `creator`(322) `originality`(334) `reviewer`(337/342/350) `done`(360-363) `rejected`(372) `escalated`(380-381).
- **emit 페이로드 최소화** — script/storyboard 전문은 SSE로 안 흘림(done에서만). stage별 필요한 필드만.

### 3.3 SSE 이벤트 흐름
```
POST /api/pd {topic}
 → step  {stage:"supervisor", task_id, topic}
 → step  {stage:"trend-live", trends:[{keyword,why}], sources:[{title,url}]}  ← 작업 C(Sonar 실시간)
 → step  {stage:"trend-analyst", phase:"start"} → {phase:"done", keywords, hooks}
 → step  {stage:"creator", retry:0}
 → step  {stage:"originality", max_similarity, is_original}
 → step  {stage:"channel-dup", max_jaccard, is_distinct}        ← 작업 A 결과
 → step  {stage:"reviewer", phase:"check", metric, pass, comment} ×8
 → step  {stage:"creator", retry:1}     ← 반려 시 루프 시각화
 → done  {payload:{title,script,storyboard,thumbnail_prompt,hashtags}, eval[8], cost_krw, token_usage, verdict}
```

### 3.4 화면 구성 (결과: 산출물 + 검수 투명성 + 아키텍처)
1. **입력** — 주제 입력 + "기획 생성" 버튼. (예시 주제 칩 몇 개)
2. **진행바** — Supervisor→(트렌드 조사)→Analyst→Creator→Reviewer 단계별 체크. 반려 시 retry 회차 표시.
3. **라이브 트렌드 패널** — Sonar가 가져온 실시간 트렌드 키워드 + **출처 링크**(작업 C). "지금 이 순간의 트렌드를 반영한다" 임팩트.
4. **결과 카드** — 제목·🎬스크립트·🖼스토리보드·🎨썸네일프롬프트·🏷해시태그 (`[승인대기]` 뱃지).
5. **검수표** — Eval **8종** + 채널중복검사 1종. metric·기준·✅/❌·코멘트. originality는 "코드 실측 주입"으로 표기(LLM 판단 아님). 채널중복은 "73개 영상 대조".
6. **비용/토큰** — "트렌드 조사(Sonar) X원 + 생성(flash-lite) Y원" 분리 + 총합·토큰(투명성).
7. **아키텍처 섹션** — 4-에이전트 카드(역할+온도 0.8/0.8/0.2) + 핵심 설계 5종 + 트렌드 소스(채널 조회수 + Sonar 실시간).

### 3.5 결과화면 "아키텍처 설명" 6종 (ORCHESTRATION.md 인용)
1. **온도 차등** 0.8/0.8/0.2 — 발산(발상·창작) vs 수렴(판정).
2. **flash-lite 단일모델** — 호출당 ~0.05원, TTFT 0.29초, 1회 기획 <1원. "모델이 아니라 프롬프트가 전문성을 만든다."
3. **Eval 루프** — 8종 전부 Pass 전 노출 금지, max_retries 3.
4. **originality + 채널 중복 실측** — difflib(스크립트) + 토큰 자카드(채널 73개 영상 제목) 결정론·의존성 0. **LLM 추측이 아니라 코드 실측 주입.**
5. **한국 규제** — FTC + **한국 표시광고법·추천보증 심사지침(뒷광고 금지)**을 income_claim_compliance가 차단.
6. **실시간 트렌드(하이브리드 모델)** — 채널 조회수 상위(flash-lite 무관) + Perplexity Sonar 실시간 웹검색(출처 포함). **사실조사는 Sonar, 생성·판정은 flash-lite — 모델을 용도별로 쓴다.**

### 3.6 에러·엣지 (조사 함정 반영)
- **키 없음:** orchestrator의 `sys.exit`(290줄)는 서버에서 프로세스를 죽임 → on_step 있을 때(서버 경로)는 `emit('error')+raise`로 전환, CLI(`__main__`)는 sys.exit 유지. 프론트는 에러 안내 + `/api/samples` 폴백 표시.
- **샘플 폴백:** API 키 없거나 비용 우려 시 사전 생성 **5건(001/003/004/005/006 — 002 없음)** 정적 표시. 데모가 절대 빈 화면 안 됨.
- **에스컬레이션:** retry 3회 초과면 `done {verdict:"escalated"}` — "검수 미달 반려"를 정직하게 표시(시스템이 정직하다는 증거).
- **예외 누수:** call()의 HTTP/잘림 에러가 위로 전파되면 SSE가 무한대기 → 서버가 잡아 `error` 이벤트로 종결.
- **동시성:** 데모는 **요청 직렬화(큐 1개)** — 전역 `cost_total`/`token_usage` 교차오염·`next_task_id` 충돌·State.json last-writer-wins 레이스를 큐로 회피(가장 단순). State 쓰기는 데모 모드에서 옵션화 가능.
- **SSE 구현:** `text/event-stream` + `no-cache` + `keep-alive` + **`X-Accel-Buffering: no`**(Railway 엣지 버퍼링 대비). `wfile.flush()` 필수. 클라 끊김 `BrokenPipeError` try/except.

### 3.7 배포 (Railway)
- `Dockerfile`(대문자 D, 리포 루트): `FROM python:3.12-slim` → `COPY` → **`CMD python server.py`(shell form — exec form은 $PORT 미확장 실패)**.
- server는 `int(os.environ.get('PORT', 8000))`, `('0.0.0.0', port)` 바인딩(127.0.0.1 금지).
- `railway.json`: builder DOCKERFILE, startCommand `python server.py`, healthcheckPath `/`, restartPolicy ON_FAILURE.
- 환경변수 `BIZROUTER_API_KEY`·`YOUTUBE_API_KEY`는 Railway 서비스 Variables 탭으로만(코드·이미지 하드코딩 금지).
- 헬스체크(`/`)가 SSE 장기연결에 막히지 않게 ThreadingHTTPServer로 분리.

---

## 4. 파일 목록 (신규/수정)

| 파일 | 신규/수정 | 역할 |
|:--|:--|:--|
| `channel_catalog.json` | ✅ 신규(생성됨) | 73개 영상 제목·조회수 |
| `youtube_fetch.py` | 신규 | 카탈로그 갱신(urllib) |
| `orchestrator.py` | 수정 | `on_step` 콜백 + 채널중복(`load_channel_titles`/`title_overlap_score`) + 트렌드(`fetch_live_trends`/`channel_top_topics`, `TREND_MODEL`) |
| `eval_scenarios.json` | 수정 | `channel_dup_check` 메트릭 추가 |
| `test_orchestrator.py` | 수정 | 콜백·채널중복·트렌드(mock) 회귀 추가(기존 9건 보존) |
| `server.py` | 신규 | http.server SSE + 정적 서빙 + 키 격리 |
| `web/index.html` | 신규 | 단일 페이지 데모 UI |
| `web/samples.json` | 신규 | 폴백 5건 |
| `Dockerfile` | 신규 | python:3.12-slim |
| `railway.json` | 신규 | 배포 설정 |
| `README.md`(데모) | 신규 | 로컬 실행·배포 안내 |

## 5. 테스트 전략
- `server.py`: SSE 포맷·키 부재 처리·정적 서빙·샘플 폴백을 `unittest`로(**모델 호출 mock** → 키 없이 CI 통과).
- orchestrator: 기존 9건 + `on_step` 호출 검증 + `title_overlap_score` 자카드 + 카탈로그 부재 graceful + `fetch_live_trends` 실패 시 graceful(Sonar mock).
- 배포 전 로컬 종단: 키 넣고 `python server.py` → 브라우저 실제 1회 구동(트렌드 패널·출처 링크·검수표 확인).

## 6. 비범위 (YAGNI)
- 사용자 인증·다중 사용자·DB — 데모 불필요.
- 실시간 SSE 토큰 스트리밍(글자 단위) — 단계 단위로 충분.
- 틱톡/롱폼 — eval은 쇼츠(100~250단어) 고정. 데모는 쇼츠 명시.
- State.json 영구 기록 — 데모는 옵션(동시성 회피 위해 기본 off 가능).
