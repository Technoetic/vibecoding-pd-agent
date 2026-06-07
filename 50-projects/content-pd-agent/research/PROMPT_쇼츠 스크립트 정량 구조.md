---
type: prompt_template
target: deepresearch
purpose: "쇼츠/틱톡 스크립트의 정량 구조(단어수·해시태그·구간 길이) 1차 출처 조사"
created: 2026-06-07
related_module: "20-knowledge/scripts/쇼츠 스크립트 구조와 길이.md"
related_gap: G5
priority: high
status: answered
deepresearch_input: "PROMPT_쇼츠 스크립트 정량 구조.deepresearch.txt"
answered_by: "숏폼 영상 스크립트 정량 구조 연구.md"
post_traffic: false
title: "딥리서치 프롬프트 — 쇼츠 스크립트 정량 구조"
ai_priority: medium
updated: 2026-06-07
tags:
  - research
  - prompt
related:
  - "[[쇼츠 스크립트 구조와 길이]]"
  - "[[domain-priorities-2026-06-07]]"
---

# 딥리서치 프롬프트 — 쇼츠 스크립트 정량 구조

## 사용법
이 노트는 메타 정보다. **외부 딥리서치 도구(Perplexity/Gemini/ChatGPT/Claude.ai Deep Research)에 넣을 입력본은 페어 파일** `PROMPT_쇼츠 스크립트 정량 구조.deepresearch.txt`를 그대로 복사해 쓴다.

## 결손 영역 (현 상태 vs 결손)
| 항목 | 현 상태 | 결손 |
| :-- | :-- | :-- |
| 스크립트 길이 | `eval_scenarios` 100~250단어(실무 휴리스틱) | 훅·바디·CTA **각 구간 최적 단어수** 미검증 |
| 해시태그 | "과다 태깅 지양"만 | **개수·배치 전략** 최적값 미검증 |
| 첫 3초 훅 | 검증됨(완주율 1순위) | 훅 **이후** 바디의 리텐션 곡선 정량 미검증 |

→ [[쇼츠 스크립트 구조와 길이]]의 "⚠ 미검증" 절을 메우는 조사.

## 채택 절차
딥리서치 결과 수신 후 `/squeeze-report <결과.md>`로 사실성 분리 → ACCEPT 항목만 `20-knowledge/scripts/`·`eval_scenarios.json`에 본문화. 가짜 인용·빈 약속은 거부.

## 면책
직전 딥리서치가 이미 알고리즘 신호·훅 역U자·수익규제는 커버함. 이 프롬프트는 **그때 "thin"으로 남긴 정량 영역만** 조사(중복 회피).
