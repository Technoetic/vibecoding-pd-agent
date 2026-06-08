# 썸네일 한글 금지 — 영문 프롬프트 강제 (G9 보강)

- 작성일: 2026-06-08
- 영역: `50-projects/content-pd-agent`
- 문제: 나노바나나(`google/gemini-2.5-flash-image`)가 이미지 내 한글 텍스트를 깨뜨림.
  실측: 프롬프트 `"코딩 없이 5일 만에 수익"` → 생성 이미지 텍스트 `"코긴엉 옆지 5일 만데 유익"`.

## 원인

Creator 에이전트가 한국어 채널이라 `thumbnail_prompt`를 **한국어로 생성**한다([orchestrator.py:1055](../../50-projects/content-pd-agent/orchestrator.py)).
그 안의 한글 텍스트 오버레이 지시를 이미지 모델이 한글로 그리려다 깨진다.

## 요구사항 (확정)

- `thumbnail_prompt`를 **영문으로 생성**
- 이미지 내 텍스트 오버레이는 **영문만 허용** (한글 금지)
- 한글이 새어들어도 이미지에는 한글이 안 그려지도록 **결정론 보장**

## 2단 방어 (결정론 + LLM 분리 철학)

LLM 지시만으로는 0% 보장 불가 — 코드 게이트가 최종 차단선.

### 1단 — 생성 지시 (LLM, `agent_creator` 시스템 프롬프트)
`thumbnail_prompt` 출력 지시를 영문 강제로 변경:
> "thumbnail_prompt: 반드시 영어로. 이미지에 넣을 텍스트(오버레이)도 영어만. 한글 텍스트 절대 금지 — 이미지 모델이 한글을 깨뜨림."

### 2단 — 결정론 게이트 (`generate_thumbnail`, BizRouter 전송 직전)
- 프롬프트에 한글(`[가-힣]`) 포함 여부를 정규식으로 검사.
- **거부하지 않는다** — 한글이 있으면 이미지가 안 나와 UX 후퇴.
- 대신 프롬프트 앞에 영문 강제 지시를 prepend:
  > "Render ALL text in the image in English only. Do NOT render any Korean/Hangul characters. If the description contains Korean text overlays, translate them to short English or omit text entirely."
- 한글 유무와 무관하게 이 지시를 항상 prepend(단순·견고). 한글이 없어도 무해(영문 텍스트 강제는 항상 옳음).

### 왜 강제 지시 주입인가 (거부 아님)
거부 시 썸네일 미생성 → UX 후퇴. 지시 주입은 한글이 들어와도 이미지엔 한글이 안 그려지도록 유도하면서 이미지 생성은 유지.

## 컴포넌트

1. `orchestrator.py`
   - `_THUMB_EN_DIRECTIVE` 상수: 영문 강제 지시문(영문).
   - `agent_creator` 시스템 프롬프트: thumbnail_prompt 영문 지시 1줄 추가.
   - `generate_thumbnail`: prompt 앞에 `_THUMB_EN_DIRECTIVE` prepend 후 전송.

2. (server.py·web 변경 없음 — 프롬프트 가공은 orchestrator 내부)

## 검증

1. **단위**: `generate_thumbnail`이 한글 포함 프롬프트에 영문 지시를 prepend하는지(전송 body 검사, mock).
2. **e2e 실측 (핵심)**: 한글 섞인 프롬프트로 실제 생성 → 이미지에 **한글 텍스트가 없거나 영문**인지 스크린샷 직접 확인. 0% 보장 입증.
3. **회귀**: 기존 테스트 PASS 유지.

## 범위 밖 (YAGNI)

- 프롬프트 전체 영문 번역 LLM 콜(지연·비용↑) — 강제 지시로 충분.
- OCR 한글 검출 후 재생성 루프 — 과설계.
- 한글 발견 시 생성 거부 — UX 후퇴.
