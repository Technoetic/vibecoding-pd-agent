---
description: output 기획안을 eval_scenarios 기준으로 단독 검수한다
argument-hint: "검수할 output 파일명 (예: CONTENT_2026_001)"
---

# /eval — 기획안 단독 검수 (Reviewer)

대상: **$ARGUMENTS**

[[reviewer]] 페르소나로 `50-projects/content-pd-agent/output/$ARGUMENTS` 를 `eval_scenarios.json`의 5개 assert로 검사한다:

1. **length_bounds** — 100~250단어
2. **keyword_inclusion** — 타겟 키워드 80%+ 포함
3. **originality_check** — 기존 스크립트와 유사도 < 0.85
4. **format_compliance** — 제목/본문/해시태그 분리
5. **security_check** — 실제 데이터·이메일 미포함

각 항목 Pass/Fail과 사유를 표로 출력하고, 종합 판정(`approved` / `rejected + 수정요구`)을 내린다. `rejected`면 `feedback_log`에 기록.
