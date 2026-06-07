# /gamma — Gamma API로 프레젠테이션 생성

사용자가 프레젠테이션 생성을 요청하면 Gamma API를 통해 자동 생성한다.

## 사용법

```
/gamma [주제 또는 내용]
```

예시:
- `/gamma 마케팅 전략 2026`
- `/gamma 딥러닝 기초 입문자용 10장`
- `/gamma AI 트렌드 발표자료, 전문가 대상, 20장`

---

## 실행 흐름

### 1. API 키 확인

환경변수 `GAMMA_API_KEY` 또는 사용자에게 요청:

```bash
echo $GAMMA_API_KEY
```

키가 없으면 사용자에게 요청:
> Gamma API 키가 필요합니다. [developers.gamma.app](https://developers.gamma.app/) 에서 발급 후 알려주세요.

---

### 2. 요청 파라미터 구성

사용자 입력을 분석해 아래 파라미터를 자동 추론한다:

| 파라미터 | 기본값 | 자동 추론 예시 |
|---------|--------|--------------|
| `format` | `presentation` | 고정 |
| `numCards` | `10` | "20장" → 20 |
| `textOptions.language` | `korean` | 고정 |
| `textOptions.tone` | `professional` | "입문자용" → `casual` |
| `textOptions.audience` | `general` | "전문가" → `expert` |
| `textOptions.amount` | `medium` | 슬라이드 수에 따라 조정 |
| `cardOptions.dimensions` | `16x9` | 고정 |
| `imageOptions.source` | `aiGenerated` | 고정 |

---

### 3. API 호출 (생성 요청)

```bash
curl -s -X POST https://public-api.gamma.app/v1.0/generations \
  -H "Content-Type: application/json" \
  -H "X-API-KEY: $GAMMA_API_KEY" \
  -d '{
    "inputText": "<사용자 입력>",
    "format": "presentation",
    "textMode": "generate",
    "numCards": <numCards>,
    "cardOptions": { "dimensions": "16x9" },
    "textOptions": {
      "amount": "medium",
      "tone": "<tone>",
      "audience": "<audience>",
      "language": "ko"
    },
    "imageOptions": {
      "source": "aiGenerated"
    }
  }'
```

응답에서 `generationId` 추출 후 저장.

---

### 4. 상태 폴링 (완료 대기)

5초 간격으로 최대 12회 (1분) 폴링:

```bash
curl -s https://public-api.gamma.app/v1.0/generations/<generationId> \
  -H "X-API-KEY: $GAMMA_API_KEY"
```

- `status: "completed"` → 결과 출력
- `status: "failed"` → 오류 메시지 출력
- 1분 초과 → 타임아웃 안내

---

### 5. 결과 출력

```
✅ 프레젠테이션 생성 완료!

📊 제목: <inputText 요약>
🔗 Gamma에서 보기: <gammaUrl>
📥 내보내기 URL: <exportUrl>

슬라이드 수: <numCards>장 | 형식: 16:9
```

---

## 전체 Bash 스크립트 (인라인 실행)

```bash
GAMMA_API_KEY="${GAMMA_API_KEY:-}"
INPUT_TEXT="$1"
NUM_CARDS="${2:-10}"
TONE="${3:-professional}"
AUDIENCE="${4:-general}"

if [ -z "$GAMMA_API_KEY" ]; then
  echo "❌ GAMMA_API_KEY 환경변수가 설정되지 않았습니다."
  exit 1
fi

# 생성 요청
RESPONSE=$(curl -s -X POST https://public-api.gamma.app/v1.0/generations \
  -H "Content-Type: application/json" \
  -H "X-API-KEY: $GAMMA_API_KEY" \
  -d "{
    \"inputText\": \"$INPUT_TEXT\",
    \"format\": \"presentation\",
    \"textMode\": \"generate\",
    \"numCards\": $NUM_CARDS,
    \"cardOptions\": { \"dimensions\": \"16x9\" },
    \"textOptions\": {
      \"amount\": \"medium\",
      \"tone\": \"$TONE\",
      \"audience\": \"$AUDIENCE\",
      \"language\": \"korean\"
    },
    \"imageOptions\": { \"source\": \"aiGenerated\" }
  }")

GENERATION_ID=$(echo "$RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin).get('generationId',''))")

if [ -z "$GENERATION_ID" ]; then
  echo "❌ 생성 요청 실패: $RESPONSE"
  exit 1
fi

echo "⏳ 생성 중... (ID: $GENERATION_ID)"

# 폴링
for i in $(seq 1 12); do
  sleep 5
  STATUS_RESPONSE=$(curl -s "https://public-api.gamma.app/v1.0/generations/$GENERATION_ID" \
    -H "X-API-KEY: $GAMMA_API_KEY")

  STATUS=$(echo "$STATUS_RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin).get('status',''))")

  if [ "$STATUS" = "completed" ]; then
    GAMMA_URL=$(echo "$STATUS_RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin).get('gammaUrl',''))")
    EXPORT_URL=$(echo "$STATUS_RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin).get('exportUrl',''))")
    echo ""
    echo "✅ 프레젠테이션 생성 완료!"
    echo "🔗 Gamma에서 보기: $GAMMA_URL"
    echo "📥 내보내기 URL: $EXPORT_URL"
    exit 0
  elif [ "$STATUS" = "failed" ]; then
    echo "❌ 생성 실패: $STATUS_RESPONSE"
    exit 1
  fi

  echo "  대기 중... ($((i*5))초 경과)"
done

echo "⚠️ 타임아웃: 1분 초과. generationId=$GENERATION_ID 로 나중에 상태 확인 가능."
```

---

## 주의사항

- **Pro 이상 플랜** 필수 (API 키 발급 조건)
- API 키는 [developers.gamma.app](https://developers.gamma.app/) > Account Settings > API Keys에서 발급
- `numCards` 범위: 1–60 (Ultra 플랜은 75까지)
- 생성 소요 시간: 보통 20–60초
- 한국어 결과물은 `textOptions.language: "korean"` 으로 보장
