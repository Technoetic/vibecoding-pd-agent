# /railway-deploy — Railway 배포 실행

GitHub 레포 연동 배포 또는 CLI 직접 배포를 실행한다.

## 배포 방식 판단

- GitHub 레포가 있으면 → **GitHub 연동 배포** (push하면 자동 배포)
- GitHub 레포가 없으면 → **CLI 직접 배포** (`railway up`)

---

## A. GitHub 연동 배포 (권장)

### 1. 인증 확인
```bash
export RAILWAY_API_TOKEN=<토큰>
railway whoami
```
실패 시 → "RAILWAY_API_TOKEN 설정 필요" 안내 후 중단

### 2. GitHub 레포 확인
```bash
git remote -v
gh repo view --json nameWithOwner --jq '.nameWithOwner'
```
레포 없으면 → "GitHub 레포 필요" 안내

### 3. Railway 프로젝트 생성 (없으면)
```bash
URL=https://backboard.railway.app/graphql/v2

# 프로젝트 생성
curl -s -X POST $URL \
  -H "Authorization: Bearer $RAILWAY_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "mutation { projectCreate(input: { name: \"PROJECT_NAME\", workspaceId: \"WORKSPACE_ID\" }) { id name } }"}'
```

### 4. GitHub 레포로 서비스 생성
```bash
curl -s -X POST $URL \
  -H "Authorization: Bearer $RAILWAY_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "mutation { serviceCreate(input: { name: \"SERVICE_NAME\", projectId: \"PID\", source: { repo: \"OWNER/REPO\" } }) { id } }"}'
```

### 5. 환경 변수 설정 (필요 시)
```bash
curl -s -X POST $URL \
  -H "Authorization: Bearer $RAILWAY_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "mutation { variableUpsert(input: { projectId: \"PID\", serviceId: \"SID\", environmentId: \"EID\", name: \"KEY\", value: \"VALUE\" }) }"}'
```

### 6. 퍼블릭 도메인 생성
```bash
curl -s -X POST $URL \
  -H "Authorization: Bearer $RAILWAY_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "mutation { serviceDomainCreate(input: { environmentId: \"EID\", serviceId: \"SID\" }) { domain } }"}'
```

### 7. 배포 트리거 (git push)
```bash
git add .
git commit -m "deploy: Railway 배포"
git push origin main
```
GitHub 연동이면 push 시 자동 배포됨

### 8. 로그 확인
```bash
railway logs --tail 30
```

---

## B. CLI 직접 배포

### 1. 인증 확인
```bash
export RAILWAY_API_TOKEN=<토큰>
railway whoami
```

### 2. 프로젝트 연결
```bash
railway link
```

### 3. 빌드 확인
프로젝트 빌드 명령 실행 → 에러 없는지 확인

### 4. 배포
```bash
railway up --detach
```

### 5. 로그 + URL 확인
```bash
railway logs --tail 30
railway domain
```

---

## 재배포 (이미 서비스 있을 때)
```bash
# CLI
railway up --detach

# 또는 GraphQL
curl -s -X POST https://backboard.railway.app/graphql/v2 \
  -H "Authorization: Bearer $RAILWAY_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "mutation { serviceInstanceRedeploy(environmentId: \"EID\", serviceId: \"SID\") }"}'

# 또는 git push (GitHub 연동 시)
git push origin main
```

## 결과 보고

| 항목 | 결과 |
|:-----|:-----|
| 인증 | ? |
| 방식 | GitHub 연동 / CLI 직접 |
| 프로젝트 | ? |
| 서비스 | ? |
| 배포 | ? |
| 에러 | ? |
| URL | ? |

## 트러블슈팅

| 문제 | 해결 |
|------|------|
| Dockerfile not found | GitHub 연동 안됨 → CLI `railway up` 사용 |
| 정적 사이트로 빌드 | 루트에 index.html → Dockerfile 추가 |
| 502 Bad Gateway | `railway logs` 확인 |
| 자동 배포 안됨 | Railway 대시보드에서 GitHub 연동 확인 |
