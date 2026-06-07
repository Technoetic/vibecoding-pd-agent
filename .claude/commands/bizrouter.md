# /bizrouter — BizRouter API 연결 확인

BizRouter API 키가 살아있고 호출 가능한 상태인지 확인한다.

## 동작

다음 순서로 점검하고 결과를 한 화면에 요약 보고:

### 1단계: 환경변수 확인
```bash
echo "$BIZROUTER_API_KEY" | head -c 16
```
- 비어있으면 → `[!] BIZROUTER_API_KEY 환경변수가 비어있다. export 후 재시도.` 출력 후 즉시 종료
- 키 prefix는 `sk-br-v1-`로 시작해야 함

### 2단계: 인증 + 엔드포인트 확인 (모델 목록 조회)
```bash
curl -s -o /tmp/br_check.json -w "%{http_code}" \
  -H "Authorization: Bearer $BIZROUTER_API_KEY" \
  https://api.bizrouter.ai/v1/models
```

- **200**: 정상. `python -c "import json; d=json.load(open('/tmp/br_check.json')); print(f'모델 수: {len(d[\"models\"])}장')"` 로 모델 수 출력.
- **401**: `인증 실패 — 키가 만료/오타.` 출력 후 종료
- **그 외**: HTTP 코드와 응답 본문 일부(`head -c 300`) 출력

### 3단계: 텍스트 모델 ping (가장 저렴한 호출로 살아있음 확인)
가장 저렴한 모델로 1토큰 정도만 요청해 실제 응답 흐름까지 확인:
```bash
curl -s -X POST https://api.bizrouter.ai/v1/chat/completions \
  -H "Authorization: Bearer $BIZROUTER_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "google/gemini-2.5-flash-lite",
    "messages": [{"role":"user","content":"reply with the single word OK"}],
    "max_tokens": 5
  }' > /tmp/br_ping.json
```

응답에서 다음을 추출:
- `choices[0].message.content` — 모델 답변
- `usage.cost` — 이번 호출 비용 (원)
- `model` — 실제로 라우팅된 모델 ID

### 4단계: 결과 보고 (한 번에)

다음 형식으로 한 번에 보고:
```
✅ BizRouter 연결 정상
  · 키 prefix: sk-br-v1-xxxx…
  · 엔드포인트: https://api.bizrouter.ai/v1 (HTTP 200)
  · 사용 가능 모델: NN개
  · 핑 응답: "OK"  (model=google/gemini-2.5-flash-lite, cost=0.XX원)
```

또는 실패 시:
```
❌ BizRouter 연결 실패
  · 1단계: ...
  · 2단계: HTTP 401 — 키 검증 실패
  · 권장 조치: ...
```

## 절대 규칙
- 키 전체를 화면에 출력 금지 (앞 16자 prefix만 표시)
- `/tmp/br_*.json`은 점검용 임시 파일 — 점검 후 `rm -f /tmp/br_*.json` 로 정리
- 텍스트 ping은 `max_tokens: 5`로 비용 최소화 (1원 미만)
- 이미지 생성은 호출 안 함 (확인용이라 불필요)
- `.claude/` 디렉토리에 어떤 파일도 생성하지 않는다
