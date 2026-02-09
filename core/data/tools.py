"""
AI 도구 가이드 데이터
2026년 2월 기준 최신 정보
"""

TOOLS_DATA = [
    # ========== AI 비서 (AI Assistants) ==========
    {
        'id': 'chatgpt',
        'name': 'ChatGPT',
        'category': 'ai',
        'icon': '<i class="fa-solid fa-robot text-green-500"></i>',
        'desc': '만능 해결사. 가정통신문 초안, 수업 아이디어, 고민 상담 등 텍스트로 하는 모든 일의 기본입니다.',
        'summary': 'Canvas 기능이 무료로 풀렸어요! 글쓰기나 코딩할 때 별도 창에서 수정이 가능해져서 훨씬 편합니다.',
        'details': ['Canvas 기능 전면 무료화', 'SearchGPT 통합으로 실시간 검색 강화', '기억(Memory) 용량 2배 증가'],
        'url': 'https://chat.openai.com',
        'last_updated': '2026-01-15'
    },
    {
        'id': 'claude',
        'name': 'Claude',
        'category': 'ai',
        'icon': '<i class="fa-solid fa-brain text-orange-500"></i>',
        'desc': '글쓰기와 코딩의 신. ChatGPT보다 한국어 문장이 훨씬 자연스럽고, 긴 문서를 분석할 때 탁월합니다.',
        'summary': '코딩 실력이 비약적으로 상승한 3.7 버전이 나왔습니다.',
        'details': ['Claude 3.7 Sonnet 모델 출시', 'Artifacts 기능으로 결과물 미리보기', '200K 토큰 컨텍스트 윈도우'],
        'url': 'https://claude.ai',
        'last_updated': '2026-01-20'
    },
    {
        'id': 'gemini',
        'name': 'Gemini',
        'category': 'ai',
        'icon': '<i class="fa-solid fa-star text-blue-500"></i>',
        'desc': '구글 찐친. 구글 문서, 스프레드시트, 유튜브 내용을 분석하거나 요약해야 할 때 가장 강력합니다.',
        'summary': '구글 워크스페이스 연동성이 강화되었습니다.',
        'details': ['Gemini 2.5 Flash 업데이트', 'Google Sheets 자동 시각화 기능', 'YouTube 영상 요약 강화'],
        'url': 'https://gemini.google.com',
        'last_updated': '2026-02-01'
    },
    {
        'id': 'perplexity',
        'name': 'Perplexity',
        'category': 'ai',
        'icon': '<i class="fa-solid fa-magnifying-glass text-teal-500"></i>',
        'desc': '거짓말 안 하는 검색 AI. 논문, 뉴스 기사 등 "출처"가 중요한 자료를 찾을 때 네이버/구글 대신 쓰세요.',
        'summary': 'Deep Research 모드가 추가되었습니다.',
        'details': ['Deep Research 기능 베타', 'Pro Search 속도 개선', '실시간 뉴스 검색 강화'],
        'url': 'https://perplexity.ai',
        'last_updated': '2026-01-10'
    },
    {
        'id': 'copilot',
        'name': 'Microsoft Copilot',
        'category': 'ai',
        'icon': '<i class="fa-brands fa-microsoft text-blue-600"></i>',
        'desc': 'MS Office의 AI 비서. 워드, 엑셀, 파워포인트에서 바로 AI를 불러 문서 작업을 자동화할 수 있습니다.',
        'summary': 'Office 365 통합이 더욱 강화되었습니다.',
        'details': ['PowerPoint Designer AI 강화', 'Excel 수식 자동 생성', 'Word 문서 요약 기능'],
        'url': 'https://copilot.microsoft.com',
        'last_updated': '2025-12-20'
    },
    {
        'id': 'poe',
        'name': 'Poe',
        'category': 'ai',
        'icon': '<i class="fa-solid fa-comments text-purple-500"></i>',
        'desc': '여러 AI를 한 곳에서. ChatGPT, Claude, Gemini 등을 앱 하나로 비교하며 사용할 수 있습니다.',
        'summary': '커스텀 봇 생성 기능이 무료로 제공됩니다.',
        'details': ['무료 커스텀 봇 생성', '다중 AI 모델 동시 비교', '모바일 앱 최적화'],
        'url': 'https://poe.com',
        'last_updated': '2025-11-15'
    },
    {
        'id': 'deepl',
        'name': 'DeepL',
        'category': 'ai',
        'icon': '<i class="fa-solid fa-language text-indigo-500"></i>',
        'desc': '번역의 끝판왕. 구글 번역보다 훨씬 자연스러운 번역을 제공합니다. 영어 논문이나 외국 자료 읽을 때 필수!',
        'summary': '한국어 번역 품질이 대폭 향상되었습니다.',
        'details': ['한국어 번역 정확도 30% 향상', '문서 번역 속도 개선', 'PDF 직접 번역 지원'],
        'url': 'https://deepl.com',
        'last_updated': '2026-01-05'
    },
    {
        'id': 'notionai',
        'name': 'Notion AI',
        'category': 'ai',
        'icon': '<i class="fa-solid fa-note-sticky text-black"></i>',
        'desc': '노션 안에서 바로 쓰는 AI. 회의록 정리, 아이디어 확장, 문서 요약을 노션 페이지 안에서 즉시 처리합니다.',
        'summary': 'Q&A 기능으로 노션 DB 검색이 가능해졌습니다.',
        'details': ['Notion DB 자연어 검색', '자동 태그 생성', '템플릿 AI 추천'],
        'url': 'https://notion.so/product/ai',
        'last_updated': '2025-12-10'
    },
    {
        'id': 'wrtn',
        'name': 'WRTN (뤼튼)',
        'category': 'ai',
        'icon': '<i class="fa-solid fa-wand-magic-sparkles text-pink-500"></i>',
        'desc': '한국형 AI 플랫폼. 한국어에 특화되어 있고, 다양한 AI 도구를 무료로 사용할 수 있습니다.',
        'summary': '교육용 템플릿이 대폭 추가되었습니다.',
        'details': ['교육 전용 템플릿 50+ 추가', '한국어 맞춤법 검사 강화', '무료 크레딧 확대'],
        'url': 'https://wrtn.ai',
        'last_updated': '2026-02-05'
    },

    # ========== 코딩 & 개발 (Coding & Development) ==========
    {
        'id': 'cursor',
        'name': 'Cursor',
        'category': 'dev',
        'icon': '<i class="fa-solid fa-terminal text-gray-700"></i>',
        'desc': 'AI가 탑재된 코딩 편집기. "이거 만들어줘"라고 치면 코드를 다 짜줍니다. 바이브 코딩의 핵심 툴!',
        'summary': 'Composer 기능이 더 강력해졌습니다.',
        'details': ['Composer 다중 파일 편집 기능', '자연어 터미널 명령 지원', 'Claude 3.7 통합'],
        'url': 'https://cursor.sh',
        'last_updated': '2026-02-08'
    },
    {
        'id': 'github-copilot',
        'name': 'GitHub Copilot',
        'category': 'dev',
        'icon': '<i class="fa-brands fa-github text-black"></i>',
        'desc': 'VS Code 안에서 쓰는 AI 코딩 도우미. 코드 자동완성부터 버그 수정까지 실시간으로 도와줍니다.',
        'summary': 'Copilot Chat이 더욱 똑똑해졌습니다.',
        'details': ['Copilot Chat 업그레이드', '코드 리뷰 자동화', '보안 취약점 탐지'],
        'url': 'https://github.com/features/copilot',
        'last_updated': '2026-01-25'
    },
    {
        'id': 'v0',
        'name': 'v0.dev',
        'category': 'dev',
        'icon': '<i class="fa-solid fa-shapes text-gray-700"></i>',
        'desc': '디자인 복사기. 마음에 드는 사이트 캡처해서 올리면 똑같은 모양의 코드를 만들어줍니다.',
        'summary': '피그마(Figma) 디자인 변환 정확도 향상.',
        'details': ['Figma to React 변환 개선', 'Tailwind CSS 최적화', 'shadcn/ui 통합'],
        'url': 'https://v0.dev',
        'last_updated': '2026-02-01'
    },
    {
        'id': 'replit',
        'name': 'Replit',
        'category': 'dev',
        'icon': '<i class="fa-solid fa-ghost text-orange-500"></i>',
        'desc': '설치 없는 코딩. 복잡한 세팅 없이 인터넷 창에서 바로 코딩하고 결과물을 공유할 수 있습니다.',
        'summary': 'Replit Agent가 정식 출시되었습니다.',
        'details': ['Replit Agent 정식 런칭', '모바일 앱 코딩 지원', '실시간 협업 강화'],
        'url': 'https://replit.com',
        'last_updated': '2026-01-18'
    },
    {
        'id': 'supabase',
        'name': 'Supabase',
        'category': 'dev',
        'icon': '<i class="fa-solid fa-database text-green-600"></i>',
        'desc': '오픈소스 Firebase 대안. 데이터베이스, 인증, 스토리지를 한 번에 제공하는 백엔드 서비스입니다.',
        'summary': 'Edge Functions와 Realtime 기능이 더욱 강력해졌습니다.',
        'details': ['Postgres 기반 실시간 DB', 'Edge Functions 성능 개선', '무료 티어 확대'],
        'url': 'https://supabase.com',
        'last_updated': '2026-02-09'
    },
    {
        'id': 'railway',
        'name': 'Railway',
        'category': 'dev',
        'icon': '<i class="fa-solid fa-train text-purple-600"></i>',
        'desc': '배포의 혁명. Git에 푸시만 하면 자동으로 서버에 배포됩니다. Heroku보다 빠르고 저렴합니다.',
        'summary': '무료 티어가 개선되고 배포 속도가 2배 빨라졌습니다.',
        'details': ['배포 속도 2배 향상', '무료 500시간 제공', 'PostgreSQL 자동 백업'],
        'url': 'https://railway.app',
        'last_updated': '2026-02-09'
    },

    # ========== 디자인 & 협업 (Design & Collaboration) ==========
    {
        'id': 'figma',
        'name': 'Figma',
        'category': 'design',
        'icon': '<i class="fa-brands fa-figma text-purple-600"></i>',
        'desc': 'UI/UX 디자인 도구. 웹사이트나 앱 화면을 디자인하고 프로토타입을 만들 수 있습니다. 실시간 협업이 가능해 팀 작업에 최적화되어 있습니다.',
        'summary': 'AI 디자인 제안 기능과 Dev Mode가 더욱 강력해졌습니다.',
        'details': ['AI 디자인 자동 생성', 'Dev Mode로 개발자 협업 강화', '실시간 멀티플레이어 편집'],
        'url': 'https://figma.com',
        'last_updated': '2026-02-09'
    },
    {
        'id': 'canva',
        'name': 'Canva',
        'category': 'design',
        'icon': '<i class="fa-solid fa-palette text-cyan-500"></i>',
        'desc': '디자인 만능 도구. 포스터, 인포그래픽, 프레젠테이션을 템플릿 기반으로 쉽게 만들 수 있습니다.',
        'summary': 'AI 디자인 생성 기능이 대폭 강화되었습니다.',
        'details': ['Magic Design (AI 자동 디자인)', 'Magic Eraser (배경 제거)', '무료 템플릿 10만+'],
        'url': 'https://canva.com',
        'last_updated': '2026-01-12'
    },

    # ========== 모니터링 & 운영 (Ops & Monitoring) ==========
    {
        'id': 'sentry',
        'name': 'Sentry',
        'category': 'ops',
        'icon': '<i class="fa-solid fa-shield-halved text-purple-700"></i>',
        'desc': '실시간 오류 추적 도구. 서비스에서 발생하는 에러를 실시간으로 감지하고, 어디서 왜 발생했는지 정확히 알려줍니다.',
        'summary': 'AI 기반 오류 분석과 성능 모니터링이 추가되었습니다.',
        'details': ['AI 기반 오류 우선순위 분석', '성능 병목 지점 자동 탐지', 'Slack/Discord 실시간 알림'],
        'url': 'https://sentry.io',
        'last_updated': '2026-02-09'
    },

    # ========== 생산성 도구 (Productivity) ==========
    {
        'id': 'obsidian',
        'name': 'Obsidian',
        'category': 'work',
        'icon': '<i class="fa-solid fa-gem text-purple-600"></i>',
        'desc': '제2의 뇌. 노트들을 서로 연결하여 지식 네트워크를 만들 수 있는 메모 앱입니다.',
        'summary': '로컬 저장으로 데이터 소유권을 보장합니다.',
        'details': ['마크다운 기반', '그래프 뷰로 노트 연결 시각화', '플러그인 생태계'],
        'url': 'https://obsidian.md',
        'last_updated': '2025-11-20'
    },
    {
        'id': 'notion',
        'name': 'Notion',
        'category': 'work',
        'icon': '<i class="fa-solid fa-note-sticky text-black"></i>',
        'desc': '올인원 워크스페이스. 문서, 데이터베이스, 캘린더, 칸반보드를 하나의 공간에서 관리할 수 있습니다.',
        'summary': 'Notion AI와 자동화 기능이 강화되었습니다.',
        'details': ['AI 기반 문서 작성', '데이터베이스 자동화', '무료 개인 플랜'],
        'url': 'https://notion.so',
        'last_updated': '2026-01-30'
    },

    # ========== 창작 & 예술 (Creative Arts) ==========
    {
        'id': 'midjourney',
        'name': 'Midjourney',
        'category': 'art',
        'icon': '<i class="fa-solid fa-image text-purple-500"></i>',
        'desc': 'AI 이미지 생성의 끝판왕. 텍스트만 입력하면 예술 작품 수준의 이미지를 만들어줍니다.',
        'summary': 'V7 모델로 사실성과 디테일이 극대화되었습니다.',
        'details': ['Midjourney V7 출시', '초고해상도 업스케일', '스타일 일관성 유지'],
        'url': 'https://midjourney.com',
        'last_updated': '2026-01-22'
    },
    {
        'id': 'runway',
        'name': 'Runway',
        'category': 'art',
        'icon': '<i class="fa-solid fa-video text-green-500"></i>',
        'desc': 'AI 영상 생성 도구. 텍스트나 이미지를 입력하면 짧은 영상 클립을 만들어줍니다.',
        'summary': 'Gen-3 Alpha가 출시되어 영상 품질이 비약적으로 향상되었습니다.',
        'details': ['Gen-3 Alpha 출시', '16초 영상 생성', '모션 브러시 기능'],
        'url': 'https://runwayml.com',
        'last_updated': '2026-01-28'
    },
    {
        'id': 'elevenlabs',
        'name': 'ElevenLabs',
        'category': 'art',
        'icon': '<i class="fa-solid fa-microphone text-blue-600"></i>',
        'desc': 'AI 음성 생성. 텍스트를 입력하면 사람처럼 자연스러운 음성으로 읽어줍니다.',
        'summary': '한국어 음성 품질이 크게 향상되었습니다.',
        'details': ['한국어 음성 지원', '감정 표현 가능', '음성 복제 기능'],
        'url': 'https://elevenlabs.io',
        'last_updated': '2026-02-03'
    },
]
