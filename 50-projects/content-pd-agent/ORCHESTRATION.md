---
title: "오케스트레이션 아키텍처"
type: concept
status: active
ai_priority: high
created: 2026-06-07
updated: 2026-06-07
tags:
  - project
  - orchestration
related:
  - "[[content-pd-agent context]]"
  - "[[supervisor]]"
---

# 오케스트레이션 아키텍처 — google/gemini-2.5-flash-lite 단일 모델

`orchestrator.py`가 4-에이전트 파이프라인을 BizRouter(`google/gemini-2.5-flash-lite`)로 실제 호출해 구동한다. 상태는 `State.json`, 검수 기준은 `eval_scenarios.json`.

> **모델 정책(2026-06-07, ADR-006):** 2.5-flash-lite **유지**. 3.1-flash-lite 교체를 1회 실증(회귀 9건·`/pd` 종단 CONTENT_2026_006 승인)했으나 **단가 2.85배**라 비용 사유로 되돌림. 종료(2026-10-16)까지 여유 있어 stable horizon(2026-07-22) 임박 시 `MODEL` 1줄 교체 예정. 교체 가용성·절차는 이미 실증됨.

## 백엔드 검증 결과 (2026-06-07 실측)

| 항목 | 결과 | 설계 반영 |
| :-- | :-- | :-- |
| `response_format: json_object` | ✅ 동작 (2.5·3.1 양쪽 확인) | 에이전트 출력은 모두 JSON, 프롬프트에 스키마 명시 |
| `response_format: json_schema` (strict) | ❌ Google `response_schema`로 변환되며 `additionalProperties` 충돌 → 400 | strict 스키마 미사용 |
| `usage` 키 (prompt/completion/total/cost) | ✅ 동작 | ADR-005 토큰 로깅 |
| Eval 8종 채점 | ✅ 8개 메트릭 전부 동작 (originality 실측·income_claim 한국규제 차단 포함) | G1·G3 통합 검증 |
| system 역할 분리 | ✅ 페르소나 .md를 system 프롬프트로 주입 가능 | 각 에이전트 = 페르소나 .md + 출력 스키마 |
| 호출당 비용 | 약 0.05원 (112토큰 기준), 1회 기획(재시도 포함) ≈ 0.2~0.5원 | 저단가 — 2.5 유지 사유 |
| (참고) 3.1-flash-lite 단가 | 2.5 대비 **약 2.85배** (CONTENT_2026_006 ≈0.00055원/토큰) | 교체 시 비용 모니터링 필요 |

## 파이프라인 (상태 머신)

```
[Supervisor] task 발급 → pending_analysis
      ↓
[Trend Analyst]  20-knowledge 분석 → keywords[]·hooks[]        → drafting
      ↓
[Creator]        스크립트·스토리보드·썸네일·해시태그           → pending_review
      ↓
[Reviewer]       eval_scenarios 8종 assert
      ├─ 전부 Pass → approved → output/CONTENT_*.md (`[승인대기]`)
      │              ↓
      │         [Gamma] 승인 즉시 프레젠테이션 생성요청(블로킹 0) → done에 gamma{id,status}
      │              ↓  (클라가 /api/gamma 폴링 → PDF 새 탭. 실패해도 기획안은 정상 — graceful)
      └─ Fail → rejected + feedback_log → retry_count+1 → Creator로 복귀
                 (retry_count > max_retries → 에스컬레이션 후 중단. 미승인은 슬라이드화 안 함)
```

## 단일 모델 전략 (왜 flash-lite 하나로 충분한가)

- **속도·비용:** TTFT 0.29초, 호출당 0.05원. 4-에이전트 × 재시도를 돌려도 1원 미만.
- **구조화 출력:** `json_object`로 에이전트 간 핸드오프 무결성 확보 — A의 출력이 변환 없이 B의 입력으로.
- **역할 분리:** 같은 모델이라도 system 프롬프트(페르소나)로 4개 인격을 분리. 모델이 아니라 **프롬프트가 전문성을 만든다.**

## 온도(temperature) 차등 — 설계 근거

같은 flash-lite를 단계별로 온도만 바꿔 "발산"과 "수렴"을 분리한다. 외부 설계 가이드(`_가이드/단일 경량 모델…오케스트레이션 설계 및 파이프라인 구현 상세 가이드.md`)가 동일 패턴을 권장 — 사실 기반/판정은 낮은 온도(0.1~0.2), 창의적 종합은 약간 높은 온도(0.4).

| 에이전트 | temperature | 근거 |
| :-- | :-- | :-- |
| Trend Analyst | 0.8 | 키워드·훅 **발상** — 다양성 확보 |
| Creator | 0.8 | 스크립트 **창작** — 표현 다양성 |
| Reviewer | 0.2 | Eval **판정** — 같은 초안에 일관된 결과(결정론에 근접) |

값은 `orchestrator.py`의 `agent_*` 호출에 고정. 변경 시 이 표와 함께 갱신.

## 실시간 트렌드 — Perplexity Sonar (작업 C, ADR-013)

Trend Analyst 단계에서 `perplexity/sonar`(BizRouter 경유, `TREND_MODEL`)로 실시간 LLM·바이브코딩 트렌드를 조사해 출처와 함께 주입한다. 딥리서치(`Perplexity Sonar 활용법` 보고서)로 우리 구현이 Sonar 모범사례와 정합함을 검증.

| Sonar 모범사례(검증된 사실) | 우리 구현 정합 |
| :-- | :-- |
| **사용자 메시지가 웹 검색 동력** — system 프롬프트는 검색 백엔드가 무시, 합성 시점만 작용 | ✅ `call_text`는 system 없이 user 메시지만 전송 |
| **구체적·서술적 쿼리**가 검색 품질 결정 | ✅ `fetch_live_trends` 프롬프트를 "최근 3개월·구체 키워드·검색 근거" 서술형으로 강화 |
| **출처는 산문 링크 요구 금지, 응답 배열에서 추출** (환각 링크 방지) | ✅ `metadata.search_results`에서 `{title,url}`만 추출 |
| **그라운딩**: 검색결과 없으면 추측 말고 선언 | ✅ 프롬프트에 "근거 없으면 빈 배열" + graceful 빈 결과 |

**❌ BizRouter 경유 적용 불가(영구거부, ADR-007 전례):** `search_context_size`(low/medium/high)·`search_domain_filter`·`search_recency_filter` 등 Sonar 전용 파라미터(OpenAI 호환 엔드포인트로 전달 검증 불가), LangChain/LlamaIndex 통합(의존성 0 위반), Pydantic JSON Schema·스키마 웜업(Sonar json_object 미지원 확인), 하이브리드 RAG·임베딩(데모 과설계), 공식 가격표(BizRouter 경유라 실측 ~8원/호출과 다름).

> Sonar 응답 JSON은 비결정적으로 깨질 수 있어 `_parse_trends`가 정규식 부분복구로 방어(종단검증에서 발견). 비용 ~8원/호출.

### 다단계 트렌드 체인 (ADR-021 — 광역→심화→교차검증)

`fetch_live_trends`는 1콜 단발이 아니라 **다단계 체인**으로 깊이를 판다. 노드 신설이 아니라 기존 함수 내부 심화(ADR-010/013 "5번째 에이전트 거부" 정합).

| 단계 | 함수 | 동작 | 콜 |
| :-- | :-- | :-- | :-- |
| ① 광역 스캔 | `_trend_scan` | 지금 뜨는 키워드 5개 + 출처 | Sonar 1 |
| ② 심화 조사 | `_trend_deepen` | 광역 키워드 묶어 '구체 사례·왜 지금·신선도' detail 보강. DEPTH=3이면 교차검증 강화(콜 추가 없이 프롬프트로) | Sonar 1 (DEPTH≥2) |
| ③ 교차검증 | `_trend_score` | 출처 도메인 다양성으로 `freshness_score`(0~1) 부여 + 정렬, '신선도 약함' 감점 | 코드 0콜 |

- **공유 캐시:** 모듈 레벨 `_trends_cache`(TTL `TREND_CACHE_TTL`=1800s). `run`(/pd)·`suggest_topics`(홈 칩)가 같은 topic이면 중복 Sonar 호출 0. server.py `/api/suggest` TTL 캐시와는 별개 레이어.
- **비용 통제 env:** `TREND_DEPTH`(1=광역만 현행 1콜, 2=+심화 2콜 **기본**, 3=교차검증 강화 — 콜 수 동일 품질↑). 비용 급할 때 `TREND_DEPTH=1`로 즉시 폴백.
- **graceful 불변식:** 광역 실패→`{trends:[],sources:[]}`(캐시 미저장, 재시도 허용). 심화 실패→광역 결과 유지. 교차검증은 순수 코드라 무실패. **반환 키(`trends`/`sources`)·시그니처 불변** → 호출처 2곳·`agent_trend_analyst`·emit 전부 무변경(추가 필드 `detail`/`freshness_score`는 기존 소비자가 무시).

## 핸드오프 페이로드 (State.json tasks[i])

`task_id` · `topic` · `source_agent` · `target_agent` · `status` · `retry_count` · `content_payload{keywords,hooks,script,storyboard,thumbnail_prompt,hashtags}` · `wiki_references[]` · `feedback_log[]` · `token_usage{prompt,completion,total,calls}` · `cost_krw`

> `token_usage`는 BizRouter `usage` 응답(실측 키: `prompt_tokens`/`completion_tokens`/`total_tokens`)을 누적. 회귀: `test_orchestrator.py`.

## Eval 설계철학 — 12 메트릭 선정 근거 (왜 이 12개인가)

Eval은 **합격 가이드 §4 기본 8종 + 딥리서치·사용자 요청으로 진화한 4종**이다. 단순 복사가 아니라 "콘텐츠 PD 문제에 맞게 측정 수단을 추가·검증"한 결과. **결정론 측정(코드 실측 주입)**과 **LLM 종합 판정**을 분리한 게 핵심 — LLM이 "유사도 0.85 미만으로 가정"하는 가짜 통과를 코드 실측으로 차단.

| # | 메트릭 | 측정 방식 | 선정 근거 (ADR) |
| :-- | :-- | :-- | :-- |
| 1 | length_bounds | 단어수 100~250 | 기본(쇼츠 길이 휴리스틱) |
| 2 | keyword_inclusion | 키워드 ≥80% 포함 | 기본(SEO·타겟팅) |
| 3 | **originality_check** | **difflib 코드 실측** | 기본 → G1 결정론 실구현(LLM "가정" 제거). 강제 반려 |
| 4 | **channel_dup_check** | **토큰 자카드 코드 실측** | 신규(사용자 지적 "채널 중복 방지") — 양실장 73개 영상 제목 대조. 강제 반려. overlap coefficient 보강(ADR-011) |
| 5 | format_compliance | 양식 블록 | 기본(파서 무결성) |
| 6 | security_check | PII 금지 패턴 | 기본(faker 더미만, ADR-017 faker 생성모듈은 의존성0 거부) |
| 7 | **income_claim_compliance** | LLM 판정 | 기본 강화 → 미 FTC + **한국 표시광고법·추천보증 심사지침**(G3, 채용 대상이 한국 채널) |
| 8 | **hook_concreteness_context** | LLM 판정 | 기본 강화 → **훅 구체성 역U자**(딥리서치 검증, 무지성 숫자 박기 차단) + 3대 패턴(ADR-011) |
| 9 | **retention_design** | LLM 판정 | 기본 강화 → 완주율 1순위 + 가치우선·정보사다리·시간비율(ADR-009 정량구조) |
| 10 | **korean_syllable_density** | **음절수 코드 실측** | 신규(딥리서치 G5) — WPM 1:1 전이 금지, 3초 훅 18~21음절(한국언어청각임상학회지). ADR-009 |
| 11 | **hashtag_count** | **개수 코드 실측** | 신규(딥리서치 G5) — Metricool 231만건, 1~5개 최적. ADR-009 |
| 12 | **factual_accuracy** | **과장패턴·수치 코드 실측** | 신규(사용자 요청) — 교육 채널 신뢰 보호. 독립 에이전트 대신 Reviewer 하이브리드(ADR-010) |

**진화 요약:** 기본 8종(가이드 §4) → +채널중복(사용자) +음절·해시태그(딥리서치 G5) +팩트체크(사용자) = 12종. **강제 반려는 2-티어**(ADR-018): originality(≥0.85)·channel_dup(≥0.6)·hook 음절(>21)·해시태그(범위 밖) 같은 **맥락무관 하드위반만** 강제 rejected, 본문 음절 상한·overclaim flag 등 **맥락의존은 soft**(Reviewer 종합). length/keyword도 코드 실측 주입(LLM 눈대중 제거). 회귀 45건이 전 메트릭 코드 함수를 검증.

## 발표 슬라이드 자동 생성 — Gamma 통합 (승인 즉시 자동)

승인된 기획안을 Gamma Generate API v1.0으로 프레젠테이션(PDF)화한다. domain-priorities G9/G10(산출물 시각화)의 부분 실현.

- **트리거:** Reviewer 승인 즉시 자동. `orchestrator.gamma_generate(payload)`가 **생성요청만**(블로킹 0) 보내고 `done` 이벤트에 `gamma={id, status:"generating"}`을 실어 즉시 반환.
- **프롬프트 작성 에이전트(ADR-022/023):** `gamma_generate`는 inputText를 `agent_gamma_prompt(payload, topic) or gamma_build_input(payload, topic)`로 만든다. **`agent_gamma_prompt`(LLM)** 가 승인 기획안을 '발표 서사'(제목→핵심→타겟·훅 전략→스크립트→스토리보드→썸네일→배포)로 능동 재구성 — 단순 필드 나열인 `gamma_build_input` 조립 함수의 지능형 대체. **검증된 프레젠테이션 방법론(ADR-023) 주입:** 두괄식(결론 먼저)·메시지형 헤드라인(의미 없는 명사형 제목 금지)·1슬라이드 1메시지·역순 압축·핵심 패널 강조. 에이전트가 키 부재·예외·빈약 출력이면 None → **조립 함수로 폴백**(이중 안전망). 비용 +1 flash-lite 콜(~0.05원, Gamma 크레딧 대비 무시).
- **폴링 분리:** 생성(~1~2분)은 SSE 밖. 프론트가 `GET /api/gamma?id=`를 5초 간격(최대 2분) 폴링 → server.py 프록시가 `gamma_status()` 대리 호출 → `completed`면 `pdf_url`·`gamma_url` 반환. **SSE 타임아웃·_run_lock 장기점유 회피.**
- **PDF 표시:** 프론트가 `completed` 수신 시 PDF/Gamma 링크 표시 + `window.open(pdf_url)` 새 탭 1회.
- **키 보안:** `GAMMA_API_KEY`는 서버 환경변수에서만. 클라는 Gamma API를 직접 만지지 않음(server.py 프록시 경유, 브라우저 노출 0).
- **graceful degradation:** Gamma 실패(키 부재·크레딧 소진·HTTP 오류)는 예외 대신 `{status:"failed", error}`로 강등 → **기획안(done payload)은 절대 막지 않음.** 미승인(escalated)은 슬라이드화 안 함.
- **Cloudflare 주의:** Gamma 앞단이 기본 `Python-urllib` User-Agent를 봇(HTTP 403 code 1010)으로 차단 → `_gamma_request`가 `User-Agent` 헤더 명시.
- **비용:** 호출당 크레딧 ~41~71(실측). 승인 즉시 자동이라 매 승인 소모. 잔여 크레딧은 status 응답으로 프론트 노출(투명성).
- **의존성 0 유지:** Gamma 호출도 urllib(stdlib). 회귀 orc 53 + srv 12 PASS.

## 실행

```bash
export BIZROUTER_API_KEY="sk-br-v1-..."     # 필수 — 4-에이전트 LLM
export GAMMA_API_KEY="sk-gamma-..."         # 선택 — 발표 슬라이드 생성(미설정 시 슬라이드만 graceful skip, 기획은 정상)
export TREND_DEPTH=2                         # 선택 — 트렌드 심화 깊이(1=광역 1콜, 2=+심화 기본, 3=교차검증 강화)
export TREND_CACHE_TTL=1800                  # 선택 — 트렌드 공유 캐시 TTL(초). 같은 topic 반복 호출 절약
python 50-projects/content-pd-agent/orchestrator.py "개발 없이 5일 만에 수익 웹서비스 비법"
```

산출물은 `output/CONTENT_2026_NNN.md`, 로그는 `00-meta/log.md` 최상단에 1줄.
웹 데모(server.py)는 두 키를 환경변수로 받아 `/api/pd`(SSE)·`/api/gamma`(폴링 프록시)를 제공한다. Railway 배포 시 두 키를 환경변수에 등록.
