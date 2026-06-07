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
      └─ Fail → rejected + feedback_log → retry_count+1 → Creator로 복귀
                 (retry_count > max_retries → 에스컬레이션 후 중단)
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

> Sonar 응답 JSON은 비결정적으로 깨질 수 있어 `_parse_trends`가 정규식 부분복구로 방어(종단검증에서 발견). 비용 ~8원/호출이라 매 `/pd`마다 호출(사용자 결정).

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

## 실행

```bash
export BIZROUTER_API_KEY="sk-br-v1-..."
python 50-projects/content-pd-agent/orchestrator.py "개발 없이 5일 만에 수익 웹서비스 비법"
```

산출물은 `output/CONTENT_2026_NNN.md`, 로그는 `00-meta/log.md` 최상단에 1줄.
