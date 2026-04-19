from pathlib import Path

from django.test import SimpleTestCase


ROOT_DIR = Path(__file__).resolve().parents[2]

AUDITED_TEMPLATES = [
    "artclass/templates/artclass/setup_home.html",
    "autoarticle/templates/autoarticle/wizard/step1.html",
    "blockclass/templates/blockclass/main.html",
    "collect/templates/collect/landing.html",
    "consent/templates/consent/dashboard.html",
    "consent/templates/consent/create.html",
    "docviewer/templates/docviewer/main.html",
    "docsign/templates/docsign/create.html",
    "edu_materials/templates/edu_materials/main.html",
    "edu_materials_next/templates/edu_materials_next/main.html",
    "encyclopedia/templates/encyclopedia/landing.html",
    "happy_seed/templates/happy_seed/dashboard.html",
    "happy_seed/templates/happy_seed/landing.html",
    "handoff/templates/handoff/landing.html",
    "hwpxchat/templates/hwpxchat/main.html",
    "infoboard/templates/infoboard/dashboard.html",
    "noticegen/templates/noticegen/main.html",
    "ocrdesk/templates/ocrdesk/main.html",
    "qrgen/templates/qrgen/landing.html",
    "quickdrop/templates/quickdrop/landing.html",
    "reflex_game/templates/reflex_game/main.html",
    "schoolprograms/templates/schoolprograms/landing.html",
    "schoolcomm/templates/schoolcomm/main.html",
    "slidesmith/templates/slidesmith/main.html",
    "textbook_ai/templates/textbook_ai/main.html",
    "textbooks/templates/textbooks/main.html",
    "timetable/templates/timetable/index.html",
]

BANNED_HELPER_PHRASES = (
    "할 수 있습니다",
    "할 수 있어요",
    "하려면",
    "여기서",
    "먼저 ",
    "바로 시작할 수 있습니다",
)

REMOVED_VERBOSE_SNIPPETS = {
    "artclass/templates/artclass/setup_home.html": (
        "영상 주소를 넣고, 제미나이 답변을 불러오고, 초록 버튼으로 바로 시작하세요.",
        "수정, 시작, 공유 링크 복사를 한 번에 이어서 합니다.",
        "다른 선생님 수업을 바로 내 수업으로 가져와 수정할 수 있습니다.",
    ),
    "autoarticle/templates/autoarticle/wizard/step1.html": (
        "교실 소식을 AI가 멋진 기사로 바꿔드려요.",
        "기사 하단에 삽입될 사진을 선택해주세요.",
    ),
    "blockclass/static/blockclass/blockclass.js": (
        "코드 생성 중 오류가 발생했습니다. 블록 연결을 다시 확인해 주세요.",
        "블록을 배치하면 코드가 여기에 표시됩니다.",
        "아직 코드가 없습니다. 블록을 하나 더 놓아 보세요.",
        "블록을 더 정리한 뒤 JSON 저장이나 활동판 저장으로 이어가세요.",
        "왼쪽 템플릿을 먼저 눌러 기본 흐름을 불러오세요.",
    ),
    "blockclass/templates/blockclass/main.html": (
        "오늘 할 일",
        "카테고리 선택",
        "드래그 이동",
        "휠 확대·축소",
        "템플릿 선택 전",
        "아래 코드 동기화",
        "템플릿 선택 후 블록 추가",
    ),
    "collect/templates/collect/landing.html": (
        "QR 또는 입장코드로 파일, 링크, 텍스트, 선택형 응답을 빠르게 수합하세요.",
        "새 요청 생성과 제출 확인",
    ),
    "consent/templates/consent/dashboard.html": (
        "학부모 확인형과 일반 서명형을 같은 서비스에서 관리합니다.",
        "필요할 때만 펼쳐 확인합니다.",
    ),
    "consent/templates/consent/create.html": (
        "대상에 맞는 방식만 먼저 고르면 이후 화면이 그에 맞게 바뀝니다.",
        "학생 이름과 연락처 뒤 4자리로 찾는 방식입니다. 가정통신문, 참여 동의, 이름 사용 동의처럼 학급 단위 수합에 맞습니다.",
        "교사, 직원, 외부 강사, 개별 학부모처럼 이름만으로 구분해 개별 링크를 보내는 방식입니다.",
    ),
    "docviewer/templates/docviewer/main.html": (
        "PDF 올리고 확인",
        "끌어놓기 또는 파일 선택",
    ),
    "docsign/templates/docsign/create.html": (
        "PDF를 고르면 여기서 바로 봅니다.",
        "페이지 미리보기를 준비합니다.",
    ),
    "edu_materials/templates/edu_materials/main.html": (
        "공개 자료실, 내 보관함, 새 자료 만들기.",
        "대표 자료 체험 후 공개 자료실 확인.",
    ),
    "edu_materials_next/templates/edu_materials_next/main.html": (
        "처음 쓰는 순서",
        "오늘 수업 주제를 적고, AI에 프롬프트를 넣어 HTML 자료를 만든 뒤, QR로 학생에게 바로 보여 주세요.",
    ),
    "encyclopedia/templates/encyclopedia/landing.html": (
        "NotebookLM 기반 AI 백과사전을 공유하고 활용하세요!",
        "Google NotebookLM으로 만든 AI 백과사전을 등록하고, 다른 선생님들과 공유하세요.",
        'Google NotebookLM에서 "공유" 버튼을 눌러 얻은 링크를 붙여넣으세요.',
        "위에서 새 백과사전을 등록해보세요!",
    ),
    "happy_seed/templates/happy_seed/dashboard.html": (
        "작은 실천을 씨앗으로, 교실의 성장을 꽃으로. 내 교실을 열고 학생 기록, 꽃피움, 동의 상태를 이어서 관리합니다.",
        "가장 최근에 만든 교실이 먼저 보입니다.",
        "새 교실을 만들면 학생 기록과 긍정 행동 운영을 바로 시작할 수 있습니다.",
        "교실 열기 → 학생 관리, 동의 상태, 꽃피움 진행",
        "안내 보기",
        "사용 안내 보기",
        "학생 관리 · 동의 · 꽃피움",
    ),
    "happy_seed/templates/happy_seed/landing.html": (
        "작은 실천을 씨앗으로, 교실의 성장을 꽃으로",
        "긍정 행동 기록, 꽃피움 추첨 보상, 학급 꽃밭 대시보드를 한 흐름으로 운영하세요.",
        "보호자 동의와 보상 확률 설정까지 한 화면에서 연결됩니다.",
        "\"나의 작은 행동 하나하나가 나의 미래, 너의 미래, 우리 모두의 미래를 행복으로 바꿉니다.\"",
    ),
    "handoff/templates/handoff/landing.html": (
        "명부 만들고 체크",
    ),
    "hwpxchat/templates/hwpxchat/main.html": (
        "공문이나 한글 문서를 올리면 해야 할 일, 기한, 전달 대상을 카드로 정리해 드려요.",
        "파일을 여기로 끌어다 놓거나 아래에서 선택해 주세요.",
        "업무 카드와 추가 질문을 여기서 이어갑니다",
    ),
    "infoboard/templates/infoboard/dashboard.html": (
        "오늘 바로 쓰는 제출 월",
        "패들릿처럼 벽에 모이되, 수업 현장에서는 더 가볍고 더 빠르게 시작할 수 있게 만들었어요.",
    ),
    "noticegen/templates/noticegen/main.html": (
        "바로 작성",
        "메모만 적고 바로 만듭니다.",
        "메모만 적고 2회까지 바로 써봅니다.",
    ),
    "ocrdesk/templates/ocrdesk/main.html": (
        "오늘 할 일",
        "사진 올리고 결과 확인",
        "사진 1장 선택",
    ),
    "qrgen/templates/qrgen/landing.html": (
        "기본은 링크 1개 생성입니다. 필요할 때 링크를 추가해 자동 전환으로 QR을 보여주세요.",
        "학생에게 보여줄 공개 링크만 사용해 주세요.",
    ),
    "quickdrop/templates/quickdrop/landing.html": (
        "텍스트를 붙여넣거나 첨부파일을 골라 바로 옮깁니다.",
        "한 번 연결",
    ),
    "reflex_game/templates/reflex_game/main.html": (
        "신호가 뜨면 가장 빠르게 터치하세요",
        "혼자 반응속도를 측정합니다",
        "화면 양쪽을 잡고 먼저 터치하세요",
        "시작 버튼을 눌러 준비하세요",
    ),
    "schoolprograms/templates/schoolprograms/landing.html": (
        "지역, 학년, 방식으로 고르기",
        "상세에서 가격 확인",
        "{{ card.trust_context }}",
        "업체 자세히 보기",
    ),
    "schoolcomm/templates/schoolcomm/main.html": (
        "공지, 자료, 대화, 캘린더",
        "채팅방 하나로 시작",
        "이름만 정하기",
    ),
    "slidesmith/templates/slidesmith/main.html": (
        "제목과 발표 내용을 넣으면 미리보고, 새 탭에서 발표합니다.",
        "슬라이드를 나누려면",
    ),
    "ssambti/templates/ssambti/main.html": (
        "결과 저장을 위해선 로그인이 필요해요",
        "수합 연동 모드가 켜져 있습니다. 검사 완료 후 결과가 자동 전송됩니다.",
    ),
    "textbook_ai/templates/textbook_ai/main.html": (
        "올린 PDF에서 목차, 본문, 표를 정리해 둡니다.",
        "디지털 PDF를 올리면 구조를 정리합니다.",
    ),
    "textbooks/templates/textbooks/main.html": (
        "PDF 올리고 입장코드 열기",
        "과목, 단원, PDF",
        "PDF 수업과 분리",
    ),
    "timetable/templates/timetable/index.html": (
        "새 학기, 입력 링크, 확정본 관리.",
        "학교, 학기, 반 수 입력.",
        "편집, 검토, 확정.",
    ),
}


class ServiceEntryCopyAuditTests(SimpleTestCase):
    def test_audited_templates_do_not_use_default_explanatory_phrases(self):
        for relative_path in AUDITED_TEMPLATES:
            template_text = (ROOT_DIR / relative_path).read_text(encoding="utf-8")
            for phrase in BANNED_HELPER_PHRASES:
                self.assertNotIn(
                    phrase,
                    template_text,
                    msg=f"{relative_path} should avoid helper phrase: {phrase}",
                )

    def test_removed_verbose_snippets_do_not_return(self):
        for relative_path, snippets in REMOVED_VERBOSE_SNIPPETS.items():
            template_text = (ROOT_DIR / relative_path).read_text(encoding="utf-8")
            for snippet in snippets:
                self.assertNotIn(
                    snippet,
                    template_text,
                    msg=f"{relative_path} should stay concise and not reintroduce: {snippet}",
                )
