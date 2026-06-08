# 설계 — `/pd` 파이프라인 Gamma 슬라이드 자동 생성 통합

- 작성일: 2026-06-08
- 대상: `50-projects/content-pd-agent` (Railway 배포 웹앱 `vibecoding-pd-web-production.up.railway.app`)
- 관련: ADR-019(Gamma 가이드 점검), domain-priorities G9/G10
- 접근법: **A — 서버 사이드 백그라운드 + 클라이언트 폴링** (사용자 확정)

## 1. 목표

`/pd` 오케스트레이션에서 Reviewer 승인이 나면, 승인된 기획안을 **Gamma 프레젠테이션(PDF)** 으로 자동 생성하고, 사용자 브라우저에서 PDF 링크 표시 + 새 탭 자동 오픈한다.

## 2. 확정된 결정 (사용자 + 자율)

| 항목 | 결정 | 근거 |
|---|---|---|
| 트리거 | **승인 즉시 자동** | 사용자 선택 |
| 출력 | **PDF 링크 + 새 탭 자동 오픈** | 사용자 선택 |
| 생성 흐름 | **분리** — 승인(done)은 즉시 표시, Gamma는 별도 폴링 | 사용자 선택. SSE 타임아웃/502 회피 |
| 실패 처리 | **기획안 정상 + 슬라이드만 실패 표시** (graceful degradation) | 사용자 선택. Gamma는 부가기능 |
| 키 관리 | `GAMMA_API_KEY` 서버 환경변수만, 브라우저 노출 0 | server.py 기존 원칙 |
| 의존성 | urllib(stdlib)만, 의존성 0 유지 | Dockerfile·ADR-014 정합 |
| numCards | 9 (고정. 기획안 슬라이드 매핑) | /gamma 실측 적정 |
| exportAs | pdf | 사용자 선택 |

## 3. 아키텍처 & 데이터 흐름

```
클라이언트                  server.py (Railway)                 Gamma API
   │ POST /api/pd (SSE)         │                                   │
   ├──────────────────────────▶│ orchestrator.run()                │
   │ ◀── step…(supervisor~reviewer)…승인…                          │
   │                            │ ① gamma_generate(payload) 블로킹0 │
   │                            ├──── POST /v1.0/generations ──────▶│
   │                            │ ◀── {generationId} ───────────────┤
   │ ◀── done{payload, gamma:{id, status:"generating"}}            │
   │ [기획안 즉시 렌더 + "슬라이드 생성 중…"]                      │
   │ GET /api/gamma?id= (5초폴링)│                                   │
   ├──────────────────────────▶│ ② gamma_status 프록시             │
   │                            ├──── GET /v1.0/generations/{id} ──▶│
   │                            │ ◀── {status, gammaUrl, exportUrl}─┤
   │ ◀── {status:"completed", pdf_url, gamma_url}                  │
   │ [PDF 링크 + window.open(pdf_url)]                             │
```

## 4. 컴포넌트별 변경

### 4.1 orchestrator.py (백엔드)

**신규 함수 2개 (urllib, call() 패턴 정합):**

```python
GAMMA_API_KEY = os.environ.get("GAMMA_API_KEY", "")
GAMMA_BASE = "https://public-api.gamma.app/v1.0"

def gamma_build_input(payload: dict, topic: str) -> str:
    """승인 payload(title/script/storyboard/thumbnail_prompt/hashtags)를
    Gamma inputText로 가공. 일반 텍스트(슬라이드 구획 힌트 포함)."""

def gamma_generate(payload: dict, topic: str) -> dict:
    """POST /generations — 생성요청만(폴링 안 함, 블로킹 0).
    성공: {"id": genId, "status": "generating"}
    실패(키부재·HTTP오류): {"status": "failed", "error": "..."} — 예외 던지지 않음(기획 보호)."""

def gamma_status(gen_id: str) -> dict:
    """GET /generations/{id} — server.py 프록시가 호출.
    {"status": "completed|pending|failed", "pdf_url": ..., "gamma_url": ..., "credits": ...}"""
```

- `gamma_generate`는 **키 없으면 즉시 `{status:"failed", error:"GAMMA_API_KEY 미설정"}`** 반환 (예외 X — 기획안 보호)
- 비용/토큰은 BizRouter usage가 아니므로 token_usage에 누적하지 않음(별도 크레딧 체계). credits는 status 응답에서 노출만.

**done emit 변경 (999줄):**
```python
gamma_info = gamma_generate(task["content_payload"], topic)  # 블로킹 0
emit("done", verdict="approved", title=..., payload=..., cost_krw=..., token_usage=...,
     eval=..., gamma=gamma_info)   # ← gamma 필드 추가
```
- escalated(미승인)에는 Gamma 생성 안 함 — 승인된 기획안만 슬라이드화.

### 4.2 server.py (프록시 엔드포인트)

**신규 `GET /api/gamma?id=<genId>`:**
```python
if path == "/api/gamma":
    gen_id = parse_qs(...)["id"]
    try:
        data = orc.gamma_status(gen_id)   # 키는 orchestrator가 환경변수에서
    except Exception as e:
        data = {"status": "failed", "error": str(e)[:200]}
    self._send(200, "application/json", json.dumps(data).encode())
```
- `_run_lock` **사용 안 함** — Gamma 상태조회는 BizRouter 모델호출이 아니라 502 레이스 무관, 가볍고 stateless.
- id 검증: 영숫자만(`^[A-Za-z0-9]+$`), 길이 상한.

### 4.3 web/index.html (프론트)

**renderResult 변경 (done 분기):**
- 기획안 즉시 렌더(기존)
- `d.gamma`가 있으면 슬라이드 영역 추가:
  - `status:"generating"` → "📊 슬라이드 생성 중…" 스피너 + `pollGamma(d.gamma.id)` 시작
  - `status:"failed"` → "📊 슬라이드 생성 실패: <error>" (기획안은 정상 표시 유지)

**신규 `pollGamma(id)`:**
- 5초 간격 `fetch('/api/gamma?id='+id)`, 최대 24회(2분)
- `completed` → PDF 링크 + Gamma 링크 표시 + `window.open(pdf_url, '_blank')` (1회만)
- `failed` → 실패 표시 + 재시도 버튼(자율 추가 — 비용 0, UX 향상)
- 타임아웃 → "생성 지연 — 잠시 후 새로고침" 안내 + 수동 확인 링크

### 4.4 인프라

- Railway env에 `GAMMA_API_KEY` 추가 (배포 검증 단계에서)
- Dockerfile 변경 없음(의존성 0 유지)
- ORCHESTRATION.md/README에 Gamma 통합 절 + env 문서화

## 5. 에러 처리 (실패 격리 매트릭스)

| 실패 지점 | 동작 | 사용자 영향 |
|---|---|---|
| GAMMA_API_KEY 미설정 | gamma_generate가 `{status:failed, error}` | 기획안 정상, "슬라이드 미설정" 표시 |
| POST /generations HTTP 오류 | 동일 graceful | 기획안 정상, 실패 표시 |
| 폴링 중 failed | 프론트 실패 표시 + 재시도 | 기획안 정상 |
| 폴링 타임아웃(2분) | 안내 + 수동 확인 링크 | 기획안 정상 |
| 크레딧 소진(402) | error 메시지에 노출 | 기획안 정상 |

**불변식:** Gamma 실패는 절대 기획안(`done` payload) 표시를 막지 않는다.

## 6. 테스트

### 6.1 단위/회귀 (test_orchestrator.py)
- `gamma_build_input`: payload → inputText 변환 (필드 포함 확인)
- `gamma_generate` 키 부재: `{status:failed}` 반환, 예외 X (monkeypatch GAMMA_API_KEY="")
- `gamma_generate`/`gamma_status` HTTP: urllib mock으로 200/4xx 분기
- done emit에 gamma 필드 포함 (mock run)
- **기존 회귀 전부 PASS 유지** (Gamma는 additive — 기존 경로 무변경)

### 6.2 서버 (test_server.py)
- `GET /api/gamma?id=X`: orc.gamma_status mock → JSON 반환
- id 검증: 잘못된 id 거부

### 6.3 e2e (실 키)
- 실 GAMMA_API_KEY로 `/pd` 1회 종단: 승인 → done에 gamma.id → /api/gamma 폴링 → completed → pdf_url
- Playwright: 승인 결과 화면에 슬라이드 링크 표시 + 새 탭 확인

## 7. 비용 주의

- 호출당 크레딧 ~41 (실측). **승인 즉시 자동**이라 매 승인마다 소모.
- 잔여 크레딧은 status 응답 `credits.remaining`으로 프론트에 표시(투명성).
- (향후 후속) 비용 통제가 필요하면 env 토글로 자동→수동 전환 가능하게 설계 여지 남김. 현 범위 아님.

## 8. 범위 밖 (YAGNI)

- from-template(브랜드 템플릿) — 현 범위 아님, 텍스트 생성만
- 자동→수동 env 토글 — 사용자가 "자동" 명시. 후속 여지만.
- PPTX export — PDF만(사용자 선택)
- 크레딧 사전 차단 게이트 — status에 노출만, 하드 게이트는 후속
