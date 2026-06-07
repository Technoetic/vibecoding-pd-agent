---
title: "명명·링킹 규칙 스키마"
type: concept
status: active
ai_priority: high
created: 2026-06-07
updated: 2026-06-07
tags:
  - meta
  - schema
related:
  - "[[frontmatter]]"
  - "[[index]]"
---

# 명명·링킹 규칙 스키마

파일명·태그·위키링크 규약을 한곳에 모은다. CLAUDE.md §2(Markdown & Linking)에 산재한 규칙의 단일 참조본 — Dataview 쿼리·`grep` 탐색 일관성을 위해. 프론트매터 필드 규약은 [[frontmatter]] 참조(역할 분리).

## 파일명 규칙

- **자연어 명사형 + 띄어쓰기 허용**: `바이럴 훅 3초 법칙.md`, `양실장 바이브코딩대학 채널 분석.md`.
- **케밥케이스 금지**: `viral-hook-3sec.md` ❌. (단 `.claude/commands/` 슬래시 커맨드는 케밥/영문 — Claude Code 규약이라 예외)
- 확장자 `.md` (딥리서치 입력본만 `.deepresearch.txt`).
- 같은 개념은 한 파일명으로 — 중복 노트 생성 금지(`/lint`로 점검).

## 디렉토리별 배치 (숫자 접두사 = 결정론 경로)

| 경로 | 용도 | 파일명 패턴 |
| :-- | :-- | :-- |
| `20-knowledge/hooks/` | 바이럴 훅 분석 | 개념 명사형 |
| `20-knowledge/scripts/` | 스크립트 구조·성공 대본 | 개념 명사형 |
| `20-knowledge/trends/` | 키워드·시장·채널 분석 | 개념 명사형 |
| `30-journal/` | 기획 일지 | `YYYY-MM-DD.md` (날짜형 예외) |
| `50-projects/content-pd-agent/research/` | 딥리서치 프롬프트 | `PROMPT_<주제>.md` + `.deepresearch.txt` 페어 |
| `50-projects/content-pd-agent/output/` | 승인 기획안 | `CONTENT_2026_NNN.md` (연번) |

`20-knowledge/`는 **평면 유지** — 하위 폴더(hooks/scripts/trends) 외 추가 금지(CLAUDE.md §1).

## 위키링킹 규칙

- **공격적 링킹**: 본문의 주요 개념·채널명·인물·플랫폼·키워드는 반드시 `[[노트 이름]]`으로 감싼다.
- **고아 링크 허용**: 대상 노트가 아직 없어도 `[[새 개념]]` 생성 — 나중에 채울 자리 표시.
- **경로 링크 금지**: `[텍스트](../path.md)` ❌. 오직 `[[노트 이름]]`만.
- 프론트매터 `related`의 위키링크는 **이중 따옴표 필수** → [[frontmatter]] CRITICAL 절.

## 태그 컨벤션

- 하이픈 리스트, 최소 1개(프론트매터 `tags`).
- 도메인 태그: `shorts` `hook` `script` `trend` `channel` `market` `research` `prompt` `meta` `schema`.
- 상태 태그: `검증됨`(외부 출처 교차검증 완료) `승인대기`(eval 통과·인간 승인 전).
- `#fyp`·`#viral` 같은 광범위 태그는 콘텐츠 해시태그에서도 배제([[한국 AI 교육 유튜브 시장 구조]] 해시태그 전략) — 메타 태그와 콘텐츠 해시태그를 혼동하지 말 것.

## 점검

`/lint`로 데드링크·고아노트·프론트매터 누락을 진단. 명명 규칙 위반(케밥케이스·경로링크)도 함께 점검.
