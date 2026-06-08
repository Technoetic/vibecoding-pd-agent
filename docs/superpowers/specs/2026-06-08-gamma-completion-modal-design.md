# Gamma 생성 완료 모달 — 설계

- 작성일: 2026-06-08
- 영역: `50-projects/content-pd-agent/web/index.html` (프론트 단독)

## 문제

Gamma 슬라이드 생성 완료 시 `gammaCompleted()`가 `window.open(pdf, "_blank")`로
**자동 새 탭**을 연다([web/index.html:532]). 이는 사용자 제스처 없는 비동기 호출이라
**팝업 차단기에 막히기 쉽다** → 사용자가 슬라이드 완성을 인지 못 할 수 있다.

## 요구사항 (확정)

- 자동 `window.open` **제거**
- 완료 시 화면 중앙 **모달**: "발표 슬라이드 완성!" + [📥 PDF 열기] + [닫기]
- PDF 열기는 사용자 클릭(제스처) → 팝업 차단 회피

## 동작

- `gammaCompleted(d)`: `window.open` 제거 → `pdf` 있으면 `showGammaModal(pdf)` 호출.
  `#rGamma` 인라인 PDF 링크는 **유지**(모달 닫아도 다시 열 수 있는 안전망).
- PDF 없으면 모달 안 띄움(기존 graceful).
- 모달 닫기 **4경로**: X 버튼 / [닫기] 버튼 / ESC 키 / 배경(overlay) 클릭.
- PDF 열기 버튼: `<a target="_blank" rel="noopener">` (사용자 클릭이라 차단 안 됨).

## 컴포넌트

1. **HTML**: `#gammaModal`(오버레이) > 카드(아이콘·제목·설명·버튼 행·X). 기본 `hidden`.
2. **CSS**: `.modal-overlay`(고정 전면, 반투명 #000, 중앙 정렬, fade-in),
   `.modal-card`(카드), 버튼 스타일 재사용. `prefers-reduced-motion`서 애니메이션 off.
3. **JS**:
   - `showGammaModal(pdf)`: PDF 열기 버튼 href 설정, 오버레이 표시, ESC 리스너 등록, 포커스 이동.
   - `closeGammaModal()`: 숨김, ESC 리스너 해제.
   - 배경 클릭(overlay 자신 클릭 시만)·X·닫기 버튼 → closeGammaModal.

## 검증

- 로컬: 모달 함수 직접 호출 + Playwright로 표시·닫기 4경로·PDF 버튼 href 확인(스크린샷).
- 회귀: 기존 102 PASS 유지(프론트만 변경, 백엔드 비의존).
- 배포 후: production에서 모달 DOM 존재·함수 동작 확인.

## 범위 밖 (YAGNI)

- PDF 미리보기 iframe(Gamma URL iframe 허용 불확실), 링크 복사, 다운로드 진행률.
