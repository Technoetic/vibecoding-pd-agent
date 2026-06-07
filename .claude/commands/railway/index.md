# /railway — Railway 배포/관리 연동

사용자가 Railway 관련 작업을 요청하면 이 가이드를 따른다.

## 초기 설정 (한 번만)

```bash
# API 토큰 설정 (RAILWAY_TOKEN이 아닌 RAILWAY_API_TOKEN)
export RAILWAY_API_TOKEN=<토큰>

# 인증 확인
railway whoami

# 프로젝트 연결
railway link
```

> 토큰 발급: https://railway.app/account/tokens

## CLI 명령어

### 배포
```bash
railway up                    # 현재 디렉토리 배포
railway up --detach           # 백그라운드 배포
railway logs                  # 배포 로그
railway logs --tail 50        # 최근 50줄
```

### 프로젝트 관리
```bash
railway status                # 현재 프로젝트/환경 상태
railway whoami                # 인증 상태
railway link                  # 프로젝트 연결
railway unlink                # 연결 해제
railway init --name <이름>    # 새 프로젝트 생성
```

### 환경 변수
```bash
railway variable              # 변수 목록
railway variable set KEY="value"  # 변수 설정
railway variable delete KEY       # 변수 삭제
```

### 서비스/도메인
```bash
railway service               # 서비스 목록/선택
railway domain                # 퍼블릭 도메인 생성/확인
railway run <명령어>           # Railway 환경에서 명령 실행
```

## GraphQL API

엔드포인트: `https://backboard.railway.app/graphql/v2`
인증: `Authorization: Bearer $RAILWAY_API_TOKEN`

### 계정 확인
```bash
curl -s -X POST https://backboard.railway.app/graphql/v2 \
  -H "Authorization: Bearer $RAILWAY_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "{ me { name email } }"}'
```

### 프로젝트 생성
```bash
curl -s -X POST https://backboard.railway.app/graphql/v2 \
  -H "Authorization: Bearer $RAILWAY_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "mutation { projectCreate(input: { name: \"NAME\", workspaceId: \"WORKSPACE_ID\" }) { id name } }"}'
```

### 서비스 생성 (Docker 이미지)
```bash
curl -s -X POST https://backboard.railway.app/graphql/v2 \
  -H "Authorization: Bearer $RAILWAY_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "mutation { serviceCreate(input: { name: \"NAME\", projectId: \"PID\", source: { image: \"mysql:8\" } }) { id } }"}'
```

### 서비스 생성 (GitHub 레포)
```bash
curl -s -X POST https://backboard.railway.app/graphql/v2 \
  -H "Authorization: Bearer $RAILWAY_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "mutation { serviceCreate(input: { name: \"NAME\", projectId: \"PID\", source: { repo: \"OWNER/REPO\" } }) { id } }"}'
```

### 환경 변수 설정
```bash
curl -s -X POST https://backboard.railway.app/graphql/v2 \
  -H "Authorization: Bearer $RAILWAY_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "mutation { variableUpsert(input: { projectId: \"PID\", serviceId: \"SID\", environmentId: \"EID\", name: \"KEY\", value: \"VALUE\" }) }"}'
```

> 서비스 간 참조: `${{ServiceName.RAILWAY_PRIVATE_DOMAIN}}`

### 퍼블릭 도메인 생성
```bash
curl -s -X POST https://backboard.railway.app/graphql/v2 \
  -H "Authorization: Bearer $RAILWAY_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "mutation { serviceDomainCreate(input: { environmentId: \"EID\", serviceId: \"SID\" }) { domain } }"}'
```

### 재배포
```bash
curl -s -X POST https://backboard.railway.app/graphql/v2 \
  -H "Authorization: Bearer $RAILWAY_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "mutation { serviceInstanceRedeploy(environmentId: \"EID\", serviceId: \"SID\") }"}'
```

### 삭제

#### 도메인 삭제
```bash
# 1. 도메인 ID 조회
railway status --json
# → domains.serviceDomains[].id 에서 확인

# 2. 삭제
curl -s -X POST https://backboard.railway.app/graphql/v2 \
  -H "Authorization: Bearer $RAILWAY_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "mutation { serviceDomainDelete(id: \"DOMAIN_ID\") }"}'
```

#### 서비스 삭제
```bash
curl -s -X POST https://backboard.railway.app/graphql/v2 \
  -H "Authorization: Bearer $RAILWAY_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "mutation { serviceDelete(id: \"SID\") }"}'
```

#### 프로젝트 삭제
```bash
curl -s -X POST https://backboard.railway.app/graphql/v2 \
  -H "Authorization: Bearer $RAILWAY_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "mutation { projectDelete(id: \"PID\") }"}'
```

### 로그 조회
```bash
# 빌드 로그
curl -s -X POST https://backboard.railway.app/graphql/v2 \
  -H "Authorization: Bearer $RAILWAY_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "{ buildLogs(deploymentId: \"DID\", limit: 50) { message } }"}'

# 런타임 로그
curl -s -X POST https://backboard.railway.app/graphql/v2 \
  -H "Authorization: Bearer $RAILWAY_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "{ deploymentLogs(deploymentId: \"DID\", limit: 50) { message } }"}'
```

## 작업 흐름 자동화

### "배포해" 요청 시
1. `railway whoami` — 인증 확인
2. `railway status` — 연결된 프로젝트 확인
3. `railway up --detach` — 배포
4. `railway logs --tail 20` — 로그 확인
5. `railway domain` — URL 반환

### "환경 변수 설정해" 요청 시
1. `railway variable` — 현재 변수 확인
2. `railway variable set KEY="value"` — 설정
3. 결과 확인

### "롤백해" 요청 시
1. git revert → railway up으로 재배포
2. 또는 GraphQL `serviceInstanceRedeploy` 사용

## Dockerfile 템플릿

### FastAPI
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Node.js
```dockerfile
FROM node:20-slim
WORKDIR /app
COPY package*.json ./
RUN npm ci --production
COPY . .
CMD ["node", "server.js"]
```

## 트러블슈팅

| 문제 | 원인 | 해결 |
|------|------|------|
| Unauthorized | 토큰 만료/잘못됨 | `railway.app/account/tokens`에서 재발급 |
| Dockerfile not found | GitHub 연동 안됨 | CLI `railway up` 사용 |
| 정적 사이트로 빌드 | 루트에 index.html | Dockerfile 추가 |
| 502 Bad Gateway | 앱 시작 실패 | `railway logs` 확인 |

## 주의사항
- 환경 변수명: `RAILWAY_API_TOKEN` (계정 토큰) vs `RAILWAY_TOKEN` (프로젝트 토큰, 배포만)
- 환경 변수에 민감 정보 포함 시 콘솔에 출력하지 않기
- 배포 전 빌드 에러 없는지 확인
