# /github — GitHub CLI/API 연동 가이드

사용자가 GitHub 관련 작업을 요청하면 이 가이드를 따른다.

## 사용 가능한 도구

### 1. git — 로컬 작업
```bash
git status              # 현재 상태
git add <파일>           # 스테이징
git commit -m "메시지"   # 커밋
git push origin <브랜치> # 푸시
git pull origin <브랜치> # 풀
git branch              # 브랜치 목록
git checkout -b <이름>   # 새 브랜치
git log --oneline -10   # 최근 커밋
git diff                # 변경사항
git tag v1.0.0          # 태그
git revert <커밋해시>    # 롤백
```

### 2. gh — GitHub API 작업
```bash
# PR
gh pr create --title "제목" --body "내용"
gh pr list
gh pr merge <번호>
gh pr view <번호>

# 이슈
gh issue create --title "제목" --body "내용"
gh issue list
gh issue close <번호>

# 릴리스
gh release create v1.0.0 --title "v1.0.0" --notes "릴리스 노트"
gh release list

# 레포 관리
gh repo view
gh api repos/<owner>/<repo>/collaborators/<user> -X PUT -f permission=push

# 리뷰
gh pr review <번호> --approve
gh pr review <번호> --request-changes --body "수정사항"
```

### 3. gh api — 직접 API 호출
```bash
# Collaborator 추가
gh api repos/OWNER/REPO/collaborators/USERNAME -X PUT -f permission=push

# Branch protection
gh api repos/OWNER/REPO/branches/main/protection -X PUT -f '...'

# 워크플로우 확인
gh api repos/OWNER/REPO/actions/runs --jq '.workflow_runs[:5]'
```

## 작업 흐름 자동화

사용자가 요청하면 다음 흐름을 자동 실행한다:

### "PR 만들어" 요청 시
1. `git status` — 변경사항 확인
2. `git checkout -b feature/설명` — 브랜치 생성
3. `git add` + `git commit` — 커밋
4. `git push -u origin feature/설명` — 푸시
5. `gh pr create` — PR 생성
6. PR URL 반환

### "릴리스 만들어" 요청 시
1. `git log` — 최근 변경사항 확인
2. `git tag vX.X.X` — 태그
3. `git push origin vX.X.X` — 태그 푸시
4. `gh release create` — 릴리스 생성

### "롤백해" 요청 시
1. `git log --oneline -20` — 최근 커밋 보여주기
2. 사용자에게 어디로 돌아갈지 확인
3. `git revert` — 안전하게 되돌리기
4. 결과 확인

### "권한 줘" 요청 시
1. `gh api repos/OWNER/REPO/collaborators/USERNAME -X PUT -f permission=push`
2. 결과 확인

## 커밋 메시지 규칙
```
feat: 새 기능
fix: 버그 수정
refactor: 리팩토링
style: CSS/디자인
docs: 문서
test: 테스트
chore: 빌드/설정
```

## 주의사항
- `main` 브랜치에 직접 push 금지 → PR로만 병합
- `--force` push는 사용자 명시적 요청 시에만
- 커밋 전 `git diff`로 변경사항 확인
- PR 생성 전 테스트 통과 확인
