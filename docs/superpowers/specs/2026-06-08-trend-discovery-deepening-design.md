# 설계 — 트렌드 탐색 심화 (다단계 체인 + 공유 캐시)

- 작성일: 2026-06-08
- 대상: `50-projects/content-pd-agent/orchestrator.py` `fetch_live_trends`
- 접근법: **A — `fetch_live_trends` 내부 다단계 확장** (시그니처 유지, 호출처 2곳 무변경)
- 사용자 확정: 기존 심화(노드 신설 X) · 다단계 체인 · 둘 다 적용 · 공유 캐시+env

## 1. 문제

현재 `fetch_live_trends(topic)`는 **Sonar 1콜로 끝**난다. `/api/suggest` 실측 결과:
- 키워드는 실시간(Sonar 출처 실재)이나 **깊이·교차검증 없음**
- 출처가 "2026 전망 글" 위주 — **신선도 측정 없음**
- 단발이라 "구체 사례·왜 지금 뜨는지"를 못 판다

호출처 2곳: `run()`(983줄, /pd 본행)·`suggest_topics()`(690줄, 홈 칩). 둘 다 같은 1콜 한계.

## 2. 확정 결정

| 항목 | 결정 |
|---|---|
| 형태 | 기존 `fetch_live_trends` 내부 심화 (ADR-010/013 — 노드 신설 X) |
| 방식 | 다단계 체인: 광역 스캔 → 심화 조사 → 교차검증(코드) |
| 적용 | 둘 다 (`run` + `suggest_topics`) |
| 비용 통제 | 모듈 TTL 공유 캐시(run·suggest 중복 제거) + `TREND_DEPTH` env |
| 의존성 | urllib/stdlib만, 의존성 0 |

## 3. 다단계 체인 (3단계)

```
fetch_live_trends(topic)
  │  [공유 캐시 조회 — topic 키, TTL 내면 즉시 반환]
  ├─ ① _trend_scan(topic)      Sonar 1콜: 광역 키워드 N개 + 출처
  │                            (현재 fetch_live_trends 로직 = 이 단계)
  ├─ ② _trend_deepen(topic, scan)  Sonar 1콜 (DEPTH≥2): 상위 키워드 묶어
  │                            "구체 사례·왜 지금·신선도 신호" 심화 조사
  │                            → 키워드별 detail·recency_hint 보강
  ├─ ③ _trend_score(trends, sources)  코드 (LLM 0콜): 출처 URL 개수·
  │                            도메인 다양성으로 freshness_score 부여 +
  │                            과장/광역 키워드 강등(정렬)
  └─ [캐시 저장 + 반환]
```

**반환 형태(하위호환):** `{trends:[{keyword, why, detail?, freshness_score?}], sources:[...]}`.
기존 소비자(`agent_trend_analyst`·emit)는 `keyword`/`why`만 읽으므로 추가 필드는 무시 → **무변경 동작**.

## 4. 컴포넌트 (orchestrator.py)

```python
TREND_DEPTH = int(os.environ.get("TREND_DEPTH", "2"))        # 1=광역만, 2=+심화, 3=+교차검증강화
TREND_CACHE_TTL = int(os.environ.get("TREND_CACHE_TTL", "1800"))  # 30분, suggest 캐시와 동일 철학
_trends_cache = {}   # {topic: (monotonic_at, result)}

def _trend_scan(topic) -> dict:
    """① 광역 — Sonar 1콜. 현재 fetch_live_trends 본문이 그대로 이동."""

def _trend_deepen(topic, scan) -> dict:
    """② 심화 — Sonar 1콜. scan 상위 키워드를 한 번에 묶어 구체 사례·왜 지금·신선도 조사.
    실패 시 scan 그대로 반환(graceful)."""

def _trend_score(trends, sources) -> list:
    """③ 코드 — 출처 수·도메인 다양성으로 freshness_score(0~1) 부여 + 정렬. LLM 0콜."""

def fetch_live_trends(topic) -> dict:
    """공유 캐시 → _trend_scan → (DEPTH≥2) _trend_deepen → _trend_score → 캐시 저장.
    시그니처·반환 키 유지(호출처 2곳 무변경). 각 단계 graceful 폴백."""
```

- **공유 캐시:** `run(topic)`과 `suggest_topics`(topic="비개발자 AI 노코드 쇼츠 콘텐츠")가 서로 다른 topic이면 캐시 분리. 같은 topic 반복 호출만 절약. server.py의 `/api/suggest` TTL 캐시는 별개 레이어(그대로 유지) — 이건 orchestrator 내부 중복 차단용.
- **graceful 불변식:** scan 실패→`{trends:[],sources:[]}`. deepen 실패→scan 결과. score는 순수 코드라 무실패. 어느 경우도 예외 안 던짐(기존 계약 유지).

## 5. 비용

- DEPTH=2 기본: Sonar 2콜/호출(~16원). 캐시 적중 시 0.
- DEPTH=1: 현재와 동일(1콜). env로 즉시 폴백 가능 — 비용 급할 때.
- DEPTH=3: deepen 프롬프트에 교차검증 강화 지시(콜 수 동일, 품질만↑). 별도 콜 추가 안 함(YAGNI).
- 캐시 TTL 30분 → 같은 topic 반복(suggest 새로고침·연속 /pd)에서 호출 폭주 차단.

## 6. 테스트

- `_trend_scan`: Sonar mock → trends 파싱 (기존 fetch_live_trends 테스트 계승)
- `_trend_deepen`: scan + Sonar mock → detail 보강. Sonar 실패 → scan 그대로(graceful)
- `_trend_score`: 출처 다양성별 freshness_score·정렬 (순수 코드, 결정론)
- `fetch_live_trends` 캐시: 같은 topic 2회 → Sonar 1회만 (캐시 적중)
- DEPTH=1 env → deepen 건너뜀(1콜)
- graceful: scan 실패 → `{trends:[],sources:[]}`
- **기존 회귀 전부 PASS** (시그니처·반환 키 유지 → 기존 경로 무변경)

## 7. 범위 밖 (YAGNI)

- 트렌드 영속화(20-knowledge/trends/ 적측) — 별도 배치 잡 영역, 현 범위 아님
- 교차검증 전용 3번째 Sonar 콜 — DEPTH=3은 프롬프트 강화로 흡수(콜 추가 X)
- 트렌드 신선도 ML 점수 — 출처 메타 기반 휴리스틱으로 충분
