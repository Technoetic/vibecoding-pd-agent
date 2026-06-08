# 썸네일 자동 이미지 생성 (G9) — 설계

- 작성일: 2026-06-08
- 영역: `50-projects/content-pd-agent` (AI 콘텐츠 PD 에이전트)
- 결손 ID: G9 (domain-priorities — 썸네일 프롬프트 → 이미지 생성 API 자동드롭)
- 선행 검증: BizRouter `google/gemini-2.5-flash-image` 실호출 성공(production 키, `railway run`). 응답은 OpenAI 호환 chat 형식, `message.content` 배열에 `{type:"image_url", image_url:{url:"data:image/png;base64,..."}}` 포함.

## 목적

현재 Creator 에이전트는 `thumbnail_prompt`(텍스트)만 생성하고, 화면엔 프롬프트 문자열만 표시한다. 이를 **실제 썸네일 이미지(나노바나나 = Gemini 2.5 Flash Image)** 로 생성해 화면에 보여준다.

## 요구사항 (확정)

| 항목 | 결정 |
|---|---|
| 트리거 | 기획 생성 완료 시 **자동** 1장 |
| 표시·저장 | base64 **화면 표시만** (State.json·파일 저장 안 함) |
| UX | **비동기 로딩** — 기획안 즉시 표시, 이미지는 별도 요청으로 준비되면 교체 |
| 비용 안전 | `THUMBNAIL_IMAGE` 환경변수 토글(기본 ON) + 키 없음/실패 시 graceful 폴백(프롬프트 텍스트) |

## 아키텍처 (기존 Gamma 프록시·폴링 패턴 재사용)

```
[기획 생성 완료 / SSE done]
   기획안 즉시 렌더 (썸네일 자리 = "🎨 이미지 생성 중..." 스켈레톤)
        │  프론트가 thumbnail_prompt를 POST
        ▼
[server.py  POST /api/thumbnail]   ← 키는 서버 환경변수에서만 (브라우저 노출 0)
        │
        ▼ orchestrator.generate_thumbnail(prompt)
[BizRouter  google/gemini-2.5-flash-image]
        │  content 배열에서 data:image/png;base64 추출
        ▼
   {"status":"ok","image":"data:image/png;base64,..."}  |  {"status":"failed"}
        │
        ▼ 프론트: <img src=base64> 교체  |  실패 시 thumbnail_prompt 텍스트 폴백
```

## 컴포넌트 설계

### 1. `orchestrator.py` — `generate_thumbnail(prompt: str) -> str | None`

- 기존 `call()`과 동일한 urllib 패턴. 모델만 `IMAGE_MODEL = "google/gemini-2.5-flash-image"`.
- body: `{"model": IMAGE_MODEL, "messages":[{"role":"user","content": prompt}]}` (response_format 없음 — 이미지 모델은 json_object 미지원).
- 응답 `choices[0].message.content`:
  - **배열인 경우**: 순회하며 `item.get("type")=="image_url"`의 `image_url.url`이 `data:image`로 시작하면 반환.
  - 문자열/이미지 없음 → `None`.
- 환경변수 `THUMBNAIL_IMAGE`가 `"0"`이면 즉시 `None`(생성 안 함).
- `API_KEY` 비어있으면 `None`.
- 예외(HTTP·타임아웃·파싱)는 잡아서 `None` 반환 — **절대 raise 안 함**(기획안 흐름 보호). 타임아웃 90초.
- 토큰/비용 누적: 기존 `token_usage`/`cost_total` 패턴 따름(usage 있으면 누적, 없으면 skip).

### 2. `server.py` — `POST /api/thumbnail`

- `do_POST`에 분기 추가. body: `{"prompt": "..."}`.
- prompt 없거나 1MB 초과 → 400.
- `orchestrator.generate_thumbnail(prompt)` 호출:
  - 반환값 truthy → `{"status":"ok","image": "<data:...>"}`
  - `None` → `{"status":"failed"}` (200으로 — 프론트가 graceful 처리)
- 예외 → `{"status":"failed","error": "..."}` (graceful).
- 동시성: 모델 호출이지만 SSE `/api/pd`의 `_run_lock`과 별개 단발 호출. Gamma `/api/gamma`가 lock 없이 도는 선례를 따라 lock 불필요(레이스는 BizRouter 측 큐). 단 기존 코드의 lock 적용 범위를 확인해 일관되게 처리.

### 3. `web/index.html` — 비동기 썸네일 로딩

- 현재: `renderRichSections`에서 `thumbnail_prompt` 있으면 `#rThumb`에 텍스트 표시.
- 변경:
  - 썸네일 영역에 이미지 컨테이너(`#rThumbImg`) + 스켈레톤 추가.
  - 기획안 렌더 직후 `thumbnail_prompt`가 있으면 `loadThumbnail(prompt)` 호출:
    1. 스켈레톤 "🎨 이미지 생성 중..." 표시
    2. `fetch("/api/thumbnail", {method:"POST", body: JSON.stringify({prompt})})`
    3. `status==="ok"` → `<img src=image>`로 교체(+ 프롬프트는 접어두거나 작게 유지)
    4. `status!=="ok"` 또는 네트워크 실패 → 스켈레톤 제거, 기존 프롬프트 텍스트 표시(현행 폴백)
  - 샘플 폴백(`renderFallbackSamples`)에선 호출 안 함(thumbnail_prompt 없음).
- XSS: base64 `data:` URL은 `<img src>`에만 주입(텍스트 아님). prompt 표시는 기존 `textContent` 유지.

## 에러 처리

- 키 없음 / `THUMBNAIL_IMAGE=0` / 생성 실패 / 타임아웃 → 모두 `status:"failed"` → 프론트가 **프롬프트 텍스트 폴백**. 기획안 표시는 어떤 경우에도 막지 않음.
- 이미지 모델이 텍스트만 반환(이미지 누락) → `None` → 폴백.

## 테스트·검증

1. **단위(로컬)**: `railway run`으로 production 키 주입 → `generate_thumbnail`에 실제 프롬프트 1개 → base64 반환 확인(이미 1차 검증 완료).
2. **폴백**: `THUMBNAIL_IMAGE=0` 또는 키 제거 시 `None` 반환 확인.
3. **회귀**: 기존 `test_orchestrator.py`/`test_server.py` PASS 유지.
4. **배포 후 e2e**: Playwright로 실제 기획 생성 → 썸네일 `<img>` 렌더 시각 검증(스크린샷). 실패 시 프롬프트 텍스트 폴백 확인.

## 범위 밖 (YAGNI — ADR-028 정합)

- 메이커-체커 루프(생성→비평→재생성), 의도 기획기, Pydantic 구조화 출력 — 엔터프라이즈 과설계. 데모는 1콜 생성으로 충분.
- 이미지 저장·재사용·갤러리, 화면비/스타일 사용자 선택 — 현 단계 불필요.
- Google GenAI SDK / Vertex — BizRouter 경유·의존성 0 원칙 위반(임포트 불가).
