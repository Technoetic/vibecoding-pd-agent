# 바코 — AI 콘텐츠 PD 에이전트 작업장

양실장의 바이브코딩대학 채널을 위한 **AI 콘텐츠 PD 에이전트**. Obsidian(LLM 위키) × Claude Code(자율 오케스트레이터)로 쇼츠/틱톡 기획을 자동화한다.

## 한 줄 사용법

```
/pd "개발 없이 5일 만에 수익 웹서비스 비법"
```

→ 4-에이전트(Supervisor·Trend Analyst·Creator·Reviewer)가 협업해 기획서+대본을 `50-projects/content-pd-agent/output/`에 생산한다. Eval 루프를 통과한 결과만 산출된다.

## 구조

| 경로 | 역할 |
| :-- | :-- |
| `CLAUDE.md` | 행동 계약서 (볼트 아키텍처·하드룰·오케스트레이션 규칙) |
| `.claude/settings.json` | 권한 티어 (Deny/Ask/Allow) |
| `.claude/commands/` | 슬래시 커맨드 `/pd` `/ingest` `/day` `/eval` `/lint` |
| `00-meta/` | 관제 센터 — `index.md`·`log.md`·`schemas/`·`personas/`(4-에이전트) |
| `10-inbox/` | 트렌드 원시 수집 |
| `20-knowledge/` | **LLM 위키** — `hooks/`·`scripts/`·`trends/` |
| `30-journal/` | 기획 일지 |
| `50-projects/content-pd-agent/` | 에이전트 시스템 본체 (State.json·eval_scenarios.json·output/) |
| `90-assets/` | 미디어 (AI READ 차단) |
| `_가이드/` | 원본 설계 가이드 4종 (READ-ONLY) |

## 설계 근거

`_가이드/`의 4개 보고서를 통합: 엔드게임 디렉토리(그릇) + CLAUDE.md 하드룰(행동 계약) + 멀티 에이전트 오케스트레이션(내용물). 상세 결정은 `50-projects/content-pd-agent/decisions.md` 참조.

## 옵시디언으로 열기

이 폴더를 옵시디언에서 "기존 폴더를 볼트로 열기"로 연다. 새 노트는 `20-knowledge/`에 생성되고, 그래프 뷰에서 `_가이드`·`90-assets`는 자동 제외된다.
