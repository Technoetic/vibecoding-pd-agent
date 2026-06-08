# 추천 주제 환각 게이트 + G9 보강(테스트·캐시) — 설계

- 작성일: 2026-06-08
- 영역: `50-projects/content-pd-agent`

세 가지를 한 번에 처리한다. 모두 독립적이라 한 커밋씩 분리한다.

---

## A. 추천 주제 환각 결정론 게이트 (suggest_topics)

### 문제
`suggest_topics`는 LLM 생성 topic을 **결정론 검증 없이 그대로 반환**한다([orchestrator.py:953-959]).
기획안(script)에는 `overclaim_check` 결정론 게이트가 있으나, 추천 주제엔 없어
`"GPT-4o, Gemini 1.5 Pro를 넘어선 AI IDE..."` 같은 **구형 모델 우월 비교 환각**이 production에 노출됐다.
(GPT-4o·Gemini 1.5는 2024 구형 모델 + IDE가 LLM을 "넘어섰다"는 범주 오류.)

### 해결: 결정론 stale-model 게이트 (`_stale_model_check`)
LLM 프롬프트 지시(연도 하드룰)는 1단일 뿐 — 어길 수 있다. 코드 게이트가 최종선.

탐지 패턴(정규식):
- **구형 모델명**: `GPT-4o`, `GPT-4 Turbo`, `GPT-3.5`, `Gemini 1.5`, `Gemini 1.0`, `Gemini Pro`(버전 없는 구형 표기), `Claude 3`(4 아닌), `Llama 2/3`
- 단독 등장만으로는 불충분(맥락 따라 정당할 수 있음) → **우월 비교 표현과 동시 등장 시만 차단**:
  `넘어선|넘어서는|뛰어넘는|능가|압도|이긴|제친|�​보다 (나은|뛰어난|강력)`

판정: title 또는 why에 (구형 모델명 AND 우월비교) 동시 매칭 → 그 topic **제거(버림)**.

### 왜 거부(버림)인가 (재생성 아님)
- 틀린 주제를 노출하느니 안 보여주는 게 안전(교육 채널 신뢰).
- 재생성 LLM 콜은 비용·지연 + 또 환각 가능 → YAGNI. 통과분만 노출, 부족하면 적게.
- suggest는 이미 graceful(빈 결과 시 프론트가 채널/샘플 폴백).

### 적용 지점
`suggest_topics`의 topics 누적 루프에서 각 topic을 `_stale_model_check`로 필터.
필터된 개수를 로그로 남긴다(silent drop 금지 — 무엇을 걸렀는지 가시화).

---

## B. generate_thumbnail 폴백 단위 테스트 (G9 테스트 0건 해소)

검증 워크플로우 confirmed(high): 신규 함수 테스트 0건. 비용 통제 토글 계약이 회귀 무방비.

`test_orchestrator.py`에 추가:
1. `THUMBNAIL_IMAGE=0` → `generate_thumbnail(...)` is None
2. `API_KEY=""` → None
3. 빈/공백 prompt → None
4. (mock urlopen) 한글 프롬프트 → 전송 body에 `_THUMB_EN_DIRECTIVE` prepend 확인
5. (mock) image_url 멀티파트 응답 → base64 data URL 추출 + cost_total 누적

`test_server.py`에 추가:
6. `_handle_thumbnail`: 빈 prompt → 400
7. (mock generate_thumbnail) → `{"status":"ok","image":...}` / None → `{"status":"failed"}`

기존 테스트 픽스처(`fake_urlopen`/`_CapHandler`) 패턴을 따른다.

---

## C. /api/thumbnail prompt 해시 TTL 캐시 (비용 DoS 완화)

검증 워크플로우 medium: 무인증 공개 엔드포인트 → 동일 prompt 반복도 매번 과금.

`server.py`에 prompt 해시(sha256) → (timestamp, image) TTL 캐시 추가:
- TTL: `THUMBNAIL_CACHE_TTL` 환경변수(기본 3600초). 같은 prompt 재호출 시 캐시 반환(과금 0).
- `_suggest_cache` 패턴과 동형(dict + lock + monotonic).
- 캐시 키는 prompt 원문 sha256. 메모리 상한: 간단히 항목 수 캡(예: 64개, LRU 아닌 단순 truncate)으로 무한증식 차단.
- graceful: 캐시 미스 시 기존 경로.

> 인증/레이트리밋 전면 도입은 범위 밖 — `/api/pd`와 공유된 데모 트레이드오프(검증 결과도 medium으로 하향). 캐시가 가성비 최선.

---

## 검증
- A: `_stale_model_check` 단위(환각 샘플 차단 + 정상 주제 통과) + 실측 suggest 출력 확인
- B: 추가 테스트 + 전체 회귀 PASS
- C: 캐시 hit/miss 단위 + 동일 prompt 2회 호출 시 2번째 즉시 반환 확인
- 배포 후 production /api/suggest에 환각 패턴 안 나오는지, /api/thumbnail 캐시 동작

## 범위 밖 (YAGNI)
- 추천 주제 재생성 루프, OCR, 전면 인증/레이트리밋, LRU 정밀 캐시.
