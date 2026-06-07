# /verify — 범용 시각 검증 + 자동 수정 루프

코드를 변경했거나 결과를 확인해야 할 때 실행한다.
**⚠️가 하나라도 있으면 즉시 수정하고 다시 검증. ✅만 남을 때까지 반복.**

**종료 조건: ⚠️가 단 한 건도 없이 전체 ✅가 나온 회차에서만 종료한다.**

---

## 핵심 원칙: 검증 에이전트 ≠ 판정 에이전트

같은 에이전트가 검증하고 스스로 통과 판정하는 것을 **금지**한다. 반드시 독립된 두 서브에이전트를 순차 스폰한다.

---

## 절대 규칙

- **스크린샷을 Read로 직접 보기 전에 "됩니다"라고 절대 말하지 마라.**
- 콘솔 로그, 코드 리뷰, 추측으로 판단하지 마라.
- 안 보이면 "안 보입니다"라고 솔직하게 말하라.
- **⚠️ 발견 → 수정 → 재검증. ✅가 될 때까지 루프.**
- **절대 "직접 봤어?"라는 질문을 받는 상황을 만들지 마라.**
- **SVG/HTML 컨테이너를 벗어난 텍스트는 육안으로 누락되기 쉽다. 반드시 픽셀 단위 자동 점검(3.6단계)을 수행한다.**
- **두 요소가 다 보여도 baseline/bottom이 어긋나면 결함이다. "잘림"(3.6)과 "어긋남"(3.7)은 별개다. 인접 컨트롤 정렬을 픽셀로 점검(3.7단계)한다. 섹션 전체 크롭에서는 10~15px 어긋남이 묻히므로, 의심 영역은 컨트롤 묶음만 좁게 크롭해서 재확인한다.**

---

## 매 회차 실행 절차

현재 몇 번째 검증인지 표시하라.
예: `[시각 검증 1회차]`, `[시각 검증 2회차]`, ...

### Phase 1: 에이전트 A 스폰 (검증 전문)

Agent 도구로 서브에이전트를 스폰한다. 프롬프트:

```
너는 시각 검증 전문 에이전트다. 아래 프로젝트를 Playwright로 검증하고, 결과를 step_archive/시각_검증_결과.md에 저장하라. 최종 판정은 하지 않는다.

[프로젝트 URL 또는 빌드 경로를 여기에 삽입]

## 0단계: 빌드

프로젝트의 빌드 방식을 자동 감지한다:
- `package.json`에 `build` 스크립트 있으면 → `npm run build`
- `build.js`가 있으면 → `node build.js`
- 정적 HTML이면 → 빌드 불필요
빌드 결과를 기록한다. 실패 시 **검증 불가 발생: YES**로 기록한다.

## 1단계: 전체 스크린샷

Playwright로 3개 뷰포트 촬영:
- 모바일 (390x844)
- 태블릿 (768x1024)
- 데스크톱 (1920x1080)

각 뷰포트에서 주요 화면(홈, 핵심 기능 화면, 설정 등)을 캡처한다.
스크린샷은 step_archive/verify_[viewport]_[screen].png에 저장한다.

## 2단계: 영역별 크롭 스크린샷

각 뷰포트에서 주요 영역을 element.screenshot()으로 크롭:
- header
- main (또는 주요 콘텐츠 영역)
- footer (또는 컨트롤 영역)
- 프로젝트 특화 영역 (시각화, 코드 패널 등)
글자가 작아서 안 보이면 더 큰 크롭으로 재촬영한다.

## 3단계: 스크린샷 직접 확인 + 항목별 점검

**전체 + 크롭, 모든 스크린샷을 Read 도구로 열어서 직접 확인한다.** 하나도 빠뜨리지 마라.

각 영역에서 다음을 확인하고 ✅ / ❌ / ⚠️로 표시:

| 항목 | 기준 | 배점 |
|------|------|------|
| 텍스트 가독성 | 잘림·넘침·크기 문제 없는가? | 15점 |
| 레이아웃 정렬 | 그리드·정렬·패딩·마진 정상인가? | 15점 |
| 색상·대비 | 배경 대비 텍스트가 읽히는가? | 10점 |
| 요소 겹침 | 겹치거나 가려지는 요소 없는가? | 15점 |
| 반응형 | 3개 뷰포트 모두에서 정상인가? | 15점 |
| 기능 동작 | 버튼·입력·전환이 의도대로 작동하는가? | 15점 |
| 데이터 표시 | DB 데이터가 정확히 표시되는가? | 15점 |

- "대충 괜찮아 보입니다"는 금지
- 구체적으로 뭐가 보이는지 서술
- ❌ 또는 ⚠️ 항목이 있으면 **검증 불가 발생: YES**로 기록하고, 문제를 구체적으로 설명

## 3.5단계: E2E 인터랙션 테스트

**스크린샷만으로 검증할 수 없는 기능 동작을 Playwright E2E로 직접 테스트한다.**

각 페이지에서 핵심 인터랙션을 실행하고 결과를 검증:

- **버튼 클릭**: `page.click()` 후 DOM 상태 변화 확인 (`page.isVisible()`, `page.textContent()`)
- **폼 입력**: `page.fill()` 후 유효성 검증 상태 확인 (disabled/enabled, error 메시지)
- **페이지 전환**: 버튼 클릭 후 URL 변경 또는 DOM 전환 확인
- **모달/오버레이**: 열기/닫기 동작 확인 (`page.isVisible()`)
- **키보드/터치**: 키 입력, 스와이프 제스처 시뮬레이션

테스트 결과를 ✅ / ❌ 로 기록한다. 실패 시 구체적 오류 메시지 포함.

**E2E 테스트에서 확인한 항목은 "기능 동작" 배점에서 감점 없이 15/15 만점을 줄 수 있다.**
**E2E 테스트를 수행하지 않은 경우, "기능 동작" 항목은 최대 13/15까지만 부여 가능하다.**

## 3.6단계: 텍스트 오버플로 픽셀 단위 자동 점검 (필수)

**육안으로는 박스 1~5px 침범을 놓치기 쉽다. 브라우저 BBox API로 자동 측정하라.**

대상:
- 페이지 내 **모든 SVG**의 `<text>` 노드 (다이어그램, 차트, 라벨 등)
- HTML 컨테이너 중 `overflow: visible`이거나 고정 폭을 가진 박스(`.card`, `.tag`, `.chip`, `.badge` 등)의 텍스트 자식

### SVG 점검 (필수)
페이지에 SVG가 1개 이상 있으면 다음 평가 스크립트를 Playwright `page.evaluate()`로 실행:

```js
(()=>{
  const results = [];
  document.querySelectorAll('svg').forEach((svg, si)=>{
    const rects = [...svg.querySelectorAll('rect')].map(r=>({
      x:+r.getAttribute('x'), y:+r.getAttribute('y'),
      w:+r.getAttribute('width'), h:+r.getAttribute('height')
    }));
    const texts = [...svg.querySelectorAll('text')].map(t=>{
      const b = t.getBBox();
      return {txt:t.textContent.trim(), x:b.x, y:b.y, xR:b.x+b.width, yB:b.y+b.height, fs:t.getAttribute('font-size')};
    });
    const overflows = [];
    texts.forEach(t=>{
      // 어떤 rect가 이 텍스트를 "담으려고 의도된" 박스인지 추정: 텍스트 시작점이 박스 내부
      const owner = rects.find(r=>t.x>=r.x-2 && t.xR<=r.x+r.w+2 && t.y>=r.y-2 && t.yB<=r.y+r.h+2);
      if(!owner){
        const partial = rects.find(r=>t.x>=r.x-2 && t.x<=r.x+r.w+2 && t.y>=r.y-2 && t.yB<=r.y+r.h+2 && t.xR>r.x+r.w+2);
        if(partial) overflows.push({txt:t.txt, fs:t.fs, exceed:Math.round(t.xR-(partial.x+partial.w))});
      }
    });
    results.push({svgIndex:si, totalTexts:texts.length, totalRects:rects.length, overflowCount:overflows.length, overflows});
  });
  return results;
})()
```

결과 처리:
- `overflowCount === 0` → ✅
- `overflowCount > 0` → **각 항목을 ❌로 기록**하고, 텍스트 내용·초과 픽셀·현재 폰트크기를 명시. 보고서에 "SVG 텍스트 오버플로 N건"으로 별도 섹션을 만든다.
- 결과 JSON을 `step_archive/svg_overflow_check.json`에 저장한다.

### HTML 텍스트 오버플로 점검 (보조)
다음 셀렉터 후보를 점검 (페이지에 존재하는 것만):
- `.card, .tag, .chip, .badge, .pill, .label`
- 화이트리스트가 아닌 모든 인라인 박스에서 `scrollWidth > clientWidth + 2`인 요소

```js
[...document.querySelectorAll('.card,.tag,.chip,.badge,.pill,.label,.kchip,.gh,.nh')]
  .filter(e => e.scrollWidth > e.clientWidth + 2)
  .map(e => ({sel:e.className, txt:e.textContent.trim().slice(0,60), scrollW:e.scrollWidth, clientW:e.clientWidth}));
```

결과 1건이라도 있으면 ⚠️ 1건당 -5.

### 채점 반영
- SVG 오버플로 1건당 ❌ (-15점) — 발표/시연용 시각 자산은 박스 침범이 가장 치명적
- HTML 오버플로 1건당 ⚠️ (-5점)
- 텍스트 가독성 항목 점수에 추가 반영

## 3.7단계: 인접 컨트롤 정렬 픽셀 점검 (필수)

**"잘림"이 아니라 "어긋남"은 3.6단계(오버플로)로 못 잡는다. 두 요소가 멀쩡히 보여도 baseline/bottom이 틀어지면 시각 결함이다. 박스 좌표로 자동 측정하라.**

라벨이 위에 얹힌 입력칸(`flex-direction:column`인 `.field` 등)과 그 옆 버튼/슬라이더는, 컨테이너가 `align-items:center`면 라벨 높이만큼 버튼이 떠서 입력칸과 바닥선이 어긋난다(실제 회귀 사례). 이걸 픽셀로 측정한다.

대상: 같은 가로 줄에 놓인 인접 인터랙티브 요소 묶음
- 입력칸(`input`) ↔ 같은 줄의 버튼(`button`, `.btn`)
- 입력칸 ↔ 같은 줄의 슬라이더(`input[type=range]`)·체크박스
- 툴바/컨트롤 바(`.controls`, `.toolbar`, `.actions`, `.field-row` 등) 내부 형제 요소들

각 뷰포트(모바일/태블릿/데스크톱)에서 `page.evaluate()`로 실행:

```js
(()=>{
  const out = [];
  // 컨트롤 컨테이너 후보 — 프로젝트에 존재하는 것만
  const bars = [...document.querySelectorAll('.controls,.toolbar,.actions,.field-row,.control-bar,form')];
  bars.forEach((bar, bi)=>{
    const kids = [...bar.children].filter(e=>{
      const r=e.getBoundingClientRect(); return r.width>0 && r.height>0;
    });
    // 같은 flex 줄끼리 그룹핑(offsetTop이 8px 이내면 같은 줄로 간주)
    const rows = [];
    kids.forEach(e=>{
      const top = e.offsetTop;
      let row = rows.find(r=>Math.abs(r.top-top)<=8);
      if(!row){ row={top, items:[]}; rows.push(row); }
      row.items.push(e);
    });
    rows.forEach((row, ri)=>{
      if(row.items.length<2) return; // 한 줄에 요소 1개면 정렬 비교 대상 아님
      const rects = row.items.map(e=>{
        const b=e.getBoundingClientRect();
        return {tag:e.tagName.toLowerCase(), cls:(e.className||'').toString().slice(0,24), bottom:Math.round(b.bottom), top:Math.round(b.top)};
      });
      const bottoms = rects.map(r=>r.bottom);
      const maxGap = Math.max(...bottoms) - Math.min(...bottoms);
      if(maxGap > 2){ // 같은 줄인데 바닥선이 2px 넘게 어긋나면 결함 후보
        out.push({bar:bi, row:ri, maxBottomGap:maxGap, items:rects});
      }
    });
  });
  return out;
})()
```

결과 처리:
- 결과 0건 → ✅ (모든 같은-줄 인접 컨트롤의 바닥선 일치)
- 결과 N건 → **각 항목을 ⚠️로 기록**하고, 어느 컨테이너/줄에서 어떤 요소들이 몇 px 어긋나는지 명시. "컨트롤 정렬 어긋남 N건" 섹션을 만든다.
- 단, **같은 줄이 아니라 `flex-wrap`으로 다음 줄로 내려간 경우는 정상**(offsetTop이 다르면 위 스크립트가 다른 row로 분리하므로 자동 제외). 의도적으로 baseline을 다르게 둔 디자인(예: `align-items:baseline`로 텍스트 베이스라인 정렬)이면 보고하되 "의도 가능성"을 병기.
- 결과 JSON을 `step_archive/align_check.json`에 저장.

### 채점 반영
- 컨트롤 정렬 어긋남(maxBottomGap>2px) 1건당 ⚠️ (-5점). "레이아웃 정렬" 항목 점수에 반영.
- 3.6(오버플로)과 3.7(정렬)은 별개 결함이다. 둘 다 0건이어야 레이아웃·텍스트 항목이 만점.

### 크롭 보강 (육안 사각지대 방지)
3.7에서 ⚠️가 나온 컨테이너는, 섹션 전체가 아니라 **그 컨트롤 묶음만 좁게 크롭**해서(`bar.screenshot()`) 별도 PNG로 저장하고 Read로 직접 확인하라. 넓은 섹션 크롭에서는 10~15px 어긋남이 묻혀 육안으로 놓치기 쉽다.

## 저장 형식
step_archive/시각_검증_결과.md에 다음을 저장하라:
- 0~3.6단계 전체 결과
- 검증 불가 발생 여부: YES / NO
- **SVG 텍스트 오버플로 카운트(총 SVG 수 / 총 text 수 / 오버플로 수) 명시**
- **HTML 텍스트 오버플로 카운트 명시**
- **컨트롤 정렬 어긋남 카운트(컨테이너/줄별 maxBottomGap, 뷰포트별) 명시**
- 패널티 합계: -X점 (❌ 1건당 -15점, ⚠️ 1건당 -5점)
- .claude/에 파일 생성 금지
```

에이전트 A 완료를 기다린다.

### Phase 2: 에이전트 B 스폰 (판정 전문)

에이전트 A가 완료된 후, Agent 도구로 별도 서브에이전트를 스폰한다. 프롬프트:

```
너는 판정 전문 에이전트다. step_archive/시각_검증_결과.md를 읽고, 에이전트 A가 촬영한 스크린샷을 직접 Read로 열어서 독립 검증한 후 판정하라. 검증 내용을 수정하지 않는다.

## 4단계: 독립 검증

에이전트 A가 저장한 스크린샷 파일을 **직접 Read로 열어서** 확인한다.
에이전트 A의 보고와 실제 스크린샷이 일치하는지 교차 검증한다.
에이전트 A가 놓친 문제가 있으면 추가로 기록한다.

## 4.5단계: E2E 결과 검증

에이전트 A의 E2E 인터랙션 테스트 결과를 확인한다.
- E2E 테스트가 수행되었는가? → 수행되었으면 "기능 동작" 15/15 부여 가능
- E2E 테스트가 미수행이면 → "기능 동작" 최대 13/15
- E2E 테스트에서 실패 항목이 있으면 → 해당 항목 ❌ 처리

## 4.6단계: 오버플로 점검 결과 교차 검증

에이전트 A가 3.6단계를 수행했는지, 보고된 오버플로 카운트가 정확한지 검증한다.

- `step_archive/svg_overflow_check.json`이 존재하는가?
- 페이지에 SVG가 1개 이상 있다면 → 3.6단계 미수행은 **검증 미달**로 처리(최대 -10점)
- 보고된 오버플로 카운트가 0이라면 → 의심되는 박스 1~2개를 페이지 상에서 직접 BBox 측정 재실행해 교차 확인
- 보고된 카운트가 0이 아닌데 메인 보고서가 "정상"이라고 적었다면 → 보고 정확성 ❌

오버플로 1건이라도 미해결이면 **다음 회차 강제**. 100점 종료 불가.

## 4.7단계: 정렬 점검 결과 교차 검증

에이전트 A가 3.7단계를 수행했는지, 보고된 정렬 어긋남 카운트가 정확한지 검증한다.

- `step_archive/align_check.json`이 존재하는가? 없으면 3.7 미수행 → **검증 미달**(최대 -10점).
- 페이지에 입력칸+버튼이 같은 줄에 놓인 컨트롤이 1개 이상 있는데 정렬 점검을 안 했다면 검증 미달.
- 보고된 어긋남이 0건이라면 → 의심 컨테이너 1~2개를 직접 BBox 재측정(같은 줄 형제들의 `getBoundingClientRect().bottom` 비교)해 교차 확인.
- 보고된 어긋남이 0이 아닌데 메인 보고서가 "정렬 정상"이라 적었다면 → 보고 정확성 ❌.
- A가 크롭한 컨트롤 단위 스크린샷이 있으면 직접 Read로 열어, "입력칸 아랫변과 버튼 아랫변이 같은 바닥선인가"를 육안 확인하라. **섹션 전체 크롭만 보고 정렬을 판정하지 마라** — 작은 어긋남은 좁은 크롭에서만 보인다.

정렬 어긋남 1건이라도 미해결이면 **다음 회차 강제**. 100점 종료 불가.

## 5단계: 종합 판정

**종합 점수:** (기본 100점 - 패널티 - 항목별 감점) / 100점

### 이 회차에 ⚠️ 또는 ❌가 한 건이라도 있는가?

**YES → 100점이어도 종료하지 않는다. 즉시 다음 회차 시작을 메인 에이전트에 지시하라.**
- 문제 항목을 구체적으로 나열
- 수정 방향 제안

**NO + 100점 → 진짜 종료.**
- 검증 완료 상태를 한 문장으로 요약
- 3개 뷰포트 모두 정상임을 명시

**NO + 99점 이하 → 예외 없이 다음 회차 시작을 메인 에이전트에 지시하라.**

판정 결과를 출력하라.
```

### Phase 3: 반복 여부 결정

에이전트 B의 판정 결과를 확인한다.
- **⚠️/❌ 발견 또는 100점 미만** → 즉시 코드 수정 후 다음 회차 시작 (빌드부터)
- **전체 ✅ + 100점** → "검증 완료" 보고 후 종료

### 자동 수정 루프

⚠️가 하나라도 있으면:
1. 문제를 구체적으로 설명
2. 즉시 코드 수정
3. Phase 1(빌드)로 돌아가서 재검증
4. 모든 항목 ✅가 될 때까지 반복

**SVG 텍스트 오버플로 수정 가이드 (자주 발생하는 회귀):**
- 박스(`<rect>`)와 텍스트의 폰트크기를 함께 바꾼 경우(폰트만 키우고 박스는 그대로)에 자주 발생
- 해결 우선순위:
  1. **박스 width 확장** — 옆 박스/요소와 충돌하지 않는 한 가장 안전. 인접 좌표 계산 후 충돌 없는 만큼 확장
  2. **연관 edge/화살표 좌표 보정** — 박스가 넓어졌으면 박스 우측에 붙는 path 시작 x도 그만큼 이동
  3. **텍스트 단축** — 박스를 더 키울 수 없는 경우(`luck_cycle` → `luck`처럼 의미 보존)
  4. **폰트 미세 조정** — 1~2px 미세 초과일 때만 최후 수단 (전체 디자인 일관성 깨질 수 있음)
- 수정 후 **반드시 3.6단계 자동 점검을 재실행**해 `overflowCount === 0` 확인

**컨트롤 정렬 어긋남 수정 가이드 (이번 회귀 사례):**
- 라벨이 위에 얹힌 입력칸(`label.field { flex-direction:column }`)과 옆 버튼이 어긋나는 주원인은 컨테이너의 `align-items:center`다 — 라벨+입력칸 묶음 전체의 중앙에 버튼이 맞춰져 입력칸보다 라벨 높이만큼 뜬다.
- 해결: 컨트롤 컨테이너(`.controls` 등)를 **`align-items:flex-end`**로 바꿔 입력칸·버튼·슬라이더의 바닥선을 맞춘다(라벨은 입력칸 위에 그대로 유지).
- 수정 후 **반드시 3.7단계 자동 점검을 재실행**해 모든 같은-줄 쌍의 `maxBottomGap ≤ 2px` 확인.

**탈출 조건:**
- 모두 ✅ + 100점 + **SVG/HTML 오버플로 0건 + 컨트롤 정렬 어긋남 0건** → "검증 완료" 보고 후 종료
- 같은 문제 3회 반복 → 해결 불가 판정, 사용자에게 보고
