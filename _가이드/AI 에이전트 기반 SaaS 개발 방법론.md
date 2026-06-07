# **AI 에이전트 기반 SaaS 개발 방법론: 클로드 코드(Claude Code)와 옵시디언(Obsidian)을 활용한 지식 축적 및 탐색 자동화 아키텍처 설계**

소프트웨어 엔지니어링의 패러다임은 개발자가 직접 코드를 타이핑하는 방식에서, AI 에이전트가 코드베이스 전체를 읽고, 파일을 편집하며, 테스트 코드를 실행하고, 형상 관리 시스템에 커밋을 수행하는 자율형 시스템(Agentic System)으로 급격히 전환되고 있다. 특히 앤스로픽(Anthropic)이 개발한 클로드 코드(Claude Code)는 터미널 내에서 구동되며 파일 시스템과 개발 도구에 직접 접근할 수 있는 강력한 대화형 및 자율형 코딩 에이전트이다. 이러한 시스템은 기존의 단순한 자동 완성(Autocomplete) 도구를 넘어, 개발자가 요구사항의 명세와 아키텍처를 정의하면 시스템이 스스로 구현체를 완성해 내는 진정한 의미의 '에이전트 기반 개발(Agentic Development)'을 가능하게 한다. 기업 환경에서도 AI 에이전트의 활용은 급증하고 있으며, 운영 비용 최적화와 코드 품질 관리라는 과제와 맞물려 개발 환경에 통합되고 있다.     
그러나 클로드 코드와 같은 거대 언어 모델(LLM) 기반의 에이전트를 활용하여 대규모 SaaS(Software as a Service) 애플리케이션을 개발할 때, 개발자는 필연적으로 '컨텍스트 윈도우(Context Window)의 한계'와 '상태 비저장성(Statelessness)'이라는 두 가지 근본적인 기술적 병목에 직면하게 된다. 에이전트가 복잡한 디렉토리를 탐색하고 여러 파일을 수정하는 과정에서 컨텍스트는 매우 빠르게 채워지며, 일정 한계(약 95%)에 도달하면 시스템은 과거의 대화 기록을 파기하고 요약본으로 대체하는 '압축(Compaction)' 과정을 강제로 수행한다. 이 과정에서 세밀한 아키텍처 결정 사항, 이전 세션에서의 디버깅 맥락, 그리고 프로젝트 고유의 규칙들이 유실되는 치명적인 문제가 발생한다.     
이러한 한계를 극복하고 AI 에이전트가 대규모 SaaS 개발을 연속적으로, 그리고 오류 없이 수행할 수 있도록 하기 위해서는 에이전트의 일시적인 작업 세션(Session) 외부에서 지식을 영구적으로 저장하고 관리할 수 있는 **지식 관리 아키텍처(Knowledge Management Architecture)** 가 필수적이다. 본 보고서는 마크다운(Markdown) 기반의 로컬 지식 관리 도구인 옵시디언(Obsidian)을 '영구적 상태 계층(Persistent State Layer)'으로 설정하고, 클로드 코드를 '상태 비저장 작업자(Stateless Worker)'로 규정하여 SaaS 애플리케이션(특히 Next.js 및 Supabase 환경)을 구축하는 구체적이고 실전적인 방법론을 심층 분석한다. 본 보고서는 단순한 개념 설명을 배제하고, 실제 프로젝트에 즉시 적용할 수 있는 디렉토리 구조, 설정 파일(JSON), 훅(Hook) 스크립트, 그리고 프롬프트 파이프라인을 체계적으로 제공한다.

## **1\. 아키텍처의 이론적 배경: 클로드 코드의 메모리 시스템과 한계**

클로드 코드를 활용한 지식 축적 방법론을 구체화하기에 앞서, 시스템이 내부적으로 지식을 어떻게 처리하고 관리하는지 그 매커니즘을 정확히 이해해야 한다. 클로드 코드는 단일 컨텍스트의 한계를 극복하기 위해 다층적인 메모리 아키텍처를 도입하고 있으나, 각각의 계층은 명확한 한계를 지니고 있다.

| 메모리 유형 | 작성 주체 | 주요 내용 | 스코프 | 지속성 및 로드 시점 |
| :---- | :---- | :---- | :---- | :---- |
| **CLAUDE.md** | 개발자 | 지시사항, 아키텍처 규칙, 코딩 스타일, 워크플로우 제약 사항 | 프로젝트 루트, 사용자 계정, 또는 전체 조직 | 모든 세션 시작 시 가장 먼저 컨텍스트에 로드되며 절대적인 진리(Ground Truth)로 취급됨 |
| **자동 메모리 (Auto Memory)** | 클로드(AI) | 빌드 명령어, 빈번한 디버깅 패턴, 코드 스타일 선호도, 작업 습관 | Git 리포지토리 단위 (작업 트리 간 공유됨) | 모든 세션 시작 시 로드 (단, 200줄 또는 25KB의 엄격한 용량 제한이 존재함) |
| **세션 메모리 (Session Memory)** | 시스템 | 대화 기록 요약 및 진행 중인 작업의 상태 | 단일 세션 내 | 압축(Compaction) 이벤트 발생 시 생성되어 이전 컨텍스트를 대체함 |
| **외부 지식 베이스 (Obsidian)** | 개발자 & AI | 영구적 설계 문서, 컴포넌트 명세, 전체 Handoff 프로토콜, 회의록 및 도메인 지식 | 로컬 파일 시스템 전체 (벤더 종속성 없음) | 훅(Hooks) 메커니즘이나 명시적 프롬프트를 통해 온디맨드(On-demand) 방식으로 로드됨 |


### **1.1. 자동 메모리(Auto Memory)의 메커니즘과 제약**

자동 메모리는 개발자가 명시적으로 지시하지 않아도 클로드 코드가 세션 도중 스스로 학습한 내용을 기록하는 기능이다. 예를 들어, 특정 환경 변수가 누락되어 발생하는 오류 패턴이나 특정 패키지 매니저(예: pnpm)의 선호도를 에이전트가 스스로 판단하여 .claude/projects/\<project\>/memory/ 경로 내의 마크다운 파일(예: debugging.md, api-conventions.md)에 저장한다. 이 디렉토리에는 MEMORY.md라는 색인 파일이 존재하여 클로드가 저장된 위치를 추적한다.     
백그라운드에서는 'Auto Dream'이라는 프로세스가 유휴 시간 동안 복잡한 메모리들을 병합하고 오래된 내용을 정리한다. 그러나 이 시스템은 단일 도구 단위의 로컬 파일 기반 아키텍처라는 태생적 한계를 갖는다. 메모리 인덱스는 최대 200줄로 제한되어 있으며, 의미론적 검색(Semantic Search)이 불가능하고 오직 정확한 키워드 매칭에만 의존한다. 또한, 다른 AI 에이전트 도구(예: Cursor, OpenCode 등)로 전환할 경우 이 지식은 전혀 호환되지 않고 초기화된다.   

### **1.2. 컨텍스트 엔지니어링: 압축(Compaction)과 도구 정리(Tool Clearing)**

SaaS 개발 과정에서 에이전트는 파일 읽기, 정규식 검색(Grep), 쉘 스크립트 실행 등 수백 번의 도구 호출(Tool Use)을 수행한다. 클로드 모델(Sonnet 4.6 또는 Opus 4.7)은 200K\~1M 토큰의 컨텍스트 윈도우를 제공하지만, 대규모 저장소를 탐색하면 이 공간은 수 시간 내에 고갈된다. 이를 관리하기 위해 시스템은 세 가지 컨텍스트 엔지니어링 기법을 사용한다.   

1. **도구 결과 정리(Tool-result Clearing):** 문서 읽기나 파일 검색 후, 불필요해진 방대한 원시 데이터(Raw data) 반환 값을 컨텍스트 윈도우에서 의도적으로 삭제하여 윈도우 비대화를 방지한다.     
2. **컨텍스트 압축(Context Compaction):** 입력 토큰이 제한치의 약 95%에 도달하면, 백그라운드 스레드가 트리거된다. 시스템은 이전의 전체 대화 기록을 다른 LLM 호출을 통해 요약하도록 지시하며, 생성된 요약본을 \<summary\>\</summary\> 태그로 감싸 컨텍스트 맨 앞에 배치한다. 이후 이전의 상세한 분류, 탐색 로그, 논의 과정은 완전히 영구 삭제된다.     
3. **외부 메모리 기록(Memory):** 구조화된 노트 테이킹 방식으로, 에이전트가 컨텍스트 윈도우 외부의 영구 저장소에 진행 상황을 기록하여 다중 세션 간에 지식을 유지한다.   

압축이 발생할 때마다 시스템은 성능 저하를 방지하지만, 초기 세션에서 합의했던 미묘한 구현 제약이나 사용자 취향, 임시 변수명 등은 요약 과정에서 유실될 확률이 극히 높다. CLAUDE.md는 압축의 영향을 받지 않고 시스템 프롬프트로서 보존되는 유일한 파일이지만 , 이 파일이 지나치게 비대해지면 에이전트가 지시사항의 우선순위를 혼동하여 결국 규칙을 무시(Ignore)하는 역효과가 발생한다.     
결론적으로, 대규모 SaaS의 아키텍처와 컨텍스트를 유지하기 위해서는 CLAUDE.md를 최소화하고, 클로드 코드 외부에 구조화된 영구 지식 베이스(옵시디언)를 구축하여, 에이전트가 필요할 때마다 스스로 지식을 읽고 쓰는 자동화된 파이프라인을 설계해야 한다.

## **2\. 영구적 상태 계층 설계: AI 지향적 옵시디언 볼트(Vault) 구축**

옵시디언(Obsidian)은 데이터를 로컬 파일 시스템에 순수 텍스트(Plain Text) 및 마크다운 형식으로 저장한다. 이는 특수한 플러그인이나 벤더 종속성 없이도 클로드 코드가 쉘 명령어(Bash)나 파일 읽기/쓰기 도구만을 사용하여 데이터를 온전히 조작할 수 있음을 의미한다. 인간 개발자를 위한 기존의 지식 관리 시스템(PKM)은 시각적 그래프 뷰나 태그 클라우드, 복잡한 중첩 폴더를 선호하지만, AI가 주도하는 환경에서는 철저히 **AI 지향적(AI-Orientation)** 으로 볼트를 설계해야 한다.     
AI 세션을 '상태 비저장 작업자(Stateless Worker)'로 간주하고, 옵시디언을 '영구적 상태 계층(Persistent State Layer)'으로 활용하는 구조에서는 에이전트가 단독으로 30초 이내에 프로젝트의 현황을 파악하고 작업을 재개할 수 있는 프로토콜이 필수적이다.   

### **2.1. SaaS 프로젝트 내장형 디렉토리 아키텍처**

AI 지향적 옵시디언 볼트는 프로젝트 루트의 최상위 디렉토리에 위치시켜 코드베이스와의 접근성을 극대화해야 한다. 다음은 복잡한 Next.js 및 Supabase 기반 SaaS 프로젝트를 관리하기 위한 표준 볼트 구조이다.  
/my-saas-project  
├──.claude/  
│   ├── settings.json           \# 클로드 코드 훅(Hooks) 설정 (팀 공유 가능)  
│   └── settings.local.json     \# 개인화된 로컬 훅 설정 (Git ignore 대상)   
├── CLAUDE.md                   \# 최상위 에이전트 행동 지시사항 (진입점)   
├── src/                        \# SaaS 소스 코드 (Next.js App Router)  
├── supabase/                   \# 데이터베이스 마이그레이션, Edge Functions, 타입 정의  
└── docs/                       \# 옵시디언 볼트 루트 디렉토리 (AI 상태 계층)  
├── 000 \- Rules/  
│   ├── A-Meta\_rules.md     \# 에이전트 프롬프트 원칙 및 코드 작성 철학   
│   ├── B-Tech\_Stack.md     \# 프레임워크별 문법(Next.js 15, Tailwind 4, Shadcn/ui)   
│   ├── C-Architecture.md   \# 마이크로서비스 구조 및 Supabase 데이터베이스 스키마   
│   └── E-Index.md          \# 000 폴더 내 주요 기술 문서의 메타 목차   
├── 001 \- Working Context/  
│   ├── Feature\_Auth.md     \# 현재 구현 중인 특정 도메인(인증/인가)의 컨텍스트   
│   └── Feature\_Payment.md  \# Stripe 결제 연동 도메인의 컨텍스트   
├── 002 \- Daily Logs/       \# 매일 생성되는 디버깅 로그 및 작업 내역 (타임스탬프)   
├── Session\_Handoff.md      \# 세션 종료 시 다음 세션을 위해 강제 기록되는 인계 파일   
└── Vault\_Navigation.md     \# 에이전트에게 볼트 전체의 구조를 맵핑해 주는 마스터 내비게이션    

### **2.2. 핵심 오리엔테이션 파일 명세**

볼트 내 파일들은 인간을 위한 미려한 서술보다는 AI가 정규 표현식으로 파싱하기 쉽고, 헤더 계층이 명확한 구조적 마크다운을 사용해야 한다. 특히 에이전트의 부트스트래핑을 돕는 두 가지 핵심 파일의 작성 규격은 다음과 같다.

#### **\[문서 1:** docs/Vault\_Navigation.md**\]**

이 문서는 에이전트가 볼트의 지형을 이해하기 위해 세션 시작 즉시 읽어야 하는 '지도'이다.

# **볼트 내비게이션 구조 (AI Orientation Map)**

이 디렉토리(docs/)는 SaaS 개발을 위한 영구적 상태 저장소(Persistent State Layer)이다.  
새로운 세션이 시작되면, 스스로 코드베이스를 유추하기 전에 반드시 이 내비게이션과 Session\_Handoff.md를 우선적으로 읽어야 한다.

* 000 \- Rules/: 기술 스택의 코어 규칙, Supabase 연동 제약 사항, 아키텍처 결정 사항이 정의되어 있다. 코드를 수정하기 전 반드시 해당 도메인의 문서를 검색(Grep/Read)하라.  
* 001 \- Working Context/: 현재 활성화된 피처(Feature)의 구체적인 구현 목표와 API 스펙이 담겨 있다.  
* 002 \- Daily Logs/: 과거에 직면했던 에러 로그와 해결 과정이 시간순으로 보존된다.  
* Session\_Handoff.md: 이전 세션의 작업자가 남긴 최신 작업 완료 상태와 다음 작업 지시사항이다.

연속성을 보장하기 위해 세션 종료 직전 훅(Hook)이나 명시적 프롬프트에 의해 자동 갱신되는 프로토콜 문서이다. 이 파일은 에이전트의 워킹 메모리를 대체한다.   

# **Session Handoff Protocol**

## **1\. 최근 완료된 작업 (Completed)**

* @supabase/ssr 패키지를 활용한 미들웨어(src/middleware.ts) 쿠키 갱신 로직 구현 완료  
* docs/000 \- Rules/B-Tech\_Stack.md 내에 Supabase 클라이언트 분리 규칙 문서화 완료

## **2\. 인간의 검토가 필요한 사항 (Needs Human Review)**

* 미들웨어 매처(Matcher) 정규식에서 /api 라우트가 올바르게 제외되었는지 보안 검토 요망

## **3\. 보류된 작업 (Deferred)**

* 소셜 로그인(OAuth 2.0 PKCE 흐름) 기능 통합은 다음 스프린트로 연기됨.

## **4\. 다음 단계 지시사항 (Next Actions)**

* src/app/dashboard/page.tsx에 서버 컴포넌트를 생성하여 유저 세션을 검증하고 대시보드 UI를 구현할 것.  
* 작업 시작 전 docs/000 \- Rules/B-Tech\_Stack.md의 '서버 컴포넌트 환경의 Supabase 호출 패턴' 섹션을 숙독할 것.

### **2.3. 옵시디언 파일 시스템 제어 전략**

옵시디언 커뮤니티의 실무 적용 사례에 따르면, 로컬 REST API 플러그인을 사용하여 데이터를 업데이트하는 방식은 지속적인 다중 쓰기 작업 시 심각한 오버헤드를 발생시킨다. 따라서 클로드 코드에게 옵시디언 문서를 갱신하도록 지시할 때는, 순수 마크다운의 강점을 살려 **운영체제 레벨의 원시 파일 조작(Raw File Operations)** 을 수행하도록 명시해야 한다. 플러그인 기능(예: Dataview, Templater)의 실행은 텍스트가 저장된 이후 옵시디언 앱 내부에서 스스로 처리하도록 위임하는 것이 에이전트의 I/O 병목을 제거하는 핵심 비결이다.   

## **3\. 에이전트 제어의 중추: CLAUDE.md 최적화 및.claudeignore 라우팅**

옵시디언 볼트라는 거대한 지식 창고가 준비되었다면, 이제 클로드 코드에게 이 창고를 어떻게 활용할 것인지 명확한 행동 강령을 부여해야 한다. 그 시작점은 프로젝트 루트의 CLAUDE.md이다.   

### **3.1. 점진적 정보 공개(Progressive Disclosure) 기반 CLAUDE.md 작성**

CLAUDE.md는 일반적인 인간용 README.md와 달리 에이전트를 위한 '행동 계약서'이다. 클로드 코드는 모델 자체의 시스템 프롬프트에 이미 약 50개의 개별 지시사항을 내포하고 있으므로 , 개발자가 CLAUDE.md에 수백 줄의 세부 로직을 욱여넣으면 지시사항의 희석 현상이 발생하여 에이전트가 규칙을 무시하게 된다.     
가장 이상적인 접근법은 **'점진적 정보 공개(Progressive Disclosure)'** 패턴이다. CLAUDE.md에는 절대 변하지 않는 메타 원칙과 옵시디언 볼트로의 탐색 경로(포인터)만을 제시하고, 도메인 지식은 필요 시 옵시디언에서 로드하도록 설계한다.   

# **프로젝트 진입점 및 필수 행동 강령**

이 프로젝트는 Next.js 15 (App Router), Tailwind 4, 그리고 Supabase를 활용한 B2B SaaS 애플리케이션이다.   

## **1\. 초기화 프로토콜 (Initialization)**

* 세션을 시작할 때마다 가장 먼저 docs/Vault\_Navigation.md와 docs/Session\_Handoff.md를 읽고 현재의 작업 맥락을 파악하라.     
* 코드베이스의 동작을 스스로 추측(Vibe coding)하지 마라. docs/000 \- Rules/ 폴더에 정의된 아키텍처 규칙을 우선적으로 검색하여 스펙 기반 개발(Spec-driven development)을 수행하라.   

## **2\. 지식 축적 및 워크플로우 (Workflow)**

* 복잡한 리팩토링이나 새로운 도메인 기능 개발 시, 코드 생성에 앞서 docs/001 \- Working Context/ 내에 관련 마크다운 파일을 생성하여 설계 스펙을 문서화하고 승인을 받아라.     
* 해결하기 어려운 버그를 수정하거나 새로운 CLI 명령어 파라미터를 발견했을 경우, 즉시 해당 패턴을 docs/002 \- Daily Logs/에 타임스탬프와 함께 기록하라.

## **3\. 절대 금지 규칙 (Critical Rules)**

* npm을 사용하지 마라. 이 프로젝트는 철저히 pnpm을 통해 의존성을 관리한다.  
* 임의의 환경변수를 추가하지 마라. 모든 환경 변수는 개발 인프라 규약에 따라 관리되어야 한다.   

\*\*\*\*    

| ✅ 반드시 포함해야 할 사항 (Include) | ❌ 배제하고 옵시디언으로 이관할 사항 (Exclude) |
| :---- | :---- |
| 옵시디언 docs/ 경로에 대한 내비게이션 지시 | 특정 API의 상세한 엔드포인트 명세서 |
| 프로젝트 전반에 걸친 아키텍처 원칙 (예: App Router 전용) | 파일 단위의 상세한 동작 설명 |
| 에이전트가 유추하기 힘든 커스텀 Bash 빌드 명령어 | 코드 분석만으로 파악 가능한 표준 언어 규칙 |
| 로컬 환경 변수 설정 등 특이한 개발 환경(Quirks) | 빈번하게 변경되는 비즈니스 로직이나 요구사항 |
| 브랜치 명명 규칙 등 강제해야 할 Git 워크플로우 제약 | "깨끗한 코드를 작성하라"와 같은 자명한 추상적 지시 |

### **3.2. 계층적 무시 처리:.claudeignore와 훅 연동**

클로드 코드는 뛰어난 탐색 능력을 갖추고 있으나, 종종 용량이 방대하고 정보 가치가 없는 디렉토리(예: node\_modules, build/, .next/)나 보안이 유지되어야 하는 크리덴셜(\*.env, \*.pem)을 읽으려 시도하여 토큰을 극심하게 낭비하거나 보안 취약점을 발생시킬 수 있다.     
이를 원천 차단하기 위해 깃허브(GitHub) 커뮤니티에서 고안된 claude-ignore 스크립트를 시스템에 통합해야 한다. 루트에 .claudeignore 파일을 작성하고, 파일 읽기 도구가 실행되기 직전에 평가되는 PreToolUse 훅을 통해 읽기를 원천 차단(Exit code 2)할 수 있다.     
**\[파일:** .claudeignore**\]**  
node\_modules/  
.next/  
.env\*  
\*.secret  
docs/.obsidian/           \# 옵시디언 자체 설정 파일은 AI가 읽을 필요 없음  
docs/002 \- Daily Logs/Archive/  \# 오래된 아카이브는 압축 방지를 위해 배제  
해당 기능을 전역 또는 로컬 프로젝트에 적용하기 위해 훅 설정 파일(.claude/settings.json)에 다음과 같이 명시한다. 이는 에이전트가 도구를 사용하기 전에 항상 평가되는 보안 게이트 역할을 수행한다.   

JSON  
{  
  "hooks": {  
    "PreToolUse":  
      }  
    \]  
  }  
}

스크립트 실행 결과가 2로 반환되면, 클로드 코드는 해당 파일의 열람을 포기하고 컨텍스트 낭비를 원천 차단하게 된다.   

## **4\. SaaS 개발 시나리오 분석: Next.js와 Supabase 지식의 문서화 전략**

지식 관리 구조가 완성되었다면, 실제 SaaS 프로젝트의 기술 스택을 에이전트가 어떻게 이해하고 코드를 생성하는지 구체적인 시나리오를 통해 분석한다. 대표적인 풀스택 스택인 Next.js (App Router)와 Supabase의 결합은 인증(Auth) 및 서버사이드 렌더링(SSR) 처리에서 지속적인 아키텍처 변화를 겪고 있으므로, 과거 데이터로 학습된 언어 모델은 종종 구식 라이브러리(예: @supabase/auth-helpers-nextjs)를 사용하려는 할루시네이션(Hallucination)을 유발한다. 이를 억제하기 위해 옵시디언 볼트에 최신 기술 문서를 명확히 작성해 두어야 한다.   

### **4.1. 기술 스택 명세서: SSR 및 인증 흐름 작성**

에이전트가 Supabase 클라이언트를 구현할 때 반드시 참고하도록 docs/000 \- Rules/B-Tech\_Stack.md에 다음과 같은 기술 스펙을 기록한다.

# **기술 스택 가이드라인: Next.js & Supabase SSR**

이 SaaS 프로젝트는 서버 렌더링 최적화와 보안을 위해 패스워드 기반 및 OAuth 인증을 완벽히 SSR 환경에서 처리한다.   

## **1\. 서버/클라이언트 컴포넌트의 엄격한 분리**

* 사용자 상호작용(이벤트 리스너, 훅)이 필수적인 최하위 컴포넌트에만 'use client' 지시어를 명시한다.     
* 데이터를 페칭하거나, 폼(Form) 처리를 위한 로직은 기본적으로 서버 컴포넌트(Server Components)나 서버 액션(Server Actions)으로 작성하여 클라이언트 번들 사이즈를 줄인다.   

## **2\. @supabase/ssr 패키지 의존성 규약**

* 과거의 @supabase/auth-helpers-nextjs 패키지 사용은 절대 금지된다. 반드시 @supabase/ssr 베타 패키지를 사용해야 한다.     
* 로컬 스토리지 대신 HTTP 전용 쿠키(Cookies)를 통해 유저 세션을 관리한다.   

## **3\. 클라이언트 유틸리티 추상화 패턴**

절대 createClient를 컴포넌트 내에서 하드코딩하지 않는다. 다음의 유틸리티 경로를 엄수하라.   

* **클라이언트 컴포넌트 접근 시**: 브라우저 환경에 맞게 createBrowserClient를 래핑한 utils/supabase/client.ts를 사용한다.     
* **서버 컴포넌트 / 서버 액션 접근 시**: 쿠키 조작이 수반되는 createServerClient를 래핑한 utils/supabase/server.ts를 호출한다.   

## **4\. 다국어(i18n) 및 Auth 미들웨어(Middleware) 체이닝**

Next.js App Router의 src/middleware.ts에서는 인증 토큰 갱신과 로케일 라우팅이 충돌하지 않도록 구현해야 한다.   

* 미들웨어 내부에서 @supabase/ssr의 updateSession을 호출하여 세션을 안정적으로 갱신한다.     
* matcher 배열에 /api 나 /auth/confirm 등 토큰 갱신 로직이 불필요한 라우트는 철저히 배제(Exclude)하도록 정규 표현식을 구성하여 불필요한 리디렉션 루프를 방지한다.   

이와 같이 도메인의 핵심 원칙이 구조화된 문장으로 기록되어 있으면, 클로드 코드는 코드를 작성하기 전 이 문서를 Read 도구로 확인하여, 인간 개발자가 직접 검토한 수준과 동일한 구조의 코드를 지체 없이 산출해 낸다.

## **5\. 결정론적 지식 탐색 및 강제화 자동화: 클로드 코드 훅(Hooks) 시스템**

단순히 CLAUDE.md에 "작업 전 옵시디언 문서를 읽어라"라고 명시하는 것(Prompt-based rules)은 에이전트의 상황 판단에 의존하는 '소프트 제어'이다. 반면, .claude/settings.json 내의 **훅(Hooks)** 시스템을 활용하면 15가지의 생명주기 이벤트 시점에 쉘 명령어, HTTP 요청, 하위 에이전트 등을 강제 실행하여 결정론적인(Deterministic) '하드 제어'가 가능해진다. 규제 환경이나 프로덕션 급 SaaS를 다룰 때 이 차이는 "아마도 따를 것이다"와 "반드시 따른다"의 차이를 만든다.   

### **5.1. SessionStart 훅: 부트스트래핑과 지식 강제 주입**

에이전트가 터미널에서 구동되자마자, 과거의 Handoff 이력과 볼트의 지형도를 컨텍스트에 즉각적으로 주입하여 초기화 오버헤드를 없앤다. SessionStart 이벤트는 세션이 시작되거나 재개될 때 단 한 번 실행된다.     
**\[파일:** .claude/settings.json **구성 예시\]**

JSON  
{  
  "hooks": {  
    "SessionStart":  
      }  
    \]  
  }  
}

이 훅이 존재하면, 사용자가 claude 명령어를 타이핑하는 순간 쉘은 옵시디언 파일의 마크다운 내용을 stdout으로 출력하며, 클로드 코드는 이 표준 출력을 수신하여 첫 프롬프트를 대기하기 전에 이미 프로젝트의 상태를 완벽히 숙지하게 된다.   

### **5.2. PostToolUse 훅: 품질 게이트(Quality Gate) 및 자동화**

클로드 코드가 파일 편집(Write, Edit, MultiEdit)을 수행할 때마다 인간은 포맷팅 불일치나 린트 에러를 마주할 수 있다. 작업 승인(Approve)을 계속 클릭하며 흐름이 끊기는 상황을 막기 위해 PostToolUse 훅을 설정한다.   

JSON  
{  
  "hooks": {  
    "PostToolUse":  
      }  
    \]  
  }  
}

파일 조작이 완료된 직후 이 훅이 실행되어 Prettier가 코드를 정리한다. 에이전트는 코드 컨벤션에 신경 쓸 필요 없이 비즈니스 로직 설계에만 집중할 수 있어, 제로 컨텍스트 스위칭(Zero context switches) 상태가 달성된다. 실무적으로는 ESLint를 연동하여 console.log가 남아있는지 확인하는 품질 게이트(Quality Gate) 스크립트로 확장할 수도 있다.   

### **5.3. PreCompact 및 Stop 훅: 문맥 유실 방지 및 세션 인계**

에이전트가 오랜 시간 코딩하여 컨텍스트 토큰이 임계치에 도달하면 PreCompact 이벤트가 발생한다. 이 시점에 시스템이 대화 이력을 요약 및 삭제하기 전, 중요한 작업 내역을 옵시디언에 백업하도록 조치해야 한다.     
또한, 세션이 종료되는 Stop 시점에는 Session\_Handoff.md를 갱신하도록 강제할 수 있다. 쉘 스크립트 대신, 단일 턴 평가가 가능한 고속 모델(예: Claude Haiku)을 호출하는 '프롬프트 훅(Prompt Hook)'을 사용하면 인간의 스크립트 개입 없이도 지능적인 처리가 가능하다.   

JSON  
{  
  "hooks": {  
    "Stop":  
      }  
    \]  
  }  
}

이러한 자동화 메커니즘은 클로드가 단순히 코드를 생성하는 '코더'를 넘어, 프로젝트의 생명주기를 직접 관리하는 진정한 의미의 '소프트웨어 엔지니어링 에이전트'로 거듭나게 한다.

## **6\. 심화 기술: 에이전트 오프로딩 및 외부 데이터 파이프라인**

단일 클로드 코드 에이전트가 전체 SaaS 프로젝트를 감당하기에는 구조적으로 무리가 따를 수 있다. 따라서 복잡성을 격리하고 컨텍스트를 보호하기 위해 하위 에이전트(Subagents) 기능과 Model Context Protocol (MCP) 연동, 그리고 CLI 도구 확장을 접목해야 한다.

### **6.1. 하위 에이전트(Subagents)를 통한 컨텍스트 격리**

개발 도중 깊이 있는 리서치나 대규모 리팩토링 설계가 필요할 경우, 이를 메인 세션에서 진행하면 방대한 파일 열람 결과가 컨텍스트 윈도우를 순식간에 고갈시킨다. 이를 방지하기 위해 클로드 코드는 고유한 컨텍스트 윈도우를 지닌 하위 에이전트를 스폰(Spawn)하는 기능을 제공한다.     
메인 세션에서 에이전트에게 다음과 같이 지시할 수 있다.  
"/subagent 현재 src/components/ 디렉토리 내의 모든 컴포넌트를 탐색하여 결제(Payment) 도메인과 엮인 코드 간의 의존성 구조를 분석하고, 리팩토링 스펙을 마크다운으로 정리해 줘."  
하위 에이전트는 병렬적인 백그라운드 세션에서 수백 개의 파일을 읽으며(Read, Glob) 분석을 수행하고, 작업이 끝나면 오직 압축된 핵심 분석 요약본(1K 단어 내외)만을 부모 에이전트에게 반환한다. 부모 에이전트는 깨끗한 컨텍스트를 유지하면서 전달받은 스펙을 바탕으로 옵시디언의 001 \- Working Context/ 문서를 갱신한다.   

### **6.2. MCP 기반 시맨틱 탐색 (Claude Context by Zilliz)**

옵시디언의 구조화된 데이터 외에도, 거대한 SaaS 코드베이스 전체에서 의미 기반의 탐색이 필요할 때는 파일 이름이나 정규식(Grep)만으로는 한계가 명확하다. Zilliz사에서 제공하는 Claude Context MCP 플러그인을 통합하면 에이전트에게 시맨틱 코드 검색(Semantic Code Search) 능력을 부여할 수 있다.   

Bash  
\# MCP 플러그인 설치 및 인덱싱 과정  
npx @zilliz/claude-context-mcp@latest  
claude "Index this codebase"

설치가 완료되면 클로드 코드는 코드의 문맥과 의미를 이해하게 되며, "유저 권한 관리(AuthZ)를 처리하는 함수와 연관된 파일들을 찾아줘"라는 자연어 기반의 광범위한 지식 탐색을 수행하고, 도출된 맥락을 옵시디언 볼트에 문서화할 수 있다.   

### **6.3. 외부 데이터의 옵시디언 내재화 (Marmot CLI)**

SaaS 개발 시 외부 공식 문서(예: Stripe API 변경 사항, Next.js 최신 릴리즈 노트 등)를 참조해야 할 때가 많다. 이를 메인 에이전트가 웹 스크래핑하게 두면 불필요한 마크업 데이터로 인해 컨텍스트 팽창이 발생한다. 이러한 외부 데이터 수집 작업을 작은 CLI 레이어로 분리하기 위해 marmot과 같은 오픈소스 AI 파이프라인 도구를 활용한다.     
에이전트는 쉘 환경에서 스스로 외부 정보를 스크랩하고 파싱하여 곧바로 옵시디언 볼트에 기록할 수 있다.

Bash  
marmot scrape https://supabase.com/docs/guides/auth/server-side/nextjs \\  
| marmot "extract Next.js SSR middleware setup code into clean markdown" \\  
\> "docs/000 \- Rules/Supabase\_Latest\_Auth\_Pattern.md"

이 한 줄의 파이프라인을 통해 클로드는 외부에 흩어져 있던 최신 API 문서를 정제하여 프로젝트의 영구적 지식 베이스(옵시디언)로 내재화(Internalize)하며, 이후의 코드 생성 과정에서 할루시네이션 없이 정확히 해당 패턴을 차용하게 된다.   

## **7\. 시스템 통합 개발 워크플로우 (End-to-End Workflow)**

상기 서술된 모든 아키텍처와 설정을 종합하여, 인간 개발자와 클로드 코드, 그리고 옵시디언 볼트가 상호작용하며 SaaS 피처(Feature)를 완성하는 전체 생명주기 워크플로우를 요약하면 다음과 같다.

1. **지식 부트스트래핑 단계:** 개발자가 터미널에서 claude를 실행한다. .claude/settings.json의 SessionStart 훅이 발동하여 옵시디언의 Vault\_Navigation.md와 Session\_Handoff.md를 읽어 컨텍스트 창 최상단에 주입한다. 시스템은 이전 세션에서 종료된 지점을 정확히 파악하고 즉각적인 대기 상태에 돌입한다.  
2. **규칙 탐색 및 컨텍스트 로딩 단계:** 개발자가 "새로운 결제(Payment) 대시보드 컴포넌트를 작성해"라고 지시한다. 클로드는 Vibe coding(무계획적인 코드 생성)을 지양하고, CLAUDE.md의 워크플로우 지시에 따라 즉시 docs/000 \- Rules/의 기술 스택 가이드와 docs/001 \- Working Context/의 요구사항 명세서를 읽어(Read/Grep) 아키텍처 규약을 학습한다.  
3. **자율적 코드 생성 및 자동 검증 단계:** 클로드가 src/app/dashboard/payment/page.tsx에 서버 컴포넌트 코드를 작성한다. 편집이 발생한 즉시 PostToolUse 훅이 백그라운드에서 동작하여 코드 포맷팅(Prettier)과 정적 분석(ESLint)을 수행한다. 빌드 실패 시 에이전트는 하위 에이전트 스폰(Spawn) 또는 자가 반복(Loop) 루틴을 통해 로그를 분석하고 에러를 디버깅한다.  
4. **새로운 지식의 축적 및 아카이빙 단계:** 디버깅 과정에서 새롭게 발견한 엣지 케이스(Edge case)나 유용한 해결 패턴이 도출되면, 클로드 코드는 파일 입출력 도구를 사용하여 옵시디언의 docs/002 \- Daily Logs/에 타임스탬프와 함께 문서를 자동 생성하고 해결 과정을 백업한다.  
5. **세션 인계(Handoff) 및 안전 종료 단계:** 컨텍스트 윈도우가 가득 차기 직전, 또는 일과가 끝나 /stop 명령을 내릴 때, PreCompact 혹은 Stop 훅이 트리거되어 오늘 완료한 내용, 잔존하는 버그, 내일 수행해야 할 과제를 Session\_Handoff.md에 구조화하여 덮어쓴다.

## **8\. 결론 및 향후 전망**

소프트웨어 개발 프로세스에서 AI 에이전트의 도입은 단순히 타이핑 속도를 높여주는 단계를 넘어 시스템의 아키텍처를 결정하고 코드를 조율하는 '오케스트레이션(Orchestration)'의 영역으로 확장되고 있다. 그러나 클로드 코드와 같은 뛰어난 지능형 에이전트 역시 상태 비저장성과 컨텍스트 한계라는 기술적 장벽에 부딪히게 된다.     
본 보고서에서 제시한 방법론은, 클로드 코드라는 '휘발성 강한 고성능 지능'에 옵시디언(Obsidian)이라는 '구조화된 무한의 비휘발성 메모리'를 결합하는 하이브리드 지식 아키텍처를 구현한 것이다. CLAUDE.md는 시스템의 진입점으로서 메타 규칙만을 담아 점진적 정보 공개를 유도하며, 복잡한 비즈니스 스펙과 잦은 변화를 겪는 기술 스택(Next.js, Supabase)의 명세는 옵시디언 볼트 내부로 완벽히 계층화된다. 여기에 15종에 달하는 클로드 코드의 이벤트 훅(Hooks) 메커니즘과 하위 에이전트, MCP 등 심화 도구를 유기적으로 연동함으로써, 인간의 개입이 거의 없이도 에이전트가 스스로 지식을 탐색하고 축적하며, 세션을 넘나드는 연속적인 개발을 수행할 수 있는 완벽한 생태계가 구축된다.  
이러한 지식 탐색 및 축적 파이프라인의 내재화는 단기적인 기능 구현 속도 향상뿐만 아니라, 시스템 전체의 기술 부채(Tech Debt)를 방지하고 일관성 있는 복합 SaaS 애플리케이션의 확장을 담보하는 가장 근본적이고 강력한 엔지니어링 표준으로 자리매김할 것이다.

[**anthropic.com**](https://www.anthropic.com/product/claude-code)  
[Claude Code | Anthropic's agentic coding system](https://www.anthropic.com/product/claude-code)  
[새 창에서 열기](https://www.anthropic.com/product/claude-code)

[**youtube.com**](https://www.youtube.com/watch?v=PDt0mPCG6xQ)  
[Exploring Claude Code (2026): The Ultimate Guide to Anthropic’s Agentic AI Terminal](https://www.youtube.com/watch?v=PDt0mPCG6xQ)  
[새 창에서 열기](https://www.youtube.com/watch?v=PDt0mPCG6xQ)

[**medium.com**](https://medium.com/@bijit211987/the-complete-guide-to-claude-md-memory-rules-loading-and-cross-tool-compression-97cc12ed037b)  
[The Complete Guide to CLAUDE.md: Memory, Rules, Loading, and ...](https://medium.com/@bijit211987/the-complete-guide-to-claude-md-memory-rules-loading-and-cross-tool-compression-97cc12ed037b)  
[새 창에서 열기](https://medium.com/@bijit211987/the-complete-guide-to-claude-md-memory-rules-loading-and-cross-tool-compression-97cc12ed037b)

[**code.claude.com**](https://code.claude.com/docs/en/overview)  
[Claude Code overview \- Claude Code Docs](https://code.claude.com/docs/en/overview)  
[새 창에서 열기](https://code.claude.com/docs/en/overview)

[**heeki.medium.com**](https://heeki.medium.com/using-spec-driven-development-with-claude-code-4a1ebe5d9f29)  
[Using spec-driven development with Claude Code](https://heeki.medium.com/using-spec-driven-development-with-claude-code-4a1ebe5d9f29)  
[새 창에서 열기](https://heeki.medium.com/using-spec-driven-development-with-claude-code-4a1ebe5d9f29)

[**timesofindia.indiatimes.com**](https://timesofindia.indiatimes.com/technology/tech-news/almost-5-months-after-microsoft-gave-engineers-access-to-anthropics-claude-code-company-is-canceling-licenses-says-this-is-shared-accountability-to-make-/articleshow/131118119.cms)  
[Almost 5 months after Microsoft gave engineers access to Anthropic's Claude Code, company is canceling licenses; says: This is shared accountability to make](https://timesofindia.indiatimes.com/technology/tech-news/almost-5-months-after-microsoft-gave-engineers-access-to-anthropics-claude-code-company-is-canceling-licenses-says-this-is-shared-accountability-to-make-/articleshow/131118119.cms)  
[새 창에서 열기](https://timesofindia.indiatimes.com/technology/tech-news/almost-5-months-after-microsoft-gave-engineers-access-to-anthropics-claude-code-company-is-canceling-licenses-says-this-is-shared-accountability-to-make-/articleshow/131118119.cms)

[**platform.claude.com**](https://platform.claude.com/cookbook/tool-use-automatic-context-compaction)  
[Automatic context compaction | Claude Cookbook](https://platform.claude.com/cookbook/tool-use-automatic-context-compaction)  
[새 창에서 열기](https://platform.claude.com/cookbook/tool-use-automatic-context-compaction)

[**okhlopkov.com**](https://okhlopkov.com/claude-code-compaction-explained/)  
[Claude Code Compaction: How Context Compression Works (2026) \- Daniil Okhlopkov](https://okhlopkov.com/claude-code-compaction-explained/)  
[새 창에서 열기](https://okhlopkov.com/claude-code-compaction-explained/)

[**medium.com**](https://medium.com/@porter.nicholas/claude-code-post-compaction-hooks-for-context-renewal-7b616dcaa204)  
[Claude Code: Post-Compaction Hooks for Context Renewal | by Nick Porter | Medium](https://medium.com/@porter.nicholas/claude-code-post-compaction-hooks-for-context-renewal-7b616dcaa204)  
[새 창에서 열기](https://medium.com/@porter.nicholas/claude-code-post-compaction-hooks-for-context-renewal-7b616dcaa204)

[**code.claude.com**](https://code.claude.com/docs/en/memory)  
[How Claude remembers your project \- Claude Code Docs](https://code.claude.com/docs/en/memory)  
[새 창에서 열기](https://code.claude.com/docs/en/memory)

[**claudefa.st**](https://claudefa.st/blog/guide/mechanics/auto-memory)  
[Claude Code Auto Memory: How Your AI Learns Your Project](https://claudefa.st/blog/guide/mechanics/auto-memory)  
[새 창에서 열기](https://claudefa.st/blog/guide/mechanics/auto-memory)

[**forum.obsidian.md**](https://forum.obsidian.md/t/design-your-vault-for-ai-orientation-not-just-human-navigation/112010)  
[Design your vault for AI orientation, not just human navigation ...](https://forum.obsidian.md/t/design-your-vault-for-ai-orientation-not-just-human-navigation/112010)  
[새 창에서 열기](https://forum.obsidian.md/t/design-your-vault-for-ai-orientation-not-just-human-navigation/112010)

[**reddit.com**](https://www.reddit.com/r/hermesagent/comments/1stz6gd/how_i_use_obsidian_as_the_longterm_memory/)  
[How I use Obsidian as the long-term memory backbone for my AI assistant : r/hermesagent](https://www.reddit.com/r/hermesagent/comments/1stz6gd/how_i_use_obsidian_as_the_longterm_memory/)  
[새 창에서 열기](https://www.reddit.com/r/hermesagent/comments/1stz6gd/how_i_use_obsidian_as_the_longterm_memory/)

[**code.claude.com**](https://code.claude.com/docs/en/hooks-guide)  
[Automate workflows with hooks \- Claude Code Docs](https://code.claude.com/docs/en/hooks-guide)  
[새 창에서 열기](https://code.claude.com/docs/en/hooks-guide)

[**mindstudio.ai**](https://www.mindstudio.ai/blog/what-is-claude-code-auto-memory)  
[What Is Claude Code Auto-Memory? How Your AI Agent Learns From Its Own Mistakes](https://www.mindstudio.ai/blog/what-is-claude-code-auto-memory)  
[새 창에서 열기](https://www.mindstudio.ai/blog/what-is-claude-code-auto-memory)

[**milvus.io**](https://milvus.io/blog/claude-code-memory-memsearch.md#:~:text=CLAUDE.md%20is%20a%20static,stale%20memories%20in%20the%20background.)  
[새 창에서 열기](https://milvus.io/blog/claude-code-memory-memsearch.md#:~:text=CLAUDE.md%20is%20a%20static,stale%20memories%20in%20the%20background.)

[**milvus.io**](https://milvus.io/blog/claude-code-memory-memsearch.md)  
[Claude Code Memory System Explained: 4 Layers, 5 Limits, and a Fix \- Milvus Blog](https://milvus.io/blog/claude-code-memory-memsearch.md)  
[새 창에서 열기](https://milvus.io/blog/claude-code-memory-memsearch.md)

[**platform.claude.com**](https://platform.claude.com/cookbook/tool-use-context-engineering-context-engineering-tools)  
[Context engineering: memory, compaction, and tool clearing | Claude Cookbook](https://platform.claude.com/cookbook/tool-use-context-engineering-context-engineering-tools)  
[새 창에서 열기](https://platform.claude.com/cookbook/tool-use-context-engineering-context-engineering-tools)

[**platform.claude.com**](https://platform.claude.com/docs/en/build-with-claude/compaction)  
[Compaction \- Claude API Docs](https://platform.claude.com/docs/en/build-with-claude/compaction)  
[새 창에서 열기](https://platform.claude.com/docs/en/build-with-claude/compaction)

[**news.ycombinator.com**](https://news.ycombinator.com/item?id=46102048)  
[Claude often ignores CLAUDE.md \> The more information you have in the file tha... | Hacker News](https://news.ycombinator.com/item?id=46102048)  
[새 창에서 열기](https://news.ycombinator.com/item?id=46102048)

[**code.claude.com**](https://code.claude.com/docs/en/best-practices)  
[Best practices for Claude Code \- Claude Code Docs](https://code.claude.com/docs/en/best-practices)  
[새 창에서 열기](https://code.claude.com/docs/en/best-practices)

[**humanlayer.dev**](https://www.humanlayer.dev/blog/writing-a-good-claude-md)  
[Writing a good CLAUDE.md | HumanLayer Blog](https://www.humanlayer.dev/blog/writing-a-good-claude-md)  
[새 창에서 열기](https://www.humanlayer.dev/blog/writing-a-good-claude-md)

[**code.claude.com**](https://code.claude.com/docs/en/settings)  
[Claude Code settings \- Claude Code Docs](https://code.claude.com/docs/en/settings)  
[새 창에서 열기](https://code.claude.com/docs/en/settings)

[**code.claude.com**](https://code.claude.com/docs/en/hooks)  
[Hooks reference \- Claude Code Docs](https://code.claude.com/docs/en/hooks)  
[새 창에서 열기](https://code.claude.com/docs/en/hooks)

[**reddit.com**](https://www.reddit.com/r/ClaudeAI/comments/1l30p37/i_built_a_free_nextjs_supabase_starter/)  
[I built a free nextjs \+ supabase starter specifically for Claude Code and AI apps \- Reddit](https://www.reddit.com/r/ClaudeAI/comments/1l30p37/i_built_a_free_nextjs_supabase_starter/)  
[새 창에서 열기](https://www.reddit.com/r/ClaudeAI/comments/1l30p37/i_built_a_free_nextjs_supabase_starter/)

[**medium.com**](https://medium.com/@simonsruggi/next-store-a-minimal-e-commerce-template-using-nextjs-stripe-and-supabase-d3ef3e994063)  
[Next Store: A Minimal E-Commerce Template Using NextJS, Stripe](https://medium.com/@simonsruggi/next-store-a-minimal-e-commerce-template-using-nextjs-stripe-and-supabase-d3ef3e994063)  
[새 창에서 열기](https://medium.com/@simonsruggi/next-store-a-minimal-e-commerce-template-using-nextjs-stripe-and-supabase-d3ef3e994063)

[**github.com**](https://github.com/li-zhixin/claude-ignore)  
[li-zhixin/claude-ignore: A Claude Code PreToolUse hook that prevents Claude from reading files that match patterns in .claudeignore files, similar to how .gitignore works. \- GitHub](https://github.com/li-zhixin/claude-ignore)  
[새 창에서 열기](https://github.com/li-zhixin/claude-ignore)

[**reddit.com**](https://www.reddit.com/r/nextjs/comments/175awkb/struggling_with_middleware_in_nextjs_supbase/)  
[struggling with middleware in NextJS \- Supbase \- Reddit](https://www.reddit.com/r/nextjs/comments/175awkb/struggling_with_middleware_in_nextjs_supbase/)  
[새 창에서 열기](https://www.reddit.com/r/nextjs/comments/175awkb/struggling_with_middleware_in_nextjs_supbase/)

[**supabase.com**](https://supabase.com/docs/guides/auth/server-side)  
[Supabase Docs \- Server-Side Rendering](https://supabase.com/docs/guides/auth/server-side)  
[새 창에서 열기](https://supabase.com/docs/guides/auth/server-side)

[**vercel.com**](https://vercel.com/templates/next.js/supabase)  
[Supabase & Next.js App Router Starter Template for Auth \- Vercel](https://vercel.com/templates/next.js/supabase)  
[새 창에서 열기](https://vercel.com/templates/next.js/supabase)

[**medium.com**](https://medium.com/becoming-for-better/taming-claude-code-a-guide-to-claude-md-and-hooks-ed059879991c)  
[Taming Claude Code: A Guide to CLAUDE.md and Hooks | by Mustafa Morbel \- Medium](https://medium.com/becoming-for-better/taming-claude-code-a-guide-to-claude-md-and-hooks-ed059879991c)  
[새 창에서 열기](https://medium.com/becoming-for-better/taming-claude-code-a-guide-to-claude-md-and-hooks-ed059879991c)

[**supabase.com**](https://supabase.com/docs/guides/auth/server-side/creating-a-client)  
[Creating a Supabase client for SSR](https://supabase.com/docs/guides/auth/server-side/creating-a-client)  
[새 창에서 열기](https://supabase.com/docs/guides/auth/server-side/creating-a-client)

[**supabase.com**](https://supabase.com/docs/guides/getting-started/tutorials/with-nextjs)  
[Build a User Management App with Next.js | Supabase Docs](https://supabase.com/docs/guides/getting-started/tutorials/with-nextjs)  
[새 창에서 열기](https://supabase.com/docs/guides/getting-started/tutorials/with-nextjs)

[**reddit.com**](https://www.reddit.com/r/Supabase/comments/17wjtie/nextjs_supabasessr_oauth_am_i_doing_this_right/)  
[Next.js, Supabase/ssr & OAuth. Am I Doing This Right? \- Reddit](https://www.reddit.com/r/Supabase/comments/17wjtie/nextjs_supabasessr_oauth_am_i_doing_this_right/)  
[새 창에서 열기](https://www.reddit.com/r/Supabase/comments/17wjtie/nextjs_supabasessr_oauth_am_i_doing_this_right/)

[**youtube.com**](https://www.youtube.com/watch?v=yLJIrvYapA0)  
[Thats the way\! How to: Supabase SSR Auth in Nextjs 14 \- YouTube](https://www.youtube.com/watch?v=yLJIrvYapA0)  
[새 창에서 열기](https://www.youtube.com/watch?v=yLJIrvYapA0)

[**github.com**](https://github.com/orgs/supabase/discussions/27235)  
[Supabase Middleware and Next js Internationalization with @supabase/ssr \#27235 \- GitHub](https://github.com/orgs/supabase/discussions/27235)  
[새 창에서 열기](https://github.com/orgs/supabase/discussions/27235)

[**ksred.com**](https://www.ksred.com/claude-code-hooks-a-complete-guide-to-automating-your-ai-coding-workflow/)  
[Claude Code Hooks: Automate Your AI Coding Workflow \- Kyle Redelinghuys](https://www.ksred.com/claude-code-hooks-a-complete-guide-to-automating-your-ai-coding-workflow/)  
[새 창에서 열기](https://www.ksred.com/claude-code-hooks-a-complete-guide-to-automating-your-ai-coding-workflow/)

[**claudefa.st**](https://claudefa.st/blog/tools/hooks/hooks-guide)  
[Claude Code Hooks: Complete Guide to All 12 Lifecycle Events](https://claudefa.st/blog/tools/hooks/hooks-guide)  
[새 창에서 열기](https://claudefa.st/blog/tools/hooks/hooks-guide)

[**github.com**](https://github.com/affaan-m/everything-claude-code/blob/main/hooks/hooks.json)  
[hooks.json \- affaan-m/everything-claude-code \- GitHub](https://github.com/affaan-m/everything-claude-code/blob/main/hooks/hooks.json)  
[새 창에서 열기](https://github.com/affaan-m/everything-claude-code/blob/main/hooks/hooks.json)

[**code.claude.com**](https://code.claude.com/docs/en/context-window)  
[Explore the context window \- Claude Code Docs](https://code.claude.com/docs/en/context-window)  
[새 창에서 열기](https://code.claude.com/docs/en/context-window)

[**code.claude.com**](https://code.claude.com/docs/en/features-overview)  
[Extend Claude Code \- Claude Code Docs](https://code.claude.com/docs/en/features-overview)  
[새 창에서 열기](https://code.claude.com/docs/en/features-overview)

[**o-mega.ai**](https://o-mega.ai/articles/top-100-skills-and-tools-for-openclaw-may-2026)  
[Top 100 OpenClaw Skills & Tools (May 2026\) | Articles \- O-mega.ai](https://o-mega.ai/articles/top-100-skills-and-tools-for-openclaw-may-2026)  
[새 창에서 열기](https://o-mega.ai/articles/top-100-skills-and-tools-for-openclaw-may-2026)

[**github.com**](https://github.com/zilliztech/claude-context)  
[zilliztech/claude-context: Code search MCP for Claude Code. Make entire codebase the context for any coding agent. \- GitHub](https://github.com/zilliztech/claude-context)  
[새 창에서 열기](https://github.com/zilliztech/claude-context)

[**reddit.com**](https://www.reddit.com/r/ClaudeCode/comments/1tb5ddn/built_a_cli_to_use_with_claude_code_for_fetching/)  
[Built a CLI to use with Claude Code for fetching external context, and accessing more models for skills composition \- Reddit](https://www.reddit.com/r/ClaudeCode/comments/1tb5ddn/built_a_cli_to_use_with_claude_code_for_fetching/)  
[새 창에서 열기](https://www.reddit.com/r/ClaudeCode/comments/1tb5ddn/built_a_cli_to_use_with_claude_code_for_fetching/)

[새 창에서 열기](https://www.anthropic.com/constitution)

[새 창에서 열기](https://platform.claude.com/docs/en/home)

[새 창에서 열기](https://www.anthropic.com/learn/build-with-claude?goal=grow-revenue)

[새 창에서 열기](https://platform.claude.com/docs/en/build-with-claude/context-editing)

[새 창에서 열기](https://www.youtube.com/watch?v=e_D9M_MJ9Hs)

[새 창에서 열기](https://code.claude.com/docs/en/cli-reference)

[새 창에서 열기](https://github.com/github/spec-kit)

[새 창에서 열기](https://github.com/anthropics/claude-code/issues/579)

[새 창에서 열기](https://medium.com/kantega/constraining-claude-514a7eed9fc7)

[새 창에서 열기](https://www.reddit.com/r/ClaudeCode/comments/1oki5la/how_do_you_deal_w_gitignore_and_claude_code/)

[새 창에서 열기](https://code.claude.com/docs/en/claude-directory)

[새 창에서 열기](https://www.reddit.com/r/ClaudeAI/comments/1r66oo0/how_i_structure_claude_code_projects_claudemd/)

[새 창에서 열기](https://www.youtube.com/watch?v=UXJA22y4C80)

[새 창에서 열기](https://forum.obsidian.md/top?page=10&per_page=50)

[새 창에서 열기](https://forum.obsidian.md/c/knowledge-management/6)

[새 창에서 열기](https://medium.com/a-voice-in-the-conversation/event-nodes-in-obsidian-pkm-4e58ef2e915a)

[새 창에서 열기](https://skillsllm.com/skill/arscontexta)

[새 창에서 열기](https://medium.com/@brickbarnblog/our-ai-overlords-4f301cc42403)

[새 창에서 열기](https://code.claude.com/docs/en/how-claude-code-works)

[새 창에서 열기](https://code.claude.com/docs/en/common-workflows)

[새 창에서 열기](https://github.com/disler/claude-code-hooks-mastery)

[새 창에서 열기](https://gist.github.com/mculp/c082bd1e5a439410158974de90c89db7)

[새 창에서 열기](https://blog.vincentqiao.com/en/posts/claude-code-settings-hooks/)

[새 창에서 열기](https://www.reddit.com/r/ClaudeAI/comments/1rxu41b/claude_code_hooks_all_23_explained_and_implemented/)

[새 창에서 열기](https://github.com/davila7/claude-code-templates)

[새 창에서 열기](https://github.com/orgs/supabase/discussions/21303)

[새 창에서 열기](https://lobehub.com/mcp/darraghh1-my-claude-setup)

[새 창에서 열기](https://github.com/gvago/nextjs-supabase-ai-template)

[새 창에서 열기](https://supalaunch.com/)

[새 창에서 열기](https://www.reddit.com/r/ClaudeAI/comments/1r6j36u/claude_codes_auto_memory_is_so_good_make_sure_you/)

