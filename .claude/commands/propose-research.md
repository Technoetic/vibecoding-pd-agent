---
description: 콘텐츠 PD 시스템 결손 영역 점검 + 딥리서치 프롬프트 제안 + md 영속화 (squeeze-report 후속 패턴)
argument-hint: (인자 없음 — 자동 시스템 결손 점검)
---

# /propose-research — 딥리서치 프롬프트 제안 + md 정리 자동화 (바코 범용판)

본 명령어는 `/squeeze-report` 후 반복되는 **"딥리서치로 조사할 것 프롬프트
제안해 + md도 정리해"** 패턴을 단일 명령어로 추상화한 것. 이 볼트(AI 콘텐츠
PD 에이전트)의 결손 영역을 점검하고, 외부 딥리서치 도구에 의뢰할 프롬프트
페어를 생성·영속화한다.

## 사용법

```
/propose-research
```

인자 없음. 시스템 결손 영역 자동 점검 + 신규 프롬프트 후보 추출 + 영속화 + 커밋.

## 행동 원칙 — Phase A 창의 단독 + Phase B 검증 분리

**창의 작업(결손 발굴·신규 작성)**과 **사실 검증(경로 실존·중복 검사·삭제 정합성)**은
위험 성격이 다르다. 단계별로 분리해 한 에이전트가 "발굴하며 동시에 채택을
합리화"하는 자기기만을 차단한다.

| Phase | 모델 | 역할 | 권한 |
|:---|:---|:---|:---|
| **A (창의)** | 메인(세션 모델) | 결손 발굴·신규 PROMPT 초안·기존 PROMPT 정정 후보 식별 | 본문화·삭제 권한 없음 (초안만) |
| **B (검증)** | **haiku 서브에이전트** | Phase A 산출물 사실 검증 — 경로 실존·기존 PROMPT 중복·삭제 후보 모듈 풀 직접 확인·CLAUDE.md/ADR 정합 | 신규 후보 발굴 금지 |
| **C (본문화)** | 메인(세션 모델) | Phase B 통과 산출물만 research/ 작성·rm·commit | 검증 우회 금지 |

이유:
- 결손 발굴은 시스템 전체 구조 이해 + 창의적 추론 필요 → Phase A는 메인 단독
- "잘못 추정 프롬프트 제거"(단계 6)와 "신규 결손 추출"(단계 1)은 **같은 추정 편향이 양방향 작동**할 위험 → Phase B 독립 haiku로 차단
- 결손 오추정(예: 이미 충실한 지식노트를 "미작성"으로 오인) 패턴을 Phase B 결정론 검증(Glob+wc+grep)으로 회수

## 행동 절차

### 단계 0 — 시스템 결손 영역 자동 점검

#### 0a. 명시적 미검증·결손 마커 검색
```bash
# 지식노트·코드의 미검증/결손/TODO 마커
grep -rE "미검증|결손|TODO|open question|placeholder|단정 금지|추후" 20-knowledge/ 50-projects/content-pd-agent/ --include="*.md" --include="*.py"
```

#### 0b. 직전 squeeze-report / domain-priorities DEFER 영역 확인
```bash
# decisions.md의 ADR DEFER 절 + domain-priorities 매트릭스 조건/데이터 의존 항목
grep -nE "DEFER|운영 데이터 후|조건 의존|미검증|post_traffic" 50-projects/content-pd-agent/decisions.md 50-projects/content-pd-agent/domain-priorities-*.md
```

#### 0c. 결손 vs 충실 구조 비교 (실 파일 확인 의무)
- `20-knowledge/hooks/` 풀 (바이럴 훅 분석)
- `20-knowledge/scripts/` 풀 (스크립트 구조·성공 대본)
- `20-knowledge/trends/` 풀 (키워드·시장·채널 분석)
- `50-projects/content-pd-agent/eval_scenarios.json` (검수 메트릭 N종)
- `00-meta/personas/` (4-에이전트 정의)

#### 0d. 기존 PROMPT 풀 중복 검사
```bash
ls "50-projects/content-pd-agent/research/"PROMPT_*.md
```
각 PROMPT frontmatter `purpose` + `related_module`·`related_gap` 읽어 **신규 후보가 기존과 중복되지 않는지 검증 의무**.

### 단계 1 — [Phase A 창의 / 메인 단독] 결손 영역 후보 추출

> 메인 단독 실행. 본문화 권한 없음 — **초안만**.

시스템 정체성 (CLAUDE.md):
- 양실장 바이브코딩대학 채널용 AI 콘텐츠 PD 에이전트 (쇼츠/틱톡 기획)
- 4-에이전트 오케스트레이션 (Supervisor·Trend Analyst·Creator·Reviewer)
- eval 12종 검수 게이트 (길이·키워드·독창성·채널중복·양식·보안·수익규제·훅·완주율·음절·해시태그·팩트체크)
- 결정론 측정 + LLM 작문 분리 정책 (originality·channel_dup·음절·해시태그·팩트체크는 코드 실측)
- BizRouter × gemini-2.5-flash-lite 단일모델 + Perplexity Sonar 실시간 트렌드

후보 추출 기준 (우선순위 순):
1. **지식노트 "⚠ 미검증" 절 직격**: `20-knowledge/`에 "단정 금지·미검증"으로 남긴 open question
2. **squeeze-report/domain-priorities DEFER 영역**: 운영 데이터·외부 출처 부재로 보류된 영역
3. **결정론 측정 결손**: LLM 판정에만 의존하는 eval 메트릭에 코드 실측 부재
4. **콘텐츠 도메인 결손**: 훅·스크립트·트렌드·채널분석 중 지식이 얕은 도메인
5. **사실성 검증 영역(ADR-010)**: 가짜 인용·과장 가능성 높은 인용 영역
6. **운영 데이터 의존 영역**: 게시 성과·A/B 데이터 누적 후 검증 가능한 영역

### 단계 2 — [Phase A / 메인] 기존 PROMPT 풀 중복 검사 (1차 자가점검)

각 신규 후보에 대해:
1. `research/PROMPT_*.md` frontmatter 확인 (1차)
2. 명백한 중복: 신규 후보 **초안에서 제외**
3. 새 영역: 신규 PROMPT 초안 작성 (단계 3)

### 단계 3 — [Phase A / 메인] 신규 PROMPT **2종 페어** 작성 (★)

> 후보별로 **반드시 2개 파일을 페어로 작성**. 메타 노트와 딥리서치 입력본을 분리해야 사용자가 입력본을 그대로 복사·붙여넣기로 외부 딥리서치 도구에 의뢰할 수 있다.

#### 3a. 메타 노트 (`50-projects/content-pd-agent/research/PROMPT_<주제>.md`)

이 볼트 컨텍스트·채택 절차·면책을 담은 노트. CLAUDE.md §3 프론트매터 규약 준수:

```yaml
---
type: prompt_template
target: deepresearch
purpose: "<한 줄 설명>"
created: <YYYY-MM-DD>
updated: <YYYY-MM-DD>
related_module: "<20-knowledge/... 또는 eval_scenarios.json 경로>"
related_gap: <G번호 또는 결손 ID>
priority: high | medium | low
status: draft
related_report: "<관련 보고서명>"   # 있을 시
deepresearch_input: "PROMPT_<주제>.deepresearch.txt"  # ★ 페어 입력본
post_traffic: true | false   # 운영 데이터 의존 여부
ai_priority: high | medium | low
tags:
  - research
  - prompt
related:
  - "[[관련 지식노트]]"
---
```

본문 구조:
1. **사용법**: 결손 영역 명시 + "딥리서치 입력본은 페어 .deepresearch.txt 참조"
2. **결손 영역 표**: 현재 상태 vs 결손
3. **채택 절차**: 딥리서치 결과 수신 후 `/squeeze-report`로 사실성 분리 → ACCEPT만 본문화
4. **면책**: CLAUDE.md 컴플라이언스(수익 단정 금지·가짜 인용 금지) 정합 의무

> 메타 노트에는 딥리서치 의뢰 본문을 **포함하지 않는다**(DRY). 입력본은 3b의 별도 파일에만.

#### 3b. 딥리서치 직접 입력본 (`research/PROMPT_<주제>.deepresearch.txt`)

외부 딥리서치 도구(Perplexity/Gemini/ChatGPT/Claude.ai Deep Research)에 **그대로 복사·붙여넣기**할 순수 입력본. **4가지 의무:**

1. **YAML frontmatter 금지** — 일반 텍스트만
2. 마크다운 표·번호 목록 허용
3. **이 프로젝트 식별자 누설 금지** — 외부 일반화 의무
   - ❌ `바코`, `content-pd-agent`, `50-projects/`, `20-knowledge/`, `eval_scenarios`, `BizRouter`, `gemini`, `Sonar`, `양실장`, `VibecodingUniversity`, `CLAUDE.md`, `/squeeze-report`, `/propose-research`, `ADR-\d+`, `State.json` 등
   - ✅ "한국 비개발자/바이브코딩 유튜브", "쇼츠 기획 시스템", "4-에이전트 오케스트레이션" 같은 일반 추상
4. **자족적(self-contained)** — 외부 에이전트가 이 프로젝트를 몰라도 의뢰만 보고 조사 가능

본문 구조 (의뢰서 표준):
1. 한 줄 목적 진술 ("...를 조사하라")
2. 배경·환경 컨텍스트 (외부 일반화)
3. 요구사항 (번호 매김, 각 항목 "반드시 출처와 함께 답할 것")
4. 출력 형식 (마크다운 표 또는 항목 스켈레톤)
5. 검증 기준 (출처 URL 의무·교차검증 2곳·가짜 인용 금지·자기신고 수치는 "추정" 분류)

#### 3c. 검증 자기점검 (Phase B 위임 전 1차)
- 입력본에 이 프로젝트 식별자 누설 없는지 (grep: `바코|content-pd-agent|20-knowledge|eval_scenarios|BizRouter|gemini|Sonar|양실장|VibecodingUniversity|CLAUDE\.md|/squeeze-report|/propose-research|ADR-[0-9]+|State\.json`)
- 입력본에 YAML frontmatter 없는지
- 메타 노트가 입력본을 본문에 중복 포함하지 않는지 (DRY)

### 단계 4 — [Phase A / 메인] 기존 PROMPT 정정 후보 식별

> **정정 후보 목록만 작성**. 실제 정정은 Phase B 통과 후 Phase C에서.

실 구현 재점검에서 이전 추정 오류 발견 시 정정 후보 표시:
- frontmatter `related_module`·`related_gap` 정정 필요
- 본문 결손 영역 명세 정정 필요
- 다른 PROMPT가 기존 모듈/노트를 잘못 추정한 경우

---

### 단계 4.5 — [Phase B 검증 / haiku 서브에이전트] 사실 검증 분리 호출

> **Phase B 핵심 게이트.** Phase A 산출물(메타 노트 + 입력본 페어)을 별도 haiku로 독립 검증.

입력본 페어 의무 점검:
- 각 PROMPT가 `.md` + `.deepresearch.txt` 페어인가? (둘 중 하나 부재 시 REJECT)
- `.deepresearch.txt`에 프로젝트 식별자 누설 없는가? (위 grep 패턴)
- `.deepresearch.txt`에 YAML frontmatter 없는가?
- 자족적인가?

Agent dispatch 시 `model: "haiku"` 명시. 검증 에이전트 프롬프트:

```
당신은 검증 에이전트입니다. Phase A 산출물(신규 PROMPT 초안 N건 + 정정 후보 M건 + 삭제 후보 K건)을 독립 검증만 합니다. 신규 후보 발굴·창작·본문화 권한 없습니다.

작업 디렉토리: c:\Users\Admin\Desktop\바코

Phase A 산출물:
- 신규 PROMPT 초안: <목록>
- 정정 후보: <목록>
- 삭제 후보: <목록>

### 검증 의무 (항목별)

1. **경로 실존 검증** (결정론):
   - 모든 related_module 경로(20-knowledge/... 또는 eval_scenarios.json)를 Glob/Read로 직접 확인
   - 존재하지 않으면 REJECT, 존재하나 빈 placeholder면 LOW_CONFIDENCE

2. **결손 실재 확인** (오추정 차단 의무):
   - 20-knowledge/hooks·scripts·trends 풀 + eval_scenarios.json을 Glob + wc -l + Read
   - "결손" 주장 후보의 해당 노트/메트릭 실측 — 이미 충실(검증된 사실 다수)하면 REJECT, 비었거나 "미검증" 명시면 ACCEPT
   - 삭제 후보도 같은 기준으로 "정말 결손 아님"인지 재검증

3. **기존 PROMPT 풀 중복 정밀 대조**:
   - research/PROMPT_*.md frontmatter purpose + related_module + related_gap 추출
   - 신규 후보와 동일 결손/모듈 명시 여부 점검, 중복이면 REJECT(또는 기존 보강 권고)

4. **CLAUDE.md/ADR 정합 점검**:
   - 컴플라이언스: 수익 보장·과장 단정 유도 여부(FTC·한국 표시광고법)
   - 사실성(ADR-010): 빈 약속·가짜 인용 가능성
   - 결정론 분리: LLM 추측을 결정론 측정으로 오인 유도 여부
   - 입력본 외부 일반화: 프로젝트 식별자 누설(위 grep)

5. **자기 합리화 차단** (★):
   - 삭제 후보 K건이 Phase A 신규 N건과 의도적 충돌(자기 신규 정당화 위해 기존 삭제)인지
   - 신규-삭제 페어 매칭 후 의심 패턴 REJECT

### 출력 (YAML)
verdicts:
  new_prompts:
    - id: "N1"
      verdict: "ACCEPT|REJECT|LOW_CONFIDENCE"
      module_exists: true|false
      note_pool_state: "<실측 — 충실/미검증/부재>"
      duplicate_of: null | "PROMPT_X.md"
      compliance: {사실성: OK, 식별자누설: OK, 컴플라이언스: OK}
      rationale: "..."
  corrections: [{id, verdict, ...}]
  deletions: [{id, verdict, note_pool_actual_state, self_rationalization_risk: LOW|HIGH, ...}]
summary: {new_accepted, new_rejected, corrections_accepted, deletions_accepted, deletions_rejected_for_self_rationalization, should_proceed}

금지: 신규 후보 발굴·창작·본문화·rm 실행.
```

검증 결과를 사용자에게 보고(이 볼트는 reports/ 관행 없음 — 보고만, 영구기록은 decisions.md ADR로).

### 단계 4.6 — [Phase C 본문화 / 메인] Phase B 결과 수용

Phase B 통과 항목만:
- ACCEPT 신규: `research/PROMPT_*.md` + `.deepresearch.txt` **페어 모두 작성**
- ACCEPT 정정: 기존 PROMPT 정정
- ACCEPT 삭제: rm (페어 두 파일)
- REJECT 삭제(자기 합리화 의심): **삭제 보류** + 사유를 decisions.md ADR에 영속 기록
- LOW_CONFIDENCE: 보고서에 🟡 검증 보류로 표시(본문화 보류)
- 식별자 누설 발견: 입력본만 재작성(메타 노트는 프로젝트 컨텍스트 보존)

### 단계 5 — [Phase C / 메인] 인덱스·로그 갱신

- `00-meta/index.md`에 신규 PROMPT 등록(관행 있을 시)
- `00-meta/log.md` 최상단에 작업 요약 1줄

### 단계 6 — [Phase C / 메인] 삭제 실행 (Phase B 통과분만)

> ★ **자기 합리화 차단 게이트.** Phase B에서 `self_rationalization_risk: LOW` 판정한 삭제 후보만 rm.
```bash
rm "50-projects/content-pd-agent/research/PROMPT_<Phase B ACCEPT 후보>.md" "...deepresearch.txt"
```
REJECT 삭제 후보는 보류 + decisions.md에 의심 사유 영속 기록(다음 호출 시 재추출 방지).

### 단계 7 — [Phase C / 메인] 커밋

> **이 볼트는 git으로 추적된다.** 산출물(`research/PROMPT_*` 페어 + 인덱스·로그)을 정상 커밋한다. `.claude/` 디렉토리 규칙 준수(commands/ 외 파일 생성 금지).

```bash
git add "50-projects/content-pd-agent/research/" 00-meta/index.md 00-meta/log.md
git commit -m "docs(바코): /propose-research 딥리서치 프롬프트 <주제> 추가 — <결손>"
```
push는 사용자 승인 또는 명백한 의도가 있을 때만.

### 단계 8 — 사용자 보고 형식

```
## /propose-research 결과

### 시스템 결손 영역 재점검
| 도메인 | 이전 추정 | 실제 상태(실측) | 결정 |
|---|---|---|---|

### 신규 프롬프트 N건 (페어 2종)
| 도메인 | 우선도 | 항목 | 메타 노트 | 딥리서치 입력본 |
|---|---|---|---|---|
| 훅/스크립트/트렌드/채널 | ... | ... | `PROMPT_<주제>.md` | `PROMPT_<주제>.deepresearch.txt` |

### Phase B 검증 verdicts
- ACCEPT N / REJECT K / LOW_CONFIDENCE L (haiku 인용)

### 커밋
- <해시>: docs(바코) ...

### 추천 우선순위
| 순위 | 항목 | 사유 |
```

## 안전장치

### 결손 영역 오추론 방지
실 파일 미확인 추정 금지. 모든 신규 후보에 대해 `20-knowledge/` 해당 노트 + `eval_scenarios.json`을 Read·Grep·wc로 직접 확인. "미검증" 명시 영역과 "이미 검증된 사실" 영역을 구분.

### 중복 PROMPT 방지
신규 작성 전 기존 `research/PROMPT_*.md` frontmatter 의무 확인. 중복이면 기존 보강이 신규 작성보다 우선.

### 사용자 결정 영역 명시
🔵 사업 단계(UI·가격·결제·마케팅·배포 결단)나 명시적 Human Input 대기는 별도 프롬프트로 작성하지 않음(보고서에만 언급).

## 출력 원칙
- 결손 발굴(Phase A) — **창의적 추론** 메인 단독
- 사실 검증(Phase B) — **자기 합리화 차단** haiku 서브에이전트 분리 (★)
- 본문화(Phase C) — **결정론 절차** 메인이 Phase B 통과분만 적용
- 사용자 보고는 **검증 가능 형식** — 표 + 파일 경로 + Phase B verdicts 인용

## 주의 (불변 원칙)
- 본 명령어는 `/squeeze-report` 후속에 자주 호출 — DEFER 영역 우선 점검
- 결손 0건이면 정직히 "현 결손 0건" 보고 + 신규 프롬프트 X
- 모든 PROMPT는 CLAUDE.md 컴플라이언스(수익 단정 금지·가짜 인용 금지·결정론 분리) 정합 의무 명시
- **Phase B 우회 금지** — Phase A 단독 신규 작성·삭제 직접 실행 금지. 모든 본문화는 Phase B 통과 의무
- Phase B 검증 비용 — haiku 1회(~$0.005). 자기 합리화로 잘못 작성/삭제 시 회수 비용보다 저렴
- **★ 페어 작성 의무**: 메타 노트(.md) + 딥리서치 입력본(.deepresearch.txt) 2종. 메타만 작성하면 사용자가 의뢰 텍스트를 수동 추출해야 하는 결함
- **★ 입력본 외부 일반화 의무**: .deepresearch.txt에 이 프로젝트 식별자(파일 경로·채널명·CLAUDE.md 규칙·스킬명) 누설 금지. 외부 딥리서치 에이전트가 이 프로젝트를 몰라도 의뢰만으로 조사 가능해야 함
