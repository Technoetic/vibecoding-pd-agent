---
title: "content-pd-agent decisions"
type: concept
status: active
ai_priority: medium
created: 2026-06-07
updated: 2026-06-07
tags:
  - project
  - adr
related:
  - "[[content-pd-agent context]]"
---

# 아키텍처 결정 기록 (ADR)

왜 이렇게 설계했는지 — AI가 과거 논의를 반복하지 않게 한다.

## ADR-001 — 엔드게임 구조를 "그릇", PD 시스템을 "내용물"로 분리
숫자 접두사(`00~90`) 볼트 구조는 결정론적 탐색·토큰 절감을 위한 범용 골격. 콘텐츠 PD 시스템은 그 안의 `50-projects/`에 미니볼트로 격리. → 구조와 도메인을 독립적으로 진화.

## ADR-002 — 4-에이전트 오케스트레이션 (단일 프롬프트 거부)
단일 에이전트는 상호 검증이 불가. Supervisor 통제 + 전문 하위 3개로 분업해 [[reviewer]] 검수 축을 확보. 채용 과제가 요구하는 "상호 검증 구조".

## ADR-003 — 위키링크 프론트매터는 이중 따옴표 강제
옵시디언 `[[ ]]` 와 YAML 인라인 배열 `[ ]` 충돌 → Dataview 붕괴 방지. [[frontmatter]] 참조.

## ADR-004 — 권한은 실제 Claude Code 패턴 사용
가이드의 가상 스키마 대신 `Read()/Edit()/Write()/Bash()` 실동작 형식으로 settings.json 작성. `90-assets`·`_가이드`는 Deny.

## ADR-005 — 토큰 사용량을 State에 기록 (squeeze-report C3)
외부 설계 가이드가 권장한 `usage_metadata` 활용을 채택. **단, Google `usage_metadata`(SDK 전용)가 아니라 BizRouter `usage` 응답의 실측 키**(`prompt_tokens`/`completion_tokens`/`total_tokens`)를 1회 호출로 확인 후 채택. 방어적 접근(`.get(…,0)`)으로 키 부재 시 0. 승인/에스컬레이션 시 `tasks[i].token_usage`·`cost_krw`에 기록. 회귀 `test_orchestrator.py` 4건 PASS.
- **한계:** 캐시 토큰(`cached_content_token_count`)은 BizRouter 미지원이라 미기록.

## ADR-006 — 모델 ID는 상수 1곳, 은퇴일 전 마이그레이션 (squeeze-report R7 / domain-priorities G6·G7)
**검증됨(2026-06-07 WebSearch):** Vertex 기준 Gemini 2.5 Flash-Lite는 **2026-10-16 이후 종료**(출처: gcpstudyhub, Vertex docs). stable 엔드포인트는 더 이른 **2026-07-22 shutdown horizon**, preview(09-2025)는 2026-07-09 종료. 교체 경로 = **Gemini 3.1 Flash Lite(2026-03 출시)**. 모델 ID는 이미 `orchestrator.py`의 `MODEL` 상수 1곳에 집중.
- **BizRouter 가용성 확인됨(2026-06-07 `/v1/models`):** `google/gemini-3.1-flash-lite` **이미 가용**. 그 외 `gemini-3-flash-preview`·`gemini-3.5-flash`도 가용. 단 BizRouter의 2.5-flash-lite 제공 종료일은 별도 변수.
- **마이그레이션 절차(확정):** ① `orchestrator.py`의 `MODEL = "google/gemini-3.1-flash-lite"` 1줄 교체 → ② `test_orchestrator.py` 회귀 9건 + `/pd` 1회 종단 재검증(json_object·usage 키·Eval 8종 동작 확인) → ③ ORCHESTRATION.md 백엔드 검증표 갱신. **2026-07-22 전 실행 권장**(stable horizon).
- **결정:** config 추상화는 **YAGNI로 보류**(상수 1곳이면 충분). 교체는 위 절차로 단순.
- **거부한 것:** 보고서의 Google SDK 전용 기능(Pydantic `response_schema`·`client.caches`·`types.Tool`·`ThinkingConfig`·스트리밍)은 BizRouter 경유 불가로 영구 거부. `ORCHESTRATION.md` 백엔드 검증표 참조.
- **🔬 3.1 교체 검증 완료 → 비용 사유로 2.5 유지 결정(2026-06-07, 사용자 결단):** 3.1-flash-lite 교체를 절차대로 1회 실증한 뒤 **되돌렸다.** 검증 자체는 전부 성공 — ① 라이브 chat probe로 두 모델 200 OK·`json_object`·`usage` 4키 확인(`/v1/models`는 빈 배열 반환이라 chat 호출로 검증) → ② 회귀 9건 PASS(테스트는 모델 ID 비의존) → ③ `/pd` 종단 CONTENT_2026_006 승인(Eval 8종·originality 0.1059·income_claim 한국규제 차단 동작). **즉 "필요해지면 1줄로 즉시 교체 가능"이 실증됨.**
- **⚠ 비용 트레이드오프가 되돌린 사유:** 3.1은 2.5 대비 **토큰당 단가 약 2.85배**(004/005 ≈0.00019원/토큰 → 006 ≈0.00055원/토큰). 006 비용 13.87원은 토큰 증가(1.6배)+단가 상승(2.85배) 복합. ADR-007 외부검증 2.5 단가($0.10/$0.40)보다 3.1은 상위 티어. 품질·정확도 우위는 미측정(표본 1)이라 **2.85배 비용을 정당화할 근거 없음.**
- **✅ 최종 결정:** **2.5-flash-lite 유지.** 종료(2026-10-16)까지 4개월+ 여유 있고 저단가. **stable horizon(2026-07-22) 임박 시 `MODEL` 1줄을 `google/gemini-3.1-flash-lite`로 교체**(가용성·절차 모두 실증됨 — 1분 작업). 그때까지 재검토 불필요.

## ADR-007 — `Gemini 2.5 Flash Lite 활용 전략` 보고서 처리 결과 (squeeze-report, 전부 거부)
직전 ADR-005/006 보고서와 주제 90% 중복. 신규/표본 후보를 BizRouter 경유로 실측한 결과 **채택 0건**. 재호출 시 중복 추출 방지용 영구 기록.
- **검증된 팩트(채택 안 함, 추가가치 없음):** 입력 $0.10/1M·출력 $0.40/1M (외부 2곳 일치). 단 우리 비용은 이미 실측(호출당 ~0.05원)으로 `ORCHESTRATION.md`에 기록됨.
- **`permanently_rejected`(BizRouter 경유 불가·측정 불가·과설계):**
  - Flex/Batch 인퍼런스 티어(50% 할인) → `service_tier` 파라미터를 BizRouter가 적용하는지 응답으로 검증 불가 = 빈 약속.
  - 암시적 컨텍스트 캐싱(2048토큰 자동 90%) → BizRouter `usage`에 캐시 토큰 키 부재 = 측정·활용 불가.
  - 명시적 캐싱·thinking_budget·Enum 구조화출력 → 직전 ADR-006 영구거부와 중복(Google SDK 전용).
  - Flash-Lite 모더레이션 게이트웨이 → 우리 [[reviewer]]가 이미 검수 게이트. 별도 워커는 과설계(YAGNI).
- **가짜/불일치:** LiveCodeBench 점수(보고서 52→58% vs 외부 0.34)·출시일이 출처마다 불일치 → 벤치마크 수치 인용 금지.
- **propose-research 재점검(2026-06-07):** 이 _가이드 원본(172줄)은 ADR-007로 이미 추출 완료(채택 0). 재호출 신규 0건 — 짜낼 가치 소진. **→ 이로써 `_가이드/` 8종 전부 처리 완료**(제작가이드=시스템 구현물·SaaS방법론 ADR-016·볼트구조/CLAUDE.md ADR-015·오케스트레이션 ADR-005/006/014·Flash Lite ADR-007·Sonar ADR-013·채널철학 ADR-008·합격가이드 ADR-017). 외부 딥리서치 4종(ADR-009/011/012 + 채널성장)도 완료. **propose-research/squeeze-report 소스 전면 소진.**

## ADR-008 — `유튜브 채널 철학 분석` 보고서 처리 (채널 통찰 채택, 법인수치 거부)
89줄 채널 철학 분석. 우리 [[양실장 바이브코딩대학 채널 분석]] 노트가 얕은 시드라 결손이 컸음 → **콘텐츠 통찰 5건 채택**해 노트 보강.
- **채택(콘텐츠 기획에 직접 유용):** ① 교육철학('뿌리지식'·바이브코더 정체성·50시간·1:1 BMad) ② 5주 운영계획(사업자등록→첫수주→리드관리) ③ **"영업·소통>코딩"** 핵심 통찰 ④ AXTI·SME(MDX) 블루오션 타깃 ⑤ "경력≠고객만족"(숨고 평점 5.0 대조) — ③④⑤는 강력한 콘텐츠 앵글.
- **`permanently_rejected`:** 구독자 1만4,700명·사업자번호(841-88-01562)·심충보 대표·버즈앤비(주)·창업센터 개관 등 **구체 수치·법인 정보**. 사유: (a) WebSearch 교차검증 불완전(버즈앤비는 검색상 '블링' 운영사로 나와 연결 불명확), (b) **콘텐츠 기획에 불필요**(쇼츠 대본에 사업자번호 안 씀). 출처: 보고서 §1/7/8(vling·공식사이트).
- **DEFER:** 숨고 평점·구독자 추세 등 정량 지표 — 운영 데이터로 추세 추적 가치 생기면 재평가.
- **propose-research 재점검(2026-06-07):** 이 _가이드 원본(89줄)은 ADR-008로 이미 추출 완료(통찰 5건 채택→[[양실장 바이브코딩대학 채널 분석]] 반영, 법인수치 거부). 재호출 시 신규 0건 — 짜낼 가치 소진. 재추출 차단.

## ADR-009 — `숏폼 스크립트 정량 구조 연구` 보고서 처리 (G5 결손 본문화, squeeze-report)
140줄 딥리서치 보고서. G5(쇼츠 스크립트 정량구조 미검증) 결손을 직격. 검증된 정량 사실 다수 채택.
- **채택(검증된 사실 → 본문화):**
  - **한국어 음절(SPM) 기준** ⭐: WPM 1:1 전이 금지, 한국어 356 SPM(아나운서, 한국언어청각임상학회지)·숏폼 400~420 SPM, 60초≈350~400음절·600 상한, **3초 훅 18~21음절**. → `korean_syllable_density` eval 메트릭 + `korean_syllables()`/`script_density_score()` 결정론 측정 구현. **이는 G4 "한국어 전이 미검증"의 부분 해답** — 시간비율은 전이, 발화량은 음절로.
  - **해시태그 1~5개**(Metricool 231만건): #fyp 배제·니치 태그 캡션 배치. → `hashtag_count` eval 메트릭 + `hashtag_count_score()` 결정론 측정.
  - **구간배분·정보사다리·가치우선**(500+ 바이럴): 60초 훅5/본문50/CTA5, 본문 10~15초 정보사다리, 결론 숨기기 금지. → `retention_design` rule 강화.
  - **패턴 인터럽트·심리스 루프**(opus.pro·hypebot): 3~5초 전환 완주율 41→58%, 자막 +12%. → 지식노트 [[쇼츠 스크립트 구조와 길이]] 반영.
- **결정론 분리:** 음절·해시태그는 메인이 실측해 payload에 저장 → Reviewer가 전체 payload를 받으므로 추측 차단(originality 패턴과 동일). 단 강제반려는 originality·channel_dup만(음절·해시태그는 Reviewer 종합 판정).
- **`permanently_rejected`:** ① 5초 미만 무한루프 꼼수(보고서 자체가 "통념·근거약함"으로 분류, 유튜브 2021.12 루핑스팸 페널티) ② WPM 1:1 전이(보고서가 "전이 미검증" 명시).
- **DEFER:** 영어 180WPM↔한국어 400SPM 이탈곡선 대조검증·주제별 WPM 임계·플랫폼별 해시태그 가중치 상수 — 운영 데이터 후. 보고서도 "데이터 부재로 단정 불가"로 분류.
- **외부 검증:** 출처 22건 중 핵심(한국언어청각임상학회지 jslhd.org·Metricool·opus.pro·reddit 500분석) 실재 확인.

## ADR-010 — 팩트체크: 별도 에이전트 대신 Reviewer 하이브리드 강화 (사용자 요청)
"오케스트레이션에 팩트체크 에이전트도 필요하지 않나"에 대한 결정. **5번째 독립 에이전트 신설을 거부**하고 기존 Reviewer를 강화. 양실장 채널이 교육 채널이라 사실 오류·과장은 신뢰를 붕괴시킨다.
- **거부한 것(과설계):** 독립 팩트체크 에이전트(매 기획 Sonar ~8원 추가 호출). 사유: 핸드오프·비용 증가인데, 검증 결과는 코드 실측→payload→Reviewer 자동 주입으로 **추가 호출 0**에 같은 효과. ADR-007 "별도 모더레이션 워커 = 과설계" 전례와 정합.
- **채택(하이브리드, 비용 0):**
  - `overclaim_check()` — 과장·거짓 단정 패턴 결정론 탐지(100% 대체·무조건·누구나 보장·완전 자동화·절대·평생). 실측 4-flag 검증.
  - `extract_numeric_claims()` — 수치+단위 주장 추출(구독자·조회수·원·명·%). Reviewer가 channel_catalog 실제값·상식과 대조.
  - `factual_accuracy` eval 메트릭. 둘 다 payload 저장 → Reviewer 전체 payload 수신으로 추측 차단(originality 패턴).
- **강제반려 미적용:** 과장패턴은 맥락 의존("평생 무료 강의"는 정당)이라 Reviewer 종합 판정. originality·channel_dup만 결정론 강제반려 유지.
- **검증:** 과장 스크립트 4-flag 탐지·정상 통과·수치 추출 실동작 확인. 회귀 41 PASS.

## ADR-011 — `한국 AI 교육 유튜브 성장 분석` 보고서 처리 (시장구조 본문화, squeeze-report)
190줄 딥리서치 보고서(open_question_1 = 채널 성장 사례 조사의 결과). 경쟁 지형·퍼널·시장구조 검증 사실 채택.
- **채택(검증된 사실 → 본문화):**
  - **경쟁 채널 벤치마크**(조코딩·장피엠·양실장·에어빌드): 포지션·포맷·훅 패턴. 구독자 수치는 제외(ADR-008 정합). → 신규 노트 [[한국 AI 교육 유튜브 시장 구조]].
  - **롱폼↔쇼츠 퍼널 역학**(§2.1): 쇼츠=ToF 미끼, 롱폼=신뢰·유료전환. 우리는 쇼츠 전용이라 "퍼널 맥락 지식"으로만 본문화(롱폼 기획 기능 추가는 범위 밖). 쇼츠 CTA가 채널 유입을 책임져야 함.
  - **3대 훅 패턴**(§3): 수익수치형·초단기시간형·정체성형. → [[훅 구체성 역U자 법칙]] "시장 관찰 패턴" 절 + `hook_concreteness_context` eval evidence 보강. 수익수치형은 포화+규제라 정체성형 우선.
  - **한국 B2C 1인SaaS vs 서구 B2B 에이전시**(§5.1) + **노코드→바이브코딩 피벗 변곡점**(§4.1): 시장 구조 맥락. → 신규 노트.
- **결정론 분리:** 이 보고서는 시장 맥락 지식이라 결정론 측정 메트릭 신설 없음(코드 변경 0). eval은 hook_concreteness_context evidence 텍스트 1줄 보강만.
- **`permanently_rejected`:** ① 자기신고 수익 수치("3시간 게임 월 1.2억"·"18개월 130억"·"월 800만원") — 보고서가 "추정·일화"로 자체 분류 + ADR-010 팩트체크 차단 대상 ② 구독자 수치(ADR-008 기 거부) ③ 개별 수강생 생존율(미공개).
- **이전 이력:** PROMPT_한국 AI코딩 교육 채널 성장 사례(open_question_1)의 답 → status answered 정정 완료(/propose-research, 2151c16b).
- **외부 검증:** 핵심 출처(교보문고 조코딩 서적·언론 보도·채널 공개 데이터) 실재. 자기신고 재무수치는 교차검증 불가로 거부.

## ADR-012 — `한국어 헤드라인 구체성 CTR 연구` 보고서 처리 (G4 역U자 전이 정밀화, squeeze-report)
142줄 딥리서치(G4 = 역U자 한국어 전이 PROMPT의 답). 보고서 최종 판정은 **"전이 미검증(데이터 부재)"** — 자칫 "검증됨"으로 오채택하면 가짜 인용이므로 **사실성 분리가 핵심**.
- **채택(검증된 부분만):**
  - **상승 구간은 한국어 일치(검증됨)**: 모호→구체 전환 시 CTR↑(실무 +35%, KCI 윤정민 2022 정보전달/관심유도 이원화). → [[훅 구체성 역U자 법칙]] "한국어 전이" 절 신설.
  - **하이브리드 공식**: "[상황]+[수치]+[결과]"(결론 숨김+수치) + 질문형 말걸기(관계적 구체성, high-context). → 적용규칙 #5.
  - **길이 제약**: 한국어 45~70자 CTR 최적, 길수록 하락. → 음절 상한(ADR-009)과 정합, 방증.
- **`permanently_rejected`(보고서 자체 "미검증" 결론):**
  - **역U자 하락 구간의 한국어 전이** — 포화 환경 과구체성 역효과는 한국어 1차 대규모 데이터 부재. "한국어도 역U자 하락"으로 단정 금지. (단 "상승 일치/하락 미검증" 정밀화는 채택 — 기존 "통째로 미검증"보다 정확)
- **DEFER:** 감정·표현 마커(느낌표·이모지)의 한국어 CTR 효과 — 대규모 실증 부재, 운영 데이터 후.
- **G4 상태:** "⏸️ 조건 의존(통째 미검증)" → "🟡 부분 해소(상승 검증/하락 미검증)"로 격상. domain-priorities 갱신.
- **자기기만 차단:** R1(하락 전이)을 거부하면서 그 안의 부분 사실(상승 일치)만 C1로 살림. "역U자 한국어 검증됨" 오채택 회피.
- **외부 검증:** KCI 논문(DBpia 윤정민 2022·임현빈 2014)·연합뉴스(허핑턴포스트 A/B)·실무(재능넷·orda25·kpmobile) 실재. 단 실무 수치(+35% 등)는 단일 캠페인이라 "실무 사례"로만.

## ADR-013 — `Perplexity Sonar 활용법` 보고서 처리 (Sonar 모범사례 정합 검증, squeeze-report)
164줄 딥리서치(Sonar API 프로덕션 최적화·오케스트레이션). 우리는 작업 C에서 `perplexity/sonar`를 BizRouter 경유로 쓰는데, 보고서 대부분이 **공식 Perplexity 직접 호출 전제**라 우리 환경(BizRouter OpenAI 호환·의존성 0) 적용성을 엄격히 분리.
- **채택(우리 구현 정합 검증 → ORCHESTRATION.md 문서화):**
  - **사용자 메시지가 검색 동력**(system은 검색 백엔드 무시): 우리 `call_text`가 system 없이 user만 전송 → **이미 정합**.
  - **출처는 응답 배열에서 추출**(산문 링크 = 환각): 우리가 `metadata.search_results`에서 추출 → **이미 정합**.
  - **구체적·서술적 쿼리**: `fetch_live_trends` 프롬프트를 "최근 3개월·구체 키워드·검색 근거" 서술형으로 강화 + 그라운딩("근거 없으면 빈 배열").
- **`permanently_rejected`(BizRouter 경유 불가·원칙 위반, ADR-007 전례):**
  - Sonar 전용 파라미터(`search_context_size`·`search_domain_filter`·`search_recency_filter`) — OpenAI 호환 엔드포인트 전달 검증 불가.
  - LangChain/LlamaIndex 통합 — 의존성 0 위반.
  - Pydantic JSON Schema·스키마 웜업 — Sonar json_object 미지원 확인됨(C1 종단검증).
  - 하이브리드 RAG·임베딩·누수버킷 — 데모 과설계(YAGNI).
  - 공식 가격표($1/$3 등) — BizRouter 경유라 실측(~8원/호출)과 다름. ADR-007 가격 외부수치 거부 전례.
- **자기기만 차단:** 보고서가 화려해 "LangChain 도입·파라미터 추가" 유혹 크나, 의존성 0·BizRouter 제약상 전부 불가. 가장 큰 가치는 "우리가 이미 모범사례와 정합"이라는 검증.
- **검증:** 프롬프트 강화 후 회귀 41 PASS(프롬프트 문자열은 회귀 비의존).

## ADR-014 — `단일 경량 모델 오케스트레이션 상세 가이드`(666줄) 추가 추출 결과 (전부 거부, propose-research 분석/판정 분리)
ADR-005/006이 이미 이 _가이드 원본에서 토큰로깅·모델마이그레이션을 추출함. 666줄 전체를 재정독해 미추출 결손을 점검(propose-research). **분석 에이전트가 8후보 중 5개를 "적용 가능"으로 추천했으나, 독립 판정 에이전트(haiku)가 8개 전부 REJECT.** 분석/판정 분리가 자기기만(화려한 엔터프라이즈 패턴 도입 유혹)을 차단한 사례.
- **`permanently_rejected` 8건:**
  - **async 병렬화(§7)** — aiohttp 외부 패키지 = 의존성 0 위반. 데모 순차호출(~0.2~0.5원/기획) 충분, YAGNI.
  - **Pydantic 스키마 검증(§3.1)** — pip install 필요(분석의 "stdlib 수준" 주장은 오류). 현 json_object + 프롬프트 스키마로 충분. 의존성 0 위반.
  - **모델 config 추상화(§8)** — ADR-006이 이미 "YAGNI 보류, 상수 1곳 충분"으로 결정. 번복 근거 없음.
  - **LLM 스트리밍(§3.4)** — 데모는 on_step SSE로 진행감 제공. TTFT 0.29초라 추가가치 < 복잡도. YAGNI.
  - **컨텍스트 캐싱(§5)·thinking budget(§6)·Google Search Tool(§4.1)** — Google SDK 전용, BizRouter 경유 불가(ADR-007 영구거부 전례). thinking은 2.5-flash-lite 기본 0.
  - **Code Execution(§4.2)·SFT·Live API** — 콘텐츠 PD 데모 범위 밖(텍스트·JSON만). YAGNI.
- **핵심 교훈:** 분석 에이전트는 "기술적 가능성"만 보고, 판정 에이전트가 "프로젝트 규칙(의존성 0·BizRouter·YAGNI·기존 ADR)"으로 거른다. 666줄 가이드의 잔여 가치 = **0**(ADR-005/006으로 짜낼 건 이미 짜냄). 재호출 시 이 ADR로 재추출 차단.

## ADR-015 — `_가이드/` 인프라 가이드 일괄 — propose-research 범위 밖, 신규 0건
**적용 대상:** `옵시디언 볼트 디렉토리 최적화 제안`(253줄) + `옵시디언 연동 CLAUDE.MD 작성 가이드`(263줄). 둘 다 **현 시스템(볼트 구조·CLAUDE.md)의 설계 원본**이라 이미 100% 적용됨. propose-research(딥리서치 프롬프트 생성) 대상 아님.

**CLAUDE.md 작성 가이드(263줄) 실측 정합:**
- 우리 CLAUDE.md 섹션(Vault Architecture / Hard Rules Markdown·Linking / Hard Rules YAML Frontmatter / Core Workflow) = 가이드 §6 템플릿과 일치.
- YAML 위키링크 이중따옴표 이스케이프(가이드 §5.2 핵심) = CLAUDE.md §3에 명시.
- 권장 슬래시 명령어 /day·/ingest·/lint·/pd = 전부 `.claude/commands/`에 보유.
- 부정어 억제·명령어 경제성·계층 로딩 = CLAUDE.md에 반영됨. → 신규 0건.

**볼트 디렉토리 최적화 제안(253줄) — 현 볼트 구조의 설계 원본** (00-meta·10-inbox·20-knowledge·30-journal·50-projects·90-assets·`_` 격리 = 이미 100% 적용). 253줄 정독 결과:
- **이미 적용됨:** 숫자접두사·격리구역(_archive·_processed·90-assets·_가이드 Deny)·미니볼트(content-pd-agent context/decisions/tasks/handoff)·평면 20-knowledge(CLAUDE.md 의도적 단순화).
- **의도적 편차(거부):** 가이드의 20-knowledge 5범용카테고리(concepts/domains/patterns/references/tools) vs 우리 3도메인(hooks/scripts/trends). CLAUDE.md "하위 폴더 더 만들지 말 것"이 명시. 가이드는 수천 파일 대규모 위키 전제, 우리는 소규모 콘텐츠PD 특화.
- **시스템 무관/과설계(거부):** 40-people·60-areas(인맥·경력 — 콘텐츠PD 무관), vault_migrate.py(대규모 마이그레이션 — 이미 구조화됨), templates/daily(이벤트드리븐이라 일일노트 미사용).
- **propose-research 범위 밖:** 분석이 추출한 agents.md·naming.md·process-inbox 스킬·settings.json defaultMode 변경 등은 **딥리서치 프롬프트가 아니라 볼트 인프라/Claude Code 설정 작업**. 스킬 산출물 유형 불일치 + 대부분 **🔵 사용자 결단 영역**(설정·스킬 신설). propose-research 안전장치 "인프라·설정은 별도 프롬프트 작성 안 함" 정합.
- **결론:** 신규 딥리서치 프롬프트 **0건**. 인프라 개선 후보(naming.md 분리·settings plan 모드 등)는 사용자 신호 시 별도 처리. Phase B 판정 불요(후보가 스킬 산출물 유형 아님).

## ADR-016 — `AI 에이전트 기반 SaaS 개발 방법론`(542줄) — propose-research 범위 밖, 신규 0건
ADR 처리 이력 0건이던 _가이드 원본(542줄, Claude Code×Obsidian SaaS 개발 방법론). 분석 에이전트 정독 결과:
- **이미 적용됨:** 볼트 디렉토리(00~50)·CLAUDE.md 점진적 공개(메타규칙만, 도메인은 20-knowledge)·권한 티어(deny/ask/allow)·미니볼트(handoff/context/decisions/tasks)·Session Handoff(handoff.md, 4섹션 표준은 아니나 기능 동일).
- **딥리서치 프롬프트 0건:** 미반영 3건(C1 .claudeignore·C2 SessionStart 훅·C3 Stop 훅) 전부 `is_deepresearch_prompt=false` = 볼트/Claude Code 인프라 작업이지 콘텐츠PD 지식 결손 아님.
  - **C1 .claudeignore:** settings.json `deny`(90-assets·_archive·_processed·_가이드 Read 차단)가 **이미 동일 역할** — 중복이라 추가가치 미미. 미적용.
  - **C2/C3 훅(SessionStart·Stop):** 🔵 사용자 결단 영역(자동화 vs 수동). 콘텐츠PD 대화 패턴상 handoff 수동관리가 단순. 사용자 신호 시 별도.
- **도메인 무관/과설계(거부):** §4 Next.js/Supabase SSR(우리는 SaaS 개발 아닌 콘텐츠PD), §6 Subagents/MCP/Marmot(의존성0·데모 규모 엔터프라이즈 과설계), §7 Next.js 워크플로우(우리는 /pd 오케스트레이션).
- **결론:** `_가이드/` 인프라/방법론 원본은 시스템 설계의 출처라 "이미 적용 + 나머지는 인프라/도메인무관". 짜낼 딥리서치 가치 0. 재추출 차단.

## ADR-017 — `AI 콘텐츠 PD 에이전트 제작 가이드`(129줄, 채용 합격 가이드) — 딥리서치 0건, 제출물 결손 3건 식별
이 _가이드 원본은 **채용 과제 합격 가이드**(§5 "100% 합격 실전 구현·포트폴리오 제출 전략"). 다른 가이드와 달리 "제출물 완성도" 결손을 드러냄. 분석 7후보 → 판정(독립 haiku) ACCEPT 3·REJECT 3·DEFER 1.
- **딥리서치 프롬프트 0건:** 7후보 전부 `is_deepresearch_prompt=false`. propose-research 본연 산출물은 없음.
- **✅ ACCEPT(제출물 완성 작업 — 합격 가치, 사용자 신호 시 진행):**
  - **C1 제출용 포트폴리오:** output 7건(001/003~008) 중 대표 선별 → PORTFOLIO.md 통합 + "채널 반영" 주석. 순수 문서.
  - **C2 Claude Code 세션 실행 로그:** /pd 1회 전체 실행을 터미널 로그/스크린샷으로 증빙(가이드 §5.2 명시 요건). 증빙 작업.
  - **C6 Eval 설계철학 문서:** ORCHESTRATION.md에 "12 메트릭 선정 근거 + ADR 매핑" 섹션. 문서 작업.
- **❌ REJECT:**
  - **C4 faker/pandas 합성데이터 모듈:** 외부패키지 = 의존성0 위반(ADR-014 전례). security_check가 이미 PII 차단, 쇼츠 기획에 더미 고객데이터 불필요(YAGNI).
  - **C7 추정 CTR/CAC/LTV 점수(★Critical):** "예상 CTR 70점" 같은 추정 점수는 **ADR-010 가짜통과·G1 코사인유사도 실측의 180도 회귀**. 검증 불가 수치 = 결정론 아님. 그로스 메트릭은 실게시 운영 데이터로만 측정(조건 의존). 절대 거부.
  - **C5 .llm_wiki 명시 폴더:** 실질 기능 충족(personas·State·Knowledge 존재), 형식 차이뿐. 분석도 false.
- **⏸️ DEFER C3 미래 확장 로드맵:** domain-priorities G8(검색MCP)·G9(이미지생성)·G10(랜딩배포)에 **이미 있음**. README 재구성 여부는 사용자 신호.
- **핵심:** 분석이 끌린 C4(외부패키지)·C7(추정점수)을 판정이 차단 — 자기기만 방지 작동. **ACCEPT 3건은 propose-research 산출물이 아니라 채용 제출물 완성 작업**이라 사용자 확인 후 진행.

## ADR-018 — 결정론 누수 3건 수정 (적대적 오케스트레이션 검증 반영)
4개 독립 관점(아키텍처·평가·비용·채용) 적대 검증이 **"결정론 측정+LLM 분리"·"교육채널 신뢰 1순위" 철학을 코드가 절반만 이행한 3개 실증 누수**를 잡음. CONTENT_2026_009에서 hook 22음절(ok=False)인데 approved + "월 100만원" overclaim 통과로 드러남. 거시 구조(순차·단일모델·강제반려2종·의존성0)는 4관점 만장일치로 정당(과설계 없음). 누수만 수정:
- **A — 2-티어 강제반려:** `deterministic_block(orig, channel, density, htag)`로 확장. **맥락무관 하드위반(hook ≤21음절·해시태그 1~5개) 강제반려 추가.** 본문 음절 상한은 맥락의존이라 soft 유지(Reviewer 종합판정). 009의 22음절은 이제 강제반려 확인.
- **B — overclaim 회피 보강:** `_OVERCLAIM_PATTERNS` 교체. 회피 6종("월 1000만원 보장"·"100퍼센트"·"반드시 성공"·"확실하게 수익"·"수익 보장"·"천만원 보장") 전부 flag. 골든셋 테스트로 재발 고정. **강제반려 아님**(flag 강화 + Reviewer 종합) — "평생 무료" 같은 false-positive를 맥락으로 거르기 위함(ADR-010 하이브리드 유지).
- **C — length/keyword 결정론화:** `word_count_score`·`keyword_inclusion_score` 신설, payload 주입(LLM 눈대중 대체). originality는 difflib로 결정론화하면서 가장 셀 수 있는 두 메트릭을 LLM에 맡긴 비일관 해소. 강제반려 아님(한국어 어절 경계 모호성 — 실측값 주입으로 충분).
- **D — 문서 정정:** reviewer.md 드리프트 제거("코사인 유사도"→difflib, 8개 나열→eval_scenarios.json 단일 진실원천 + 결정론/LLM 분리 명시). Supervisor는 "LLM콜 0 코드 컨트롤러"로 정직 프레이밍(동적 라우팅 도입은 데모 YAGNI 거부).
- **거부 유지(정당한 트레이드오프):** 병렬화·resume 상태머신·config추상화·5번째 에이전트 — 4관점도 fits_constraints=false. ADR-006/007/010/014/016/017 거부 유지.
- **검증:** 45 테스트 PASS(orchestrator 42+server 3). 009 누수 재현 실측 — hook 22음절 강제반려·overclaim 6종 flag·length/keyword 결정론 동작 확인. 의존성 0 유지.

## ADR-019 — `Claude Code × Gamma API 프레젠테이션 자동화 가이드`(449줄) — propose-research 범위 밖, 신규 0건
ADR 처리 이력 0건이던 외부 가이드(Claude Code로 Gamma Generate API v1.0을 구동해 텍스트→PPTX 프레젠테이션을 자동 생성하는 도구 사용법). propose-research(콘텐츠 PD 지식 결손용 딥리서치 프롬프트 생성)로 정독 점검. **Phase A(메인) "신규 0건" 판정 → Phase B(독립 haiku) ACCEPT, self_rationalization_risk LOW.** ADR-014/015/016(인프라/도구/방법론 가이드 = 신규 0건)과 동형.
- **딥리서치 프롬프트 0건:** 가이드 449줄은 순수 **도구 사용법**(API 인증·`llms.txt` 컨텍스트 주입·비동기 폴링·예외처리·`from-template`·파이핑·커스텀 스킬). 산출물이 **PPTX 프레젠테이션**으로, 이 볼트 정체성(쇼츠/틱톡 **기획안**)과 산출물 종류가 다름. 가이드 본문에 훅·스크립트·트렌드·채널전략 등 **콘텐츠 PD 지식은 0줄**.
- **인프라/Claude Code 설정 영역(콘텐츠 결손 아님):** 가이드 기술 패턴은 전부 인프라/설정. propose-research 안전장치 "인프라·설정은 별도 프롬프트 작성 안 함"에 정확히 걸림. ADR-015 §149-150("인프라 개선·설정 작업은 딥리서치 범위 밖") 전례 정합.
- **유일 인접 가치 = 이미 매핑됨:** 가이드의 "승인 텍스트 기획안 → 시각 산출물 변환"은 domain-priorities **G9(이미지 생성)·G10(랜딩 배포)**에 이미 있고 둘 다 **🔵 사용자 결단(유료 키·인프라)**. 새 결손 아님.
- **Phase B 독립 실측(haiku):** ① 지식노트 풀(hooks 2·scripts 1·trends 4) 충실, 미검증 마커 3건은 전부 저자 의도적 경계 명시(사기적 "미검증" 아님) ② eval 12종 evidence 경로 12/12 실존 ③ 남은 결손 G2/G4/G5(조건 의존)·G8/G9/G10(사용자 결단) — 미처리 결손이 아니라 의존성 구조 ④ 가이드 안 진짜 콘텐츠 결손 = 없음. **missed_gaps: none.**
- **사실성 주의(squeeze-report 영역, propose-research 아님):** 가이드 본문에 Claude Code/Gamma 관련 사실 오류 의심 다수(`claude auth login`·`claude auth status` 서브커맨드, `~/.claude/skills/` 자동 인식, `/loop 5m` 문법, Gamma 응답 필드명 `gammaUrl`/`exportUrl`·페이로드 `numCards`/`exportAs` 미검증 추정). 이는 딥리서치 결손이 아니라 사실성 분리 대상이며, 우리 시스템과 무관해 본문화 불요.
- **결론:** 외부 도구 가이드는 propose-research 산출물(콘텐츠 도메인 딥리서치 프롬프트) 유형 불일치. 짜낼 딥리서치 가치 0. 재호출 시 이 ADR로 재추출 차단.

## ADR-020 — Gamma 슬라이드 자동 생성 파이프라인 통합 (G9/G10 부분 실현, 사용자 결단)
ADR-019에서 "🔵 사용자 결단(유료 키·인프라)"으로 분류했던 Gamma 통합을 **사용자가 키를 제공하고 "자율주행 통합" 지시**해 실현. `/pd` 승인 즉시 기획안을 프레젠테이션(PDF)으로 자동 생성. brainstorming → 설계(docs/superpowers/specs/2026-06-08-gamma-pipeline-integration-design.md) → 구현 → e2e 검증.
- **접근법 A 채택(서버 백그라운드 + 클라 폴링):** 승인 시 `gamma_generate`가 생성요청만(블로킹 0) → `done`에 `gamma{id,status}` → 프론트가 `/api/gamma?id=` 5초 폴링 → server.py 프록시가 `gamma_status` 대리 → completed면 PDF 새 탭. **거부한 것:** ① SSE 안에서 끝까지 폴링(200초+ → Railway 502·_run_lock 장기점유) ② 클라가 Gamma 직접 호출(API 키 브라우저 노출 — server.py "노출 0" 원칙 위반).
- **결정(사용자 확정):** 트리거=승인 즉시 자동 / 출력=PDF 링크+새 탭 / 흐름=분리 폴링 / 실패=기획안 정상+슬라이드만 실패 표시(graceful degradation).
- **의존성 0 유지:** Gamma 호출도 urllib(stdlib). `gamma_generate`/`gamma_status`/`gamma_build_input` + `_gamma_request`. BizRouter usage와 별개 크레딧이라 token_usage 미누적(credits는 status로 노출만).
- **graceful 불변식:** Gamma 실패(키 부재·크레딧·HTTP)는 예외 대신 `{status:failed,error}` 강등 → done payload(기획안) 절대 안 막음. escalated(미승인)는 슬라이드화 안 함. 회귀 `test_run_done_has_gamma_field`로 고정.
- **🔬 실 버그 수정(e2e 발견):** Gamma 앞단 **Cloudflare가 기본 `Python-urllib` UA를 HTTP 403 code 1010으로 차단**. `_gamma_request`에 `User-Agent` 헤더 추가로 해결(curl은 통과했으나 urllib은 막힘 — Railway에서도 동일 필요). SSL은 로컬 한정(certifi SSL_CERT_FILE), Railway Linux는 정상.
- **보안:** `/api/gamma` id를 `[A-Za-z0-9_-]{1,64}` 정규식 검증(경로주입·SSRF 방어). 키는 환경변수만.
- **검증(실측):** ① 회귀 orc 53 + srv 12 = 65 PASS(의존성 0) ② 실 Gamma 키 백엔드 e2e — 생성→폴링(50초)→completed→pdf_url 확보 ③ `/api/gamma` 프록시 curl 3종(완성 id·경로주입 거부·id없음 거부) ④ Playwright 프론트 e2e — 슬라이드 영역 표시·생성중 스피너·폴링·PDF/Gamma 링크·window.open 팝업·JS에러 0, 시각 스크린샷 확인.
- **비용:** 호출당 크레딧 ~41~71(실측). 승인 즉시 자동이라 매 승인 소모. 잔여 크레딧 status 노출(투명성). **향후 비용 통제 필요 시 env 토글(자동→수동) 여지만 남김(현 범위 밖, YAGNI).**
- **범위 밖(YAGNI):** from-template 브랜드 템플릿·PPTX export·크레딧 사전 하드게이트.

## ADR-021 — 트렌드 탐색 심화 (다단계 체인, 노드 신설 거부 정합)
"최신 트렌드 탐색 에이전트 추가" 요청. `/api/suggest` 실측에서 드러난 약점(Sonar 1콜 단발, 출처가 '전망 글' 위주, 신선도 측정 없음)을 정조준. **사용자가 '기존 트렌드 탐색 심화'(독립 5번째 에이전트 신설 X)를 선택** → ADR-010/013 "노드 신설 = 과설계 거부" 철학 정합. brainstorming → 설계(docs/superpowers/specs/2026-06-08-trend-discovery-deepening-design.md) → 구현 → 테스트.
- **접근법 A(시그니처 유지 내부 다단계):** `fetch_live_trends(topic)` 시그니처·반환 키(`trends`/`sources`) 불변 → 호출처 2곳(`run`·`suggest_topics`)·`agent_trend_analyst`·emit 전부 무변경. 내부만 3단계로: ① `_trend_scan`(광역 Sonar 1콜) ② `_trend_deepen`(심화 Sonar 1콜, detail 보강) ③ `_trend_score`(코드 0콜, freshness_score). **거부:** 별도 `trend_scout` 함수 신설(호출처·테스트·캐시 재배선 과함) / Trend Analyst 페르소나에 검색 위임(검색≠설계 책임분리 파괴).
- **결정(사용자 확정):** 다단계 체인(광역→심화→교차검증) / 둘 다 적용(run+suggest) / 공유 캐시+env 비용통제.
- **비용 통제:** 모듈 공유 캐시 `_trends_cache`(TTL `TREND_CACHE_TTL`=1800s) — run·suggest 같은 topic 중복 Sonar 0. `TREND_DEPTH` env(1=현행 1콜 폴백, 2=기본 2콜, 3=교차검증 강화 콜 추가 없이). ADR-006 비용 민감 이력 반영 — DEPTH=1로 즉시 비용 절반 폴백 가능.
- **graceful 불변식:** 광역 실패→빈 결과(캐시 미저장, 재시도 허용). 심화 실패→광역 유지. 교차검증 순수 코드 무실패. 추가 필드(detail·freshness_score)는 기존 소비자가 무시 → 하위호환.
- **의존성 0:** Sonar는 기존 `call_text`(urllib). score는 stdlib `urllib.parse`. 신규 패키지 0.
- **검증(실측):** 회귀 orc 62(트렌드 9건 신규: scan·deepen·graceful·empty-noop·score·캐시공유·depth1·depth2·scan실패) + srv 12 = 74 PASS. 기존 통합 테스트(run) 무손상(DEPTH=1 reset). 프로덕션 다단계 실 e2e는 배포 후 `/api/suggest?refresh=1`로 검증.
- **범위 밖(YAGNI):** 트렌드 20-knowledge 영속화(배치 잡 영역)·교차검증 전용 3번째 Sonar 콜(DEPTH=3은 프롬프트로 흡수)·ML 신선도 점수(출처 메타 휴리스틱으로 충분).

## ADR-022 — 감마 프롬프트 작성 에이전트 (조립 함수 → LLM 능동 재구성 + 폴백)
"감마 프롬프트 작성 에이전트도 있어?" 질문에서, 기존 `gamma_build_input`이 **LLM 없는 조립 함수**(필드 기계 나열)임을 확인. 사용자가 명시적으로 '에이전트'를 원했고 Gamma 통합 직후 맥락이라, **여기선 LLM 에이전트화가 정당**(ADR-010/013/021의 "노드 신설 거부"와 충돌 아님 — 이건 기존 조립 함수의 지능형 대체이지 새 오케스트레이션 노드 신설이 아니며, 비용 +1콜이 Gamma 크레딧 41~71에 비해 무시 수준).
- **설계:** `agent_gamma_prompt(payload, topic)` — 승인 기획안을 '발표 서사'(제목→핵심→타겟·훅 전략→스크립트 흐름→스토리보드→썸네일→해시태그/배포)로 LLM이 능동 재구성. 단순 필드 나열 대신 "왜 이게 먹히는지"를 발표자 관점으로 짚음. payload의 풍부 필드(keywords·hooks 포함) 활용.
- **graceful 이중 안전망:** `gamma_generate`가 `agent_gamma_prompt(...) or gamma_build_input(...)`. 에이전트가 ① 키 부재 ② LLM 예외 ③ 빈약 출력(<100자) 중 하나면 None 반환 → **조립 함수로 폴백**. Gamma 생성은 어느 경우도 안 막힘(기존 graceful 불변식 유지).
- **컴플라이언스:** 시스템 프롬프트에 수익 단정·과장 금지(표시광고법) 명시. 출력은 일반 텍스트로만 사용(인젝션 방어 — payload는 우리 파이프라인 산출물이라 신뢰).
- **비용:** 승인당 +1 LLM콜(~0.05원, flash-lite). Gamma 크레딧 대비 무시. 키 없으면 조립 폴백이라 비용 0.
- **검증:** 회귀 orc 67(감마프롬프트 5건 신규: 성공·키부재·빈약·실패·generate연동)+srv 12=79 PASS(의존성 0). 기존 Gamma 테스트는 에이전트 실패→조립 폴백 경로로 여전히 통과(폴백 실증). 실 LLM 동작은 프로덕션 /pd e2e로 검증(BizRouter 키 로컬 부재).
- **범위 밖(YAGNI):** 슬라이드 수 동적 결정·테마/이미지 프롬프트 LLM 생성(Gamma 엔진 일임)·발표 톤 사용자 선택(현 professional 고정).

## ADR-023 — `프레젠테이션 기획서 작성 가이드`(116줄) — 딥리서치 0건 + agent_gamma_prompt 프롬프트 보강
ADR 처리 이력 0건이던 외부 가이드(프레젠테이션 기획서 작성 방법론: 두괄식·메시지형 헤드라인·1슬라이드1메시지·역순작성·슬라이드 규격·타이포 위계·60-30-10 컬러·2단계 목차·패널 강조·표준 템플릿, 출처 13개). propose-research로 점검. **Phase A "신규 딥리서치 0건" → Phase B(독립 haiku) CONFIRM, self_rationalization_risk LOW, missed_gaps none.**
- **딥리서치 0건 근거:** 가이드는 두 부류. ① **PPT 소프트웨어 조작 디테일**(A4 29.7cm 수동입력·'디자인'탭·'그림 서식' 색 필터·pt 크기·60-30-10 컬러) = 우리와 무관(Gamma API에 inputText 텍스트만 전송, 슬라이드 디자인/규격/색/폰트는 Gamma 엔진 담당). ② **슬라이드 구성 원리**(두괄식·메시지형 헤드라인·1슬라이드1메시지·역순작성·패널) = 이미 출처 13개 갖춘 검증된 방법론이라 추가 외부 조사 불요. ADR-015/016("방법론 가이드 = 이미 적용 가능, 딥리서치 범위 밖") 동형.
- **★ 코드 개선(딥리서치 아닌 구현):** ②의 슬라이드 구성 원리가 `agent_gamma_prompt`(ADR-022)의 시스템 프롬프트에 **부재**함을 실측 확인(현재 "발표 서사 재구성" 추상 지시만). 가이드에 검증된 답이 있으므로 외부 조사 없이 바로 프롬프트에 주입 — 두괄식(결론 먼저)·메시지형 헤드라인(의미 없는 명사형 제목 금지)·1슬라이드1메시지·역순 압축·패널 강조·2단계 목차 원칙. 이는 propose-research 산출물(딥리서치 프롬프트)이 아니라 별도 코드 작업으로 분리 실행.
- **결론:** 신규 딥리서치 프롬프트 0건. 가이드의 PPT 조작 디테일은 Gamma 일임이라 영구 무관. 슬라이드 원리는 코드(agent_gamma_prompt)에 직접 본문화. 재호출 시 이 ADR로 재추출 차단.
