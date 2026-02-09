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
        'desc': '수업의 든든한 조력자. 복잡한 가정통신문 초안부터 아이들을 위한 창의적인 수업 아이디어, 행정 업무 간소화까지 텍스트로 된 모든 고민을 함께 나누는 만능 비서입니다.',
        'summary': '이제 Canvas 기능이 전면 무료로 풀려 글쓰기나 코딩 수업 중에 실시간 수정이 훨씬 쉬워졌습니다!',
        'details': [
            'Canvas 기능: 별도 창에서 문서나 코드를 띄워두고 아이들과 함께 직접 수정 가능',
            'SearchGPT 통합: 수업용 최신 뉴스나 통계 자료를 실시간으로 정확하게 검색',
            '선생님 맞춤형 기억: 이전 상담 내용이나 수업 방식을 기억해 문맥에 맞는 제안 제공'
        ],
        'url': 'https://chat.openai.com',
        'last_updated': '2026-02-09'
    },
    {
        'id': 'claude',
        'name': 'Claude',
        'category': 'ai',
        'icon': '<i class="fa-solid fa-brain text-orange-500"></i>',
        'desc': '문학적 감수성과 논리를 겸비한 작가형 AI. ChatGPT보다 훨씬 한국어 문장이 매끄러워 학습지 제작이나 교재 요약 시 아이들이 읽기 좋은 자연스러운 글을 만들어줍니다.',
        'summary': '코딩과 논리적 사고력이 압도적인 3.7 버전이 출시되어 복잡한 문제 풀이도 척척 해냅니다.',
        'details': [
            'Artifacts 환경: 코딩이나 웹 디자인 결과물을 창 우측에서 즉시 확인하며 수업 진행',
            '200K 방대한 컨텍스트: PDF 수십 페이지 분량의 논문을 한 번에 넣고 요약 가능',
            '안전성 중점 설계: 학생들에게 유해한 내용을 철저히 걸러내는 윤리적인 응답'
        ],
        'url': 'https://claude.ai',
        'last_updated': '2026-02-09'
    },
    {
        'id': 'gemini',
        'name': 'Gemini',
        'category': 'ai',
        'icon': '<i class="fa-solid fa-star text-blue-500"></i>',
        'desc': '구글 생태계의 끝판왕. 구글 문서, 스프레드시트, 유튜브와 완벽하게 연동됩니다. 시각 자료가 많은 유튜브 영상을 분석해 학습용 자료로 변환할 때 최고의 효율을 보여줍니다.',
        'summary': '구글 워크스페이스(Workspace) 연동성이 극대화되어 문서 작업 환경이 완전히 바뀌었습니다.',
        'details': [
            '유튜브 영상 리서치: 긴 강의 영상의 핵심 내용을 초 단위로 요약하고 퀴즈 제작',
            'Google Sheets 시각화: 복잡한 학생 성적 데이터를 차트와 그래프로 즉시 변환',
            '실시간 협업: 구글 문서(Docs) 내에서 바로 Gemini를 호출해 글쓰기 보조'
        ],
        'url': 'https://gemini.google.com',
        'last_updated': '2026-02-09'
    },
    {
        'id': 'perplexity',
        'name': 'Perplexity',
        'category': 'ai',
        'icon': '<i class="fa-solid fa-magnifying-glass text-teal-500"></i>',
        'desc': '거짓말하지 않는 검색 AI. 환각 증상(Hallucination)이 거의 없이 모든 답변에 출처를 각주로 달아줍니다. 논문 지도나 전문 지식을 가공해야 할 때 네이버 검색보다 훨씬 강력합니다.',
        'summary': 'Deep Research 모드 출시로, 단순 검색을 넘어 심층 리서치 보고서를 스스로 작성합니다.',
        'details': [
            '투명한 정보 출처: 답변마다 링크된 출처를 클릭해 원본 데이터의 신뢰도 즉시 확인',
            'Deep Research: 복잡한 주제에 대해 스스로 수십 개의 사이트를 뒤져 종합 보고서 작성',
            'Pro Search: 질문의 의도를 파악해 후속 질문을 던지며 최적의 결과 도출'
        ],
        'url': 'https://perplexity.ai',
        'last_updated': '2026-02-09'
    },
    {
        'id': 'copilot',
        'name': 'Microsoft Copilot',
        'category': 'ai',
        'icon': '<i class="fa-brands fa-microsoft text-blue-600"></i>',
        'desc': '선생님의 오피스 도우미. 워드, 엑셀, 파워포인트 안에 AI가 들어왔습니다. 텍스트만 입력하면 멋진 발표용 슬라이드를 뚝딱 만들어 주어 자료 제작 시간을 획기적으로 줄여줍니다.',
        'summary': 'Office 365 내 모든 도구에서 자연어로 명령을 수행하는 진정한 업무 비서가 되었습니다.',
        'details': [
            'PPT 자동 생성: 주제만 던져주면 목차부터 디자인, 내용까지 포함된 슬라이드 구성',
            'Excel 데이터 분석: 함수를 몰라도 "이 데이터에서 평균 이상의 학생만 뽑아줘"라고 명령',
            '이미지 생성 탑재: DALL-E 기반의 고화질 이미지를 문서 작업 도중 바로 생성'
        ],
        'url': 'https://copilot.microsoft.com',
        'last_updated': '2026-02-09'
    },
    {
        'id': 'deepl',
        'name': 'DeepL',
        'category': 'ai',
        'icon': '<i class="fa-solid fa-language text-indigo-500"></i>',
        'desc': '언어의 장벽을 허무는 마법. 직역이 아닌 문맥을 파악한 번역을 제공하여 외국어 논문이나 해외 교육 사례를 읽을 때 "한국 사람이 쓴 것 같은" 매끄러운 번역 결과를 보여줍니다.',
        'summary': '한국어의 뉘앙스를 더욱 정밀하게 파악하도록 엔진이 대폭 업그레이드되었습니다.',
        'details': [
            '압도적인 문맥 이해: 존댓말과 반말, 학술적 어조 등을 상황에 맞게 자동으로 조절',
            'PDF/PPT 통번역: 디자인 레이아웃을 그대로 유지한 채 텍스트만 깔끔하게 번역',
            'DeepL Write: 번역을 넘어 내가 쓴 문장을 더 프로페셔널하고 자연스럽게 교정'
        ],
        'url': 'https://deepl.com',
        'last_updated': '2026-02-09'
    },
    {
        'id': 'wrtn',
        'name': 'WRTN (뤼튼)',
        'category': 'ai',
        'icon': '<i class="fa-solid fa-wand-magic-sparkles text-pink-500"></i>',
        'desc': '한국 선생님을 위한 AI 종합 선물 세트. 한국어에 특화된 모델설계는 물론, 교육용 프롬프트 템플릿이 풍부하게 제공되어 AI가 낯선 선생님들도 쉽게 시작할 수 있습니다.',
        'summary': '교육 현장에 특화된 전용 템플릿과 무료 크레딧 혜택이 더욱 확대되었습니다.',
        'details': [
            '교육용 템플릿: 생기부 기초 자료, 창체 아이디어, 독서 퀴즈 등 50종 이상의 템플릿',
            '국내외 최신 모델 무료: GPT-4o, Claude 3.5 등을 로그인 한 번으로 무료 교차 사용',
            '커뮤니티 연동: 다른 선생님들이 만든 유용한 AI 봇을 가져와 내 수업에 바로 적용'
        ],
        'url': 'https://wrtn.ai',
        'last_updated': '2026-02-09'
    },

    # ========== 코딩 & 개발 (Coding & Development) ==========
    {
        'id': 'cursor',
        'name': 'Cursor',
        'category': 'dev',
        'icon': '<i class="fa-solid fa-terminal text-gray-700"></i>',
        'desc': '코딩계의 혁명. 코드 한 줄 몰라도 "이런 웹사이트 만들어줘"라고 말하면 AI가 파일 구조부터 코드까지 전체를 설계해 주는, 미래형 코드 편집기의 정수입니다.',
        'summary': 'Composer 기능이 강화되어 여러 파일을 동시에 지휘하며 복잡한 앱을 1분 만에 빌드합니다.',
        'details': [
            'Composer 모드: 자연어 한 줄로 수십 개의 파일에 걸친 대규모 코드 수정을 자동화',
            '코드 심층 이해: 내 프로젝트 전체를 인덱싱하여 "어디가 고장 났어?"라고 물으면 즉시 해결',
            'Claude 3.7 연동: 현재 가장 똑똑한 AI 모델을 코딩 도구 안에서 바로 활용'
        ],
        'url': 'https://cursor.sh',
        'last_updated': '2026-02-09'
    },
    {
        'id': 'v0',
        'name': 'v0.dev',
        'category': 'dev',
        'icon': '<i class="fa-solid fa-shapes text-gray-700"></i>',
        'desc': '상상을 코드로 현실화하는 마법. 웹사이트 디자인 캡처본을 올리거나 글로 설명하면, React와 Tailwind CSS로 구성된 고퀄리티 UI 코드를 즉석에서 구워냅니다.',
        'summary': '피그마(Figma) 디자인 파일을 개발용 코드로 변환하는 성능이 예술 수준으로 올라갔습니다.',
        'details': [
            '이미지 to 코드: 마음에 드는 UI 캡처본을 올리면 99% 유사한 코드를 소스까지 제공',
            '컴포넌트 단위 생성: shadcn/ui 기반의 안정적인 컴포넌트를 즉각적으로 제작',
            '실시간 미리보기: 코드를 고칠 때마다 변화하는 화면을 실시간으로 확인하며 디자인'
        ],
        'url': 'https://v0.dev',
        'last_updated': '2026-02-09'
    },
    {
        'id': 'supabase',
        'name': 'Supabase',
        'category': 'dev',
        'icon': '<i class="fa-solid fa-database text-green-600"></i>',
        'desc': '서버 걱정 없는 개발 환경. 데이터베이스, 로그인 기능, 파일 저장소까지 복잡한 서버 구축 없이 클릭 몇 번으로 해결해 주는 개발자들의 든든한 백엔드 파트너입니다.',
        'summary': '실시간 데이터 동기화 기능이 강화되어 채팅이나 대시보드 제작이 훨씬 쉬워졌습니다.',
        'details': [
            '실시간 DB: 데이터 변경 시 새로고침 없이 사용자 화면에 즉각 반영되는 기능 제공',
            '간편한 인증: 카카오, 구글 로그인을 코드 몇 줄로 연동할 수 있는 강력한 Auth 서비스',
            '강력한 무료 티어: 개인 프로젝트나 교육용 실습 서비스를 운영하기에 충분한 무료 용량'
        ],
        'url': 'https://supabase.com',
        'last_updated': '2026-02-09'
    },
    {
        'id': 'railway',
        'name': 'Railway',
        'category': 'dev',
        'icon': '<i class="fa-solid fa-train text-purple-600"></i>',
        'desc': '한 번의 푸시로 전 세계 배포. 내가 만든 웹 서비스를 세상에 내놓는 가장 쉬운 방법입니다. 복잡한 명령어를 몰라도 깃허브와 연동하면 자동으로 라이브 서버를 띄워줍니다.',
        'summary': '배포 속도가 비약적으로 향상되어 코드 수정 후 반영까지 단 1분이면 충분합니다.',
        'details': [
            'Zero Config: 설치나 설정 없이 깃허브 연동만으로 서버 배포의 전 과정 자동화',
            '직관적인 모니터링: 서버가 잘 돌아가는지, 자원은 얼마나 쓰는지 한눈에 파악',
            '인프라 다변화: PostgreSQL, Redis 등 다양한 플러그인을 버튼 하나로 추가'
        ],
        'url': 'https://railway.app',
        'last_updated': '2026-02-09'
    },

    # ========== 디자인 & 협업 (Design & Collaboration) ==========
    {
        'id': 'figma',
        'name': 'Figma',
        'category': 'design',
        'icon': '<i class="fa-brands fa-figma text-purple-600"></i>',
        'desc': '디자인의 협업 혁명. 웹/앱 화면 디자인을 넘어 이제는 아이디어 보드, 학생 활동지 제작까지 실시간으로 함께 작업할 수 있는 디자인계의 구글 문서입니다.',
        'summary': '디자이너와 개발자를 잇는 Dev Mode 정식 출시와 AI 디자인 도우미가 강력해졌습니다.',
        'details': [
            '실시간 멀티플레이어: 한 도화지 위에서 수십 명의 학생이 동시에 접속해 아이디어 나눔',
            'Dev Mode: 디자이너가 만든 결과물을 코드 수치로 즉시 확인하여 코딩 작업에 활용',
            'Figma AI: "이런 느낌의 웹페이지 구조 짜줘"라고 하면 기초 레이아웃 초안 완성'
        ],
        'url': 'https://figma.com',
        'last_updated': '2026-02-09'
    },
    {
        'id': 'canva',
        'name': 'Canva',
        'category': 'design',
        'icon': '<i class="fa-solid fa-palette text-cyan-500"></i>',
        'desc': '똥손을 금손으로 만드는 도구. 포스터, PPT, 인포그래픽을 고퀄리티 템플릿 위에서 클릭 몇 번으로 완성할 수 있습니다. 학교 전용 계정으로 모든 유료 기능을 쓰세요!',
        'summary': 'Magic Studio 출시로, 텍스트만 넣으면 디자인이 알아서 완성되는 경지에 도달했습니다.',
        'details': [
            'Magic Design: 주제만 입력하면 맞춤형 PPT와 템플릿을 AI가 생성',
            '배경 제거 마법: 사진에서 피사체만 남기고 배경을 깔끔하게 지워주는 원클릭 기능',
            '동영상 편집: 복잡한 툴 없이 디자인 감각 그대로 브이로그나 교육 영상 제작'
        ],
        'url': 'https://canva.com',
        'last_updated': '2026-02-09'
    },

    # ========== 모니터링 & 운영 (Ops & Monitoring) ==========
    {
        'id': 'sentry',
        'name': 'Sentry',
        'category': 'ops',
        'icon': '<i class="fa-solid fa-shield-halved text-purple-700"></i>',
        'desc': '서비스의 든든한 방패. 내가 만든 웹사이트에서 사용자가 어떤 에러를 겪었는지 개발자에게 실시간으로 알려줍니다. 문제가 터지기 전에 미리 대비할 수 있게 도와줍니다.',
        'summary': 'AI 기반의 오류 분석 기능이 도입되어, 에러 원인뿐만 아니라 수정 코드까지 제안합니다.',
        'details': [
            '실시간 장애 감지: 에러 발생 시 Slack이나 Discord로 즉시 알림 발송',
            'AI 오류 분석: 수만 개의 시스템 로그 중 핵심 원인을 AI가 찾아내어 해결책 제시',
            '사용자 경험 모니터링: 사이트가 왜 느린지, 어디서 로딩 병목이 있는지 정밀 분석'
        ],
        'url': 'https://sentry.io',
        'last_updated': '2026-02-09'
    },

    # ========== 생산성 도구 (Productivity) ==========
    {
        'id': 'notion',
        'name': 'Notion',
        'category': 'work',
        'icon': '<i class="fa-solid fa-note-sticky text-black"></i>',
        'desc': '내 삶의 모든 데이터를 한 곳에. 문서 작성, 진도 체크, 학생 명렬표, 수업 캘린더를 하나로 묶어 관리할 수 있는 가히 최고의 기록 관리 자유도를 가진 워크스페이스입니다.',
        'summary': 'Notion AI 통합과 데이터베이스 자동화(Automation) 기능이 정식 도입되었습니다.',
        'details': [
            '자동화 버튼: 클릭 한 번으로 체크리스트를 이동하거나 상태를 변경하는 자동 로직 구축',
            '지능형 검색: 내 노션 내 수많은 문서 중 원하는 정보를 자연어 질문으로 즉각 검색',
            '커뮤니티 템플릿: 전 세계 선생님들이 만든 수업용 템플릿을 복제해 바로 사용 가능'
        ],
        'url': 'https://notion.so',
        'last_updated': '2026-02-09'
    },

    # ========== 창작 & 예술 (Creative Arts) ==========
    {
        'id': 'midjourney',
        'name': 'Midjourney',
        'category': 'art',
        'icon': '<i class="fa-solid fa-image text-purple-500"></i>',
        'desc': '상상을 현실로 그리는 붓. 텍스트 명령 몇 줄로 실사 사진부터 환상적인 일러스트까지 예술 작품 수준의 이미지를 생성해 냅니다. 삽화 제작이나 아이디어 시각화에 독보적입니다.',
        'summary': 'V7 버전 출시로 빛의 표현과 세부 묘사가 사진보다 더 정밀해졌습니다.',
        'details': [
            'Midjourney V7: 조명 배치와 텍스처 표현이 압도적으로 개선된 최신 모델 적용',
            '웹 인터페이스 정식화: 디스코드 명령어 없이 웹사이트에서 마우스로 쉽게 조작 가능',
            '스타일 일관성: 같은 등장인물이나 화풍을 다음 이미지에서도 그대로 유지하는 기능'
        ],
        'url': 'https://midjourney.com',
        'last_updated': '2026-02-09'
    },
    {
        'id': 'runway',
        'name': 'Runway',
        'category': 'art',
        'icon': '<i class="fa-solid fa-video text-green-500"></i>',
        'desc': '영화 감독이 된 AI. 영화 같은 영상 클립을 텍스트 한 줄로 생성합니다. 이미지에 생명력을 불어넣어 움직이게 하거나, 배경을 자유자재로 바꾸는 등 마법 같은 영상 편집이 가능합니다.',
        'summary': 'Gen-3 Alpha 고해상도 모델이 출시되어 영화 수준의 고퀄리티 영상 생성이 가능합니다.',
        'details': [
            'Gen-3 Alpha: 물리 법칙을 이해하는 자연스러운 움직임과 극한의 디테일 표현',
            '모션 브러시: 사진 내 원하는 부분만 콕 집어 움직임을 주는 정밀 제어기능',
            '립싱크 AI: 인물 이미지와 음성을 합쳐 입 모양이 딱 맞는 말하는 영상 제작'
        ],
        'url': 'https://runwayml.com',
        'last_updated': '2026-02-09'
    },
    {
        'id': 'elevenlabs',
        'name': 'ElevenLabs',
        'category': 'art',
        'icon': '<i class="fa-solid fa-microphone text-blue-600"></i>',
        'desc': '기계음 없는 부드러운 목소리. 텍스트를 입력하면 실제 사람보다 더 사람 같은 감성적인 음성을 만들어줍니다. 교육 자료의 내레이션이나 오디오북 제작 시 최고의 몰입감을 선사합니다.',
        'summary': '한국어 성우급 목소리가 대거 추가되었으며 감정 표현이 더욱 정교해졌습니다.',
        'details': [
            'Multilingual v3: 국적에 상관없이 자연스러운 악센트와 톤으로 한국어 음성 배출',
            'Voice Cloning: 내 목소리를 1분 만에 학습시켜 나를 대신해 주는 AI 음성 복제',
            'Speech-to-Speech: 내 말투나 톤을 그대로 유지하며 성우의 목소리로 변조하는 기능'
        ],
        'url': 'https://elevenlabs.io',
        'last_updated': '2026-02-09'
    },
]

