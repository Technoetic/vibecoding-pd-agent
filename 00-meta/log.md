---
title: "작업 로그"
type: journal
status: active
ai_priority: medium
created: 2026-06-07
updated: 2026-06-07
tags:
  - meta
  - log
related:
  - "[[index]]"
---

# 작업 로그

시계열 감사 로그. **새 항목은 항상 이 줄 바로 아래 최상단에 1줄로 추가**한다.

- 2026-06-08 — /propose-research(바이브코딩 트렌드 정보 채널 순위 가이드) → 신규 딥리서치 프롬프트 1건. 이 가이드는 ADR-014/015/016/019의 '도구 가이드'와 달리 콘텐츠 도메인 직격 자료(바이브코딩 트렌드 정보 생태계·채널 랭킹). Phase A 결손 발굴: 시장구조 노트에 경쟁 4채널만 있고 '트렌드 정보 소스 계층 지형'(1차담론 포럼→번역 미디어→튜토리얼 채널) 부재. Phase B(haiku 독립) ACCEPT(경로실존·결손실재·기존3건 중복0·ADR-008/011 거부원칙 입력본이 능동차단·식별자누설0·페어완성). 페어 작성: research/PROMPT_한국 바이브코딩 트렌드 소스 지형.{md,deepresearch.txt}. 입력본은 외부 일반화(구독자수·자기신고수익 인용금지를 검증기준에 탑재). 채택은 딥리서치 결과를 /squeeze-report로 사실성 분리 후 시장구조 노트 확장.
- 2026-06-08 — 감마 프롬프트 작성 에이전트(ADR-022): "감마 프롬프트 에이전트 있어?" 질문에서 기존 gamma_build_input이 LLM 없는 조립 함수(필드 나열)임을 확인 → LLM 능동 재구성으로 격상. agent_gamma_prompt가 승인 기획안을 발표 서사(제목→핵심→타겟·훅전략→스크립트→스토리보드→썸네일→배포)로 재구성. gamma_generate가 agent_gamma_prompt() or gamma_build_input()으로 이중 안전망(에이전트 키부재·예외·빈약<100자면 조립 폴백). 비용 +1 flash-lite콜(~0.05원, Gamma크레딧 대비 무시). 컴플라이언스(수익단정 금지) 시스템프롬프트 명시. 회귀 orc67(감마프롬프트5건)+srv12=79 PASS(의존성0). 기존 Gamma테스트는 에이전트실패→조립폴백으로 여전히 통과(폴백실증). 실LLM동작은 프로덕션 /pd e2e 검증. (commit 대기)
- 2026-06-08 — 트렌드 탐색 심화 다단계 체인(ADR-021): "최신 트렌드 탐색 에이전트 추가" 요청을 '기존 fetch_live_trends 내부 심화'(노드 신설 X, ADR-010/013 정합)로 구현. /api/suggest 실측 약점(Sonar 1콜·전망글 위주·신선도 측정 없음) 정조준. 접근법 A(시그니처 유지): ① _trend_scan 광역 Sonar1콜 ② _trend_deepen 심화 Sonar1콜(detail 보강) ③ _trend_score 코드0콜(freshness_score+정렬). 공유 캐시 _trends_cache(TTL 1800s)로 run·suggest 중복호출 0. TREND_DEPTH env(1=현행폴백/2=기본/3=교차검증강화). graceful: 광역실패→빈결과, 심화실패→광역유지, 추가필드는 기존소비자 무시(하위호환). 반환키 불변→호출처 2곳·agent_trend_analyst·emit 무변경. 회귀 orc62(트렌드9건)+srv12=74 PASS(의존성0). 프로덕션 다단계 실e2e는 배포 후 검증. (commit 대기)
- 2026-06-08 — Gamma 슬라이드 결과 UI 단순화: 잔여 크레딧·Gamma 편집 링크 제거, PDF 열기 버튼만(사용자 요청). 미사용 .glink.sec CSS 제거. 회귀 65 PASS·시각확인. 배포 d69bd617. (commit dbb2d1b)
- 2026-06-08 — Gamma 슬라이드 자동 생성 파이프라인 통합(ADR-020, G9/G10 부분 실현): /pd 승인 즉시 기획안을 Gamma 프레젠테이션(PDF)으로 자동 생성. brainstorming→설계(docs/superpowers/specs/)→구현→e2e. 접근법 A(서버 백그라운드+클라 폴링): gamma_generate 생성요청만(블로킹0)→done에 gamma{id,status}→프론트 /api/gamma 5초폴링→completed면 PDF 새탭. 거부: SSE내 끝까지폴링(502/락점유)·클라 직접호출(키노출). orchestrator gamma 함수 3개(urllib 의존성0)+server.py /api/gamma 프록시(id 정규식검증)+web/index.html 슬라이드영역·폴링·window.open. graceful 불변식: Gamma 실패는 기획안 표시 안 막음. 🔬 실버그수정: Cloudflare가 Python-urllib UA를 403 code1010 차단→User-Agent 헤더 추가. 검증: 회귀 orc53+srv12=65 PASS(의존성0), 실Gamma키 백엔드e2e(생성→폴링50초→PDF), 프록시 curl 3종, Playwright 프론트e2e(UI·window.open·JS에러0·시각). Railway GAMMA_API_KEY env 추가 필요. (commit 대기)
- 2026-06-08 — /propose-research(Claude Code×Gamma API 프레젠테이션 자동화 가이드 449줄) → 신규 딥리서치 프롬프트 0건(ADR-019). Phase A "0건" 판정을 Phase B 독립 haiku가 ACCEPT(self_rationalization_risk LOW, missed_gaps none). 근거: 순수 도구 사용법(산출물=PPTX, 콘텐츠PD 기획 0줄)·인프라/설정 영역(propose-research 범위 밖)·인접가치는 G9/G10 사용자결단에 기매핑. ADR-014/015/016 동형. 실측: 지식노트 풀 충실(미검증 마커 3건은 저자 의도 경계)·eval 12종 evidence 12/12 실존·남은 결손은 조건의존/사용자결단(미처리 아님). 가이드 본문 Claude Code/Gamma 사실오류 의심은 squeeze-report 영역(propose-research 아님). 페어 파일 신규 0, decisions.md ADR-019 영속.
- 2026-06-08 — 반복 반려 근본수정(keyword_inclusion 매칭 결함): "키워드 포함 비율 낮음"으로 3회차 반복반려→에스컬레이션. 적대적 3관점 분석으로 근인 확정=exact-substring 매칭(`k in s`)이 한국어 조사·어순 굴절을 전부 0점 처리(온토픽 스크립트도 0/5 실측). 수정 A: keyword_inclusion_score를 근접 토큰 매칭(_keyword_present)으로 교체—단일토큰 substring/복합토큰 70% 근접군집, 흩어진 우연·공통토큰 스터핑 차단으로 결정론 엄정성 보존, missing 반환 추가(Creator 피드백 경로). 수정 B: Trend Analyst 키워드를 1~2어절 짧은 명사구로 제약(증폭기 차단). 거부: min_ratio 하향·동의어사전·임베딩·형태소분석기·LLM재호출(과수정). State.json 실측으로 '긴키워드 근인설' 정정(증폭기일 뿐). 회귀 55 PASS(양방향 4종 신규: 자연변형 인정+흩어짐/오프토픽/스터핑 차단). 사용자 케이스 0/5→5/5. (commit 대기)
- 2026-06-08 — 에스컬레이션 UX 개선(막다른 길 제거): "검수 미달 — 에스컬레이션 (재시도 3회 초과)"가 빨간 라벨+빈 결과만 뜨던 막다른 길을 안내형으로 전환. 진단 결과 에스컬레이션은 버그 아닌 정상동작(미달 기획 거부, State.json 승인율 8/9). 백엔드 escalated emit에 payload(마지막 미승인 초안)·feedback_log(회차별 반려)·failed_metrics(마지막 검수 실패항목) 추가. 프론트 renderResult 에스컬레이션 분기: "미승인 초안" 경고배지+초안 참고노출+반복미달 항목(한국어 라벨)+마지막 반려사유+'주제 구체화 재시도' 가이드/버튼. 회귀 55 PASS(orc 46+srv 9, escalation payload 통합테스트 신규), Playwright 실측 PASS(배지·초안·안내·재시도포커스, JS에러 0). 동작 로직 무변경. (commit 대기)
- 2026-06-08 — 동시요청 502 수정(배포 회귀): /api/pd 실행 시 "중단됨: HTTP 502" 발생. 재현 결과 /api/suggest?refresh=1 + POST /api/pd 동시 발사 시 둘 다 x-railway-fallback 502로 컨테이너 사망. 적대적 4관점 분석으로 근본원인 확정=동시 BizRouter 모델호출 시 프로세스 사망(OOM 기각: digest 실측 29KB / 전역레이스 기각: 키없으면 안죽음). 원래 _run_lock 직렬화 설계를 신규 /api/suggest가 락 밖 호출로 깬 것. 수정: get_suggestions를 _run_lock.acquire(timeout=2)로 직렬화(못잡으면 busy 폴백), worker except에 traceback.print_exc 관측성. 회귀 54 PASS(orc 45+srv 9, 동시성 3종 신규), Playwright 실제경로(로드직후 생성클릭) 완주 실측—502 없음·done 도달. railway up 재배포(자동배포 끊김 상태). (commit 94de027)
- 2026-06-08 — 홈 화면 '동적 주제 제안' 신설: 하드코딩 칩 완전 제거 요청("동적으로 제안되게") 반영. orchestrator.suggest_topics(n) 신설(Sonar 실시간 트렌드+채널 인기주제+지식노트→flash-lite가 '지금 뜨는 쇼츠 주제' 생성, 컴플라이언스 준수, 과거 산출물 재탕 아님). server.py /api/suggest + TTL 캐시(30분, 빈결과 비캐시·refresh 우회 — 접속당 유료호출 폭주 차단). index.html renderChips를 /api/suggest 우선→/api/samples 폴백으로, 🔄새로고침 버튼·why 툴팁·출처 라벨 추가. 회귀 51 PASS(orc 45+srv 6), Playwright 실측 ok/empty 양모드 PASS(JS에러 0). → Railway 배포 동반.
- 2026-06-08 — 웹 데모 진행 애니메이션 UX 구동(index.html): 직전 추가된 진행바·경과시간·스피너 CSS가 구동 JS 0으로 죽어있던 것을 적대적 다관점 설계(3관점→심사→합성, 12결함 회피)로 전면 구현. 칩 하드코딩 제거→/api/samples 실데이터 동적화("하드코딩 싫어" 반영), 단계 가중치 진행바(시간충전 금지=정직성)·reviewer 실측 seen/12, creator·reviewer 동시-active 버그 setStep 단일함수 불변식으로 수정. Playwright 실측 happy/reject/error 3시나리오 PASS(JS에러 0, rejected 되감김·error 폭동결 정직성 확인). 테스트 잔여물(bad.json·TEST_001.md) 삭제. (commit f6217a0)
- 2026-06-07 — 적대적 오케스트레이션 검증(4관점) 반영 결정론 누수 3건 수정(ADR-018): A 2티어 강제반려(hook음절>21·해시태그 하드위반 추가, 009 22음절 누수 차단)·B overclaim 회피 6종 보강+골든셋·C length/keyword 결정론화. D 문서정정(reviewer.md 코사인→difflib·단일진실원천, ORCHESTRATION/ARCHITECTURE 갱신). 45테스트 PASS. 거시구조는 4관점 만장일치 정당(과설계 없음).
- 2026-06-07 — ARCHITECTURE.md 신설: 현 오케스트레이션 구조 종합(시스템 다이어그램·4에이전트·eval 12종·파일맵·불변원칙). ORCHESTRATION.md(상세설계)와 구분된 "한눈에 보기" 종합본. 실측 기반(함수 28·테스트 41). index 등록.
- 2026-06-07 — /propose-research 'Gemini 2.5 Flash Lite 활용 전략'(172줄, _가이드 원본): 신규 0건. ADR-007로 이미 처리(채택 0, 영구거부 상세). ADR-007에 재점검 메모. **→ _가이드/ 8종 전부 처리 완료 + 외부 딥리서치 4종 완료 = propose-research/squeeze-report 소스 전면 소진.** (분석/판정 불요 — 처리이력 명백)

- 2026-06-07 — 채용 제출물 완성(ADR-017 ACCEPT 3건): C1 PORTFOLIO.md(대표 5건 큐레이션+채널반영 주석)·C2 SESSION_LOG.md(/pd 009 전체 터미널 실행 증빙, eval 12종 ✅)·C6 ORCHESTRATION.md Eval 설계철학(12메트릭 선정근거+ADR 매핑). 회귀 41 PASS.
- 2026-06-07 — /pd '비개발자가 AI로 사장님 가게 리뷰 자동 응대 만들기' → CONTENT_2026_009 승인(C2 세션로그용). eval 12종 전부 통과·트렌드 4건·채널중복 0.25. output/CONTENT_2026_009.md (비용 13.309원)
- 2026-06-07 — /propose-research 'AI 콘텐츠 PD 에이전트 제작 가이드'(129줄, 채용 합격 가이드): 딥리서치 0건이나 **제출물 완성도 결손 3건 식별**(판정 ACCEPT 3·REJECT 3·DEFER 1). ✅C1 포트폴리오·C2 세션로그·C6 eval설계철학(합격 가치, 사용자 확인 후 진행). ❌C4 faker(의존성0 위반)·C7 추정CTR점수(ADR-010 가짜통과 회귀, Critical)·C5 폴더형식. ⏸️C3 로드맵(G8/9/10 중복). ADR-017. **→ _가이드/ 8종 전부 처리 완료.**

- 2026-06-07 — /propose-research 'AI 에이전트 기반 SaaS 개발 방법론'(542줄, _가이드 원본): 신규 0건. 미반영 3건(.claudeignore=settings deny 중복, SessionStart/Stop 훅=🔵사용자결단)은 전부 인프라(딥리서치 아님). §4 Next.js/§6 MCP는 도메인무관·과설계. ADR-016. **→ _가이드/ 8종 전부 처리 완료(ADR-005~008·013~016). 외부 딥리서치 4종도 완료. propose-research 소스 소진.**

- 2026-06-07 — /propose-research '유튜브 채널 철학 분석 방법'(89줄, _가이드 원본): 신규 0건. ADR-008로 이미 추출 완료(통찰 5건 채택→채널분석 노트 반영, 법인수치 거부). 짜낼 가치 소진. ADR-008에 재추출 차단 메모 추가. (분석/판정 에이전트 불요 — 처리이력 명백)

- 2026-06-07 — 인프라 개선: schemas/naming.md 신설(CLAUDE.md §2 산재한 파일명·링킹·태그 규약 단일화, frontmatter.md와 역할분리). index 규약섹션 등록. settings.json plan모드 변경은 **의도적 미적용**(사용자 선호=즉시실행과 충돌). autoMemory 등도 불필요 복잡도라 미적용.

- 2026-06-07 — /propose-research '옵시디언 연동 CLAUDE.MD 작성 가이드'(263줄, _가이드 원본=우리 CLAUDE.md 설계원본): 신규 0건. 실측 정합 — 섹션구조·YAML 이중따옴표·슬래시명령어(/day·/ingest·/lint·/pd) 전부 이미 적용. ADR-015에 통합(인프라 가이드 일괄: 볼트구조+CLAUDE.md 작성법 둘 다 범위 밖·이미 적용).

- 2026-06-07 — /propose-research '옵시디언 볼트 디렉토리 최적화 제안'(253줄, _가이드 원본=현 볼트 설계원본): 신규 딥리서치 프롬프트 0건. 구조 이미 100% 적용(숫자접두사·격리·미니볼트). 분석이 12후보(agents.md·naming.md·process-inbox·settings 등) 추출했으나 전부 **딥리서치 프롬프트가 아닌 볼트 인프라/설정 작업** = 스킬 범위 밖 + 🔵 사용자 결단. 20-knowledge 3도메인은 의도적 편차(거부), 40-people·vault_migrate는 무관/과설계. ADR-015.

- 2026-06-07 — /propose-research '단일 경량 모델 오케스트레이션 가이드'(666줄, _가이드 원본): 신규 0건. ADR-005/006이 이미 추출, 666줄 재정독해도 잔여가치 0. 분석에이전트 8후보 중 5개 "적용가능" 추천 → 독립 판정에이전트(haiku) 8개 전부 REJECT(async/Pydantic=의존성0위반, config=ADR-006 보류, 캐싱/thinking/GoogleSearch=BizRouter불가 ADR-007, streaming/CodeExec=YAGNI). 분석/판정 분리가 엔터프라이즈 패턴 도입 자기기만 차단. ADR-014.

- 2026-06-07 — /squeeze-report 'Perplexity Sonar 활용법'(164줄): 우리 Sonar 구현이 모범사례와 정합 검증 — user 메시지 중심·citations 배열 추출 이미 정합, fetch_live_trends 프롬프트를 구체·서술형+그라운딩으로 강화. ORCHESTRATION.md Sonar 절 신설. BizRouter 경유 불가(전용 파라미터·LangChain·Pydantic·RAG·가격표) 영구거부(ADR-007 전례). ADR-013. 회귀 41 PASS.

- 2026-06-07 — /squeeze-report '한국어 헤드라인 구체성 CTR 연구'(142줄, G4 답): 보고서 결론이 "전이 미검증"이라 사실성 분리 핵심. **상승 구간 한국어 일치(검증)** + 하이브리드 공식·관계적 구체성·길이 제약 채택 → [[훅 구체성 역U자 법칙]] 정밀화. **하락 구간(역U자 우하향) 한국어 전이는 영구거부**(데이터 부재, "검증됨" 오채택 회피). G4 "통째 미검증"→"부분 해소(상승 검증/하락 미검증)" 격상. ADR-012. 회귀 영향 0(지식노트만).

- 2026-06-07 — /propose-research '한국어 헤드라인 구체성 CTR 연구': 신규 프롬프트 0건(G4 결손의 딥리서치 답이라 신규 불필요). PROMPT status 정정 3건 — 헤드라인역U자(G4)·쇼츠정량(G5)·채널성장 모두 draft→answered. 보고서는 squeeze-report 대상. **딥리서치 프롬프트 풀 3종 전부 답 수신 완료 = 미답 결손 0.**

- 2026-06-07 — /squeeze-report '한국 AI 교육 유튜브 성장 분석'(190줄): 경쟁채널 벤치마크(조코딩·장피엠·에어빌드)·롱폼↔쇼츠 퍼널·3대 훅패턴·한국 B2C/서구 B2B 구조 채택. 신규 노트 [[한국 AI 교육 유튜브 시장 구조]] + [[훅 구체성 역U자 법칙]] 3대 패턴 절 + hook_concreteness eval evidence 보강. 자기신고 수익수치·구독자수 영구거부(ADR-008/010 정합). ADR-011. 회귀 41 PASS. (코드 변경 0 — 시장 맥락 지식)

- 2026-06-07 — 팩트체크 추가(사용자 요청): 별도 5번째 에이전트 거부, Reviewer 하이브리드 강화. overclaim_check(과장단정 패턴 결정론)+extract_numeric_claims(수치주장 추출)+factual_accuracy eval. 비용 0(코드실측→payload→Reviewer 자동주입). 실동작 검증(과장 4-flag·정상통과·수치추출). 41테스트 PASS. ADR-010(ADR-007 과설계거부 정합).

- 2026-06-07 — /squeeze-report '숏폼 스크립트 정량 구조 연구'(140줄): G5 결손 본문화. 한국어 음절(SPM 356·훅 18~21음절)·해시태그 1~5개 결정론 측정 2종 신설(korean_syllable_density·hashtag_count eval, 함수 구현, 38테스트 PASS), 구간배분·정보사다리·패턴인터럽트는 [[쇼츠 스크립트 구조와 길이]]·retention_design 반영. 5초루프꼼수·WPM 1:1전이 영구거부. ADR-009. G4 한국어 전이의 부분 해답(시간비율 전이·발화량 음절).

- 2026-06-07 — B6 종단 검증(데모 서버 SSE): 신규 주제 '인스타 자동화'로 전 파이프라인 라이브 확인 → CONTENT_2026_008 승인(트렌드 5건+출처 8개·originality 0.0937·channel-dup 0.25·Eval 8종, 비용 11.945원). 채널중복 overlap·Sonar 견고파싱 수정 입증.
- 2026-06-07 — ⚠ CONTENT_2026_007: B6 종단 1차에서 채널중복 결함 노출 증거물. '개발 없이 5일 만에 수익 웹서비스' 주제가 채널 실제 영상과 자카드 0.5로 **잘못 승인**됨(구버전). overlap coefficient 보강(0.6667 차단)으로 수정 완료. 데모 샘플 부적합 — 결함 기록용 보존.
- 2026-06-07 — G6 모델: 비용 사유로 MODEL → google/gemini-2.5-flash-lite 되돌림(사용자 결단). 3.1은 단가 2.85배인데 품질 우위 미측정이라 정당화 불가. 종료(2026-10-16)까지 4개월+ 여유 → horizon 임박 시 1줄 교체(가용성·절차 실증됨). 회귀 9건 PASS. ADR-006 갱신.
- 2026-06-07 — G6실행 3.1-flash-lite 교체 실증: 라이브 chat probe 2모델 검증(json_object·usage 4키 OK) → 회귀 9건 PASS → /pd 종단 재검증(CONTENT_2026_006 승인, Eval 8종·originality 0.1059·income_claim 한국규제 차단 동작). ⚠ 단가 2.85배 관찰(ADR-006) → 위 줄에서 2.5로 되돌림.
- 2026-06-07 — /pd 'AI한테 코딩 시킬 때 초보가 가장 많이 하는 실수 3가지' → CONTENT_2026_006 승인. output/CONTENT_2026_006.md (비용 13.870원)
- 2026-06-07 — domain-priorities AI단독 결손 3건 일괄 처리: G1(originality 코사인 유사도 결정론 실구현+강제반려, 회귀 9건), G3(한국 표시광고법·공정위 반영), G6/G7(은퇴일 2026-10-16 검증·gemini-3.1-flash-lite 마이그레이션 절차). /pd 005로 G1 종단검증(실측 0.1297).
- 2026-06-07 — /pd '노코드로 사장님 가게 예약 시스템 만들기' → CONTENT_2026_005 승인. output/CONTENT_2026_005.md (비용 3.011원)
- 2026-06-07 — /domain-priorities: 결손 10건 5차원 점수화 → domain-priorities-2026-06-07.md. 1위 G1(코사인 유사도 실구현 40점), 2위 G6(모델 마이그레이션), 3위 G3(한국 수익규제). 은퇴일 2026-10-16 라이브 검증.
- 2026-06-07 — /squeeze-report '유튜브 채널 철학 분석'(89줄): 채널 통찰 5건 채택해 [[양실장 바이브코딩대학 채널 분석]] 보강(영업>코딩·5주계획·SME블루오션·경력≠만족). 법인 수치는 교차검증 불완전+불필요로 영구거부. ADR-008.
- 2026-06-07 — /squeeze-report 'Flash Lite 활용 전략'(172줄, 직전과 90% 중복): 채택 0. Flex/암시적캐싱은 BizRouter 측정불가, 나머지 Google SDK 전용 중복. 가격 $0.10/$0.40만 외부검증. ADR-007 영구거부 기록.
- 2026-06-07 — /squeeze-report(분석/판정 분리): Flash-Lite 오케스트레이션 가이드에서 ACCEPT 2(C2 온도 문서화·C3 토큰 로깅)·REJECT 3(과설계)·기각 10(Google SDK 전용). C3 회귀 4건 PASS, ADR-005/006 기록.
- 2026-06-07 — /pd 'AI 코딩 입문자가 처음 만든 것' → CONTENT_2026_004 승인. output/CONTENT_2026_004.md (비용 2.631원)
- 2026-06-07 — 딥리서치(104 에이전트) → 검증 지식 5종 영속화: 알고리즘 신호·훅 역U자·수익 리스크·스크립트 구조. 기존 훅 가정 교정, eval 8종 확장, 페르소나·CLAUDE.md 반영. /pd 재가동으로 신규 검사 작동 확인.
- 2026-06-07 — /pd 'AI로 비개발자가 만든 첫 앱, 무엇이 달랐나' → CONTENT_2026_003 승인. output/CONTENT_2026_003.md (비용 2.697원)
- 2026-06-07 — /pd '개발 없이 5일 만에 수익 웹서비스 만드는 비법' → CONTENT_2026_001 승인. output/CONTENT_2026_001.md (비용 2.309원)
- 2026-06-07 — 오케스트레이터 구축: orchestrator.py(BizRouter×gemini-2.5-flash-lite, 4-에이전트 Eval 루프) + ORCHESTRATION.md. 실가동 검증 완료.
- 2026-06-07 — 볼트 초기 구축: 엔드게임 디렉토리 골격, CLAUDE.md, settings.json, 4-에이전트 페르소나, 슬래시 커맨드 5종, LLM 위키 시드 노트 생성.
