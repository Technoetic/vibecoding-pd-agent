---
title: "YAML 프론트매터 스키마"
type: concept
status: active
ai_priority: high
created: 2026-06-07
updated: 2026-06-07
tags:
  - meta
  - schema
related:
  - "[[index]]"
---

# YAML 프론트매터 스키마

볼트 내 모든 `.md`는 12줄 이내의 프론트매터를 최상단에 둔다. `grep`/Dataview가 본문 전체 스캔 없이 메타데이터만 1차 파싱 → 토큰 대폭 절감.

## 표준 필드

| 필드 | 타입 | 설명 |
| :-- | :-- | :-- |
| `title` | String | 고유 식별 제목. 따옴표로 감싼다. |
| `type` | Enum | `hook` `script` `trend` `concept` `journal` `persona` 중 하나 (필수) |
| `status` | Enum | `draft` `active` `archive` |
| `ai_priority` | Enum | `high` `medium` `low` `archive` (스캔 우선순위) |
| `created` | Date | `YYYY-MM-DD` |
| `updated` | Date | `YYYY-MM-DD` |
| `tags` | Array | 하이픈 리스트, 최소 1개 |
| `related` | Array | 위키링크 배열. **각 항목 이중 따옴표 필수** |

## CRITICAL — 위키링크 충돌 회피

```yaml
# ❌ 금지 — YAML이 중첩 배열로 오인, 파싱 에러
related: [[바이럴 훅 3초 법칙]]

# ✅ 단일 — 이중 따옴표
related: "[[바이럴 훅 3초 법칙]]"

# ✅ 다중 — 하이픈 리스트 + 각 항목 이중 따옴표 (권장)
related:
  - "[[바이럴 훅 3초 법칙]]"
  - "[[양실장 바이브코딩대학 채널 분석]]"
```

인라인 필드(`[key:: value]`)는 본문에 쓰지 않는다. 조회용 메타데이터는 전부 이 프론트매터 블록 안에만 둔다.
