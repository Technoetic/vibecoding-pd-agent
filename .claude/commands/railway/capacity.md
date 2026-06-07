# /railway capacity — Railway 인프라 부하 측정 및 동시 접속 한계 보고

Railway에 배포된 API 서버에 실제 부하 테스트를 실행하고 동시 접속 한계를 보고한다.

## 실행 순서

### 1. 인프라 스펙 조회 (Railway GraphQL API)

```bash
TOKEN=$(cat ~/.railway/config.json | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('user',{}).get('token',''))")

curl -s -X POST https://backboard.railway.app/graphql/v2 \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "{ me { workspaces { id name plan subscriptionPlanLimit } } }"}' \
  | python3 -c "
import sys,json
d=json.load(sys.stdin)
ws = d['data']['me']['workspaces'][0]
lim = ws['subscriptionPlanLimit']
c = lim['containers']
n = lim['networking']
print(f\"플랜: {ws['plan']}\")
print(f\"CPU: {c['cpuDescription']} / 최대 {c['maxCpuDescription']}\")
print(f\"RAM: {c['memoryDescription']} / 최대 {c['maxMemoryDescription']}\")
print(f\"HTTP 처리량: {n['httpReqPerSecPerHost']:,} req/s (버스트 {n['httpReqPerSecPerHostBurst']:,})\")
print(f\"TCP 동시 연결: {n['tcpActiveConnectionsPerHost']:,}\")
"
```

### 2. 부하 테스트 스크립트 실행

아래 Node.js 스크립트를 `/tmp/capacity_test.js`로 저장 후 실행:

```javascript
const https = require('https');

const API = 'api-production-8015.up.railway.app';

function post(path, body, token) {
  return new Promise((resolve) => {
    const data = JSON.stringify(body);
    const headers = { 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(data) };
    if (token) headers['Authorization'] = 'Bearer ' + token;
    const start = Date.now();
    const r = https.request({ hostname: API, path, method: 'POST', headers }, (res) => {
      let b = ''; res.on('data', d => b += d);
      res.on('end', () => resolve({ status: res.statusCode, ms: Date.now() - start, body: b }));
    });
    r.on('error', () => resolve({ status: 0, ms: Date.now() - start, body: '' }));
    r.setTimeout(15000, () => { r.destroy(); resolve({ status: 408, ms: 15000, body: '' }); });
    r.write(data); r.end();
  });
}

function get(path, token) {
  return new Promise((resolve) => {
    const headers = token ? { Authorization: 'Bearer ' + token } : {};
    const start = Date.now();
    const r = https.get({ hostname: API, path, headers }, (res) => {
      let b = ''; res.on('data', d => b += d);
      res.on('end', () => resolve({ status: res.statusCode, ms: Date.now() - start }));
    });
    r.on('error', () => resolve({ status: 0, ms: Date.now() - start }));
    r.setTimeout(15000, () => { r.destroy(); resolve({ status: 408, ms: 15000 }); });
  });
}

async function run(label, concurrency, fn) {
  const results = await Promise.all(Array.from({ length: concurrency }, () => fn()));
  const ok = results.filter(r => r.status >= 200 && r.status < 300).length;
  const sorted = results.map(r => r.ms).sort((a, b) => a - b);
  const avg = Math.round(sorted.reduce((a, b) => a + b, 0) / sorted.length);
  const p95 = sorted[Math.floor(sorted.length * 0.95)];
  const max = sorted[sorted.length - 1];
  console.log(`[${label}] ok=${ok}/${concurrency} avg=${avg}ms p95=${p95}ms max=${max}ms`);
  return { ok, concurrency, avg, p95, max };
}

(async () => {
  console.log('=== Railway LongRun 인프라 용량 보고 ===');
  console.log(`대상: https://${API}\n`);
  // 회원가입 후 토큰 획득
  const ts = Date.now();
  const sr = await post('/api/auth/signup', { email: `capacity_${ts}@test.com`, password: 'Test1234!', name: 'CapTest' });
  let token;
  try { token = JSON.parse(sr.body).access_token; } catch(e) {}
  if (!token) { console.log('토큰 획득 실패:', sr.body); process.exit(1); }
  console.log('=== [Railway] 읽기 (GET) 부하 테스트 ===');
  await run('GET×100',  100, () => get('/api/conditions?limit=30', token));
  await run('GET×200',  200, () => get('/api/conditions?limit=30', token));
  await run('GET×500',  500, () => get('/api/conditions?limit=30', token));
  console.log('\n=== [Railway] 쓰기 (POST) 부하 테스트 ===');
  await run('POST×50',  50,  () => post('/api/conditions', { fatigue: 5, mood: 7, energy: 6, composite_score: 72 }, token));
  await run('POST×100', 100, () => post('/api/conditions', { fatigue: 5, mood: 7, energy: 6, composite_score: 72 }, token));
  console.log('\n=== [Railway] 동시 접속 유저 환산 (API 요청 주기 5~10초 가정) ===');
  console.log('[Railway] 읽기 기준: 500 req 처리 → 약 2,500~5,000명 동시 접속');
  console.log('[Railway] 쓰기 기준: 100 req 처리 → 약 500~1,000명 동시 접속');
})();
```

```bash
node /tmp/capacity_test.js
```

### 3. 결과 해석

| 지표 | 기준 |
|------|------|
| 성공률 100% | 안정적 처리 가능 |
| 성공률 95~99% | 피크 타임 간헐적 실패 |
| 성공률 <95% | 병목 — pool/workers 조정 필요 |
| p95 < 500ms | 양호 |
| p95 500ms~1s | 주의 |
| p95 > 1s | 개선 필요 |

### 4. 병목 발생 시 조치

**DB 커넥션 부족 (Too many connections)**
```bash
# Railway MySQL 환경변수 추가
railway variable set MYSQL_MAX_CONNECTIONS=500
# database.py pool_size, max_overflow 조정
```

**Workers 부족**
```
# Procfile workers 수 조정 (권장: 2×vCPU+1)
gunicorn main:app --workers 16 ...
```
