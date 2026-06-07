---
title: "content-pd-agent context"
type: concept
status: active
ai_priority: high
created: 2026-06-07
updated: 2026-06-07
tags:
  - project
  - pd-agent
related:
  - "[[supervisor]]"
  - "[[index]]"
---

# 콘텐츠 PD 에이전트 — 진실의 원천 (Ground Truth)

세션 시작 시 가장 먼저 읽어 전체 맥락을 복원하는 닻(Anchor).

## 목표
양실장의 바이브코딩대학 채널을 위한 **쇼츠/틱톡 기획 자동화 시스템**. `/pd "주제"` 한 줄로 4-에이전트가 협업해 기획서 + 대본을 `output/`에 생산한다.

## 범위
- IN: 트렌드 분석 → 훅 설계 → 스크립트/스토리보드/썸네일 프롬프트 작성 → Eval 검수 → 산출.
- OUT: 실제 영상 편집, 업로드, 광고 집행.

## 이해관계자
- 채널: [[양실장 바이브코딩대학 채널 분석]] (그로스 해커 톤, 수익화 지향)
- 평가자: 채용 담당(AI 콘텐츠 PD 포지션)

## 아키텍처
4-에이전트 오케스트레이션 → [[supervisor]] · [[trend-analyst]] · [[creator]] · [[reviewer]].
상태 = `State.json`, 검수 기준 = `eval_scenarios.json` (둘 다 이 폴더 내 JSON).

## 현재 상태
초기 구축 완료. `/pd` 첫 가동 대기.
