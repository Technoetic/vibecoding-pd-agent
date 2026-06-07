# AI 콘텐츠 PD 에이전트 — 데모

양실장의 바이브코딩대학 PD 채용 과제. 4-에이전트 오케스트레이션으로 쇼츠 기획안을 실시간 생성한다.

## 핵심
- **4-에이전트:** Supervisor → Trend Analyst → Creator → Reviewer (BizRouter × gemini-2.5-flash-lite 단일 모델, 온도 차등)
- **채널 중복 방지:** 채널 73개 영상 제목과 토큰 자카드 대조 → 중복이면 강제 반려
- **실시간 트렌드:** Perplexity Sonar로 LLM/바이브코딩 최신 트렌드 + 출처 주입
- **Eval 8종:** 길이·키워드·독창성·양식·보안·한국수익규제·훅·완주율 전부 통과해야 승인
- **의존성 0:** 표준 라이브러리만(urllib, http.server, difflib)

## 로컬 실행
```bash
export BIZROUTER_API_KEY="sk-br-..."
export YOUTUBE_API_KEY="AIza..."   # 카탈로그 갱신 시에만(이미 channel_catalog.json 있음)
python server.py                    # http://localhost:8000
```

## 배포 (Railway)
1. 이 디렉토리를 Railway 서비스로 연결(Dockerfile 자동 감지).
2. Variables 탭에 BIZROUTER_API_KEY 등록(YOUTUBE_API_KEY는 카탈로그 재생성 시에만).
3. 배포 후 공개 URL 접속.

> 주의: 데모는 동시 1요청 직렬 처리. 클라가 중간에 끊겨도 백엔드 기획(유료 LLM)은 완주한다.

## 카탈로그 갱신
```bash
YOUTUBE_API_KEY=... python youtube_fetch.py   # channel_catalog.json 재생성
```

## 테스트
```bash
python -m pytest test_orchestrator.py test_server.py -q
```
