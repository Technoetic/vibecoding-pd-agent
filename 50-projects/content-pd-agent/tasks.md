---
title: "content-pd-agent tasks"
type: concept
status: active
ai_priority: high
created: 2026-06-07
updated: 2026-06-07
tags:
  - project
  - kanban
related:
  - "[[content-pd-agent context]]"
  - "[[domain-priorities-2026-06-07]]"
---

# 작업 칸반

우선순위 근거 = [[domain-priorities-2026-06-07]].

## Now
- [ ] (없음 — AI 단독 가능 결손 모두 처리됨)

## Next (조건/데이터 충족 후 — 지금은 검증 불가)
- [ ] **G4** 훅 역U자 한국어 전이 검증 — 한국어 쇼트폼 A/B 데이터 누적 후. (현재 노트에 "미검증·보수 적용" 명시됨)
- [ ] **G5** 스크립트 단어수·해시태그 최적값 — 실제 게시 성과 데이터 후. (노트에 "최적값 미검증" 명시됨)
- [ ] **G2** `20-knowledge/scripts/`에 실제 성공 대본 ingest — 원본 대본 확보 후 `/ingest`.

## 🔵 사용자 결단 영역 (외부 의존 — 착수는 사용자 신호)
- [ ] **G8** 검색 MCP 연동(실시간 트렌드 자동발굴) — MCP 서버 셋업 필요.
- [ ] **G9** 썸네일 프롬프트 → 이미지 생성 API 자동드롭 — 유료 API 키·비용 결단. (BizRouter에 `gemini-2.5-flash-image`·`gemini-3.1-flash-image-preview` 가용 — 키만 있으면 연동 가능)
- [ ] **G10** 승인 기획 → 랜딩페이지 자동배포 — 인프라·배포 결단.

## Blocked
- (없음)

## Done
- [x] **G6 실행** 모델 교체 검증 완료 → **2.5 유지 결정**: 3.1-flash-lite 1회 실증(회귀 9건 PASS·`/pd` 종단 CONTENT_2026_006 승인)했으나 단가 2.85배라 비용 사유로 되돌림. 종료(2026-10-16) 임박 시 `MODEL` 1줄 교체(가용성·절차 실증됨) → [[decisions|ADR-006]] (2026-06-07)
- [x] **G1** originality_check 코사인 유사도 결정론 실구현(difflib, 의존성 0) + 강제 반려 + 회귀 9건 (2026-06-07)
- [x] **G3** 한국 표시광고법·공정위 규제를 수익리스크 노트·eval에 반영(검증됨) (2026-06-07)
- [x] **G6/G7** ADR-006 은퇴일 검증 격상(2026-10-16) + 마이그레이션 절차 확정 (2026-06-07)
- [x] 볼트 골격 + CLAUDE.md + settings.json + 페르소나 4종 + 슬래시 커맨드 5종 + orchestrator + 검증지식 (2026-06-07)
