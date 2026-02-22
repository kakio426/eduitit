from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from django.core.management.base import BaseCommand
from django.db import transaction

from products.models import ManualSection, Product, ProductFeature, ServiceManual


@dataclass(frozen=True)
class SectionPayload:
    title: str
    content: str
    badge_text: str = ""
    layout_type: str = "text_only"


@dataclass(frozen=True)
class ManualPayload:
    title: str
    description: str
    sections: List[SectionPayload]


MANUAL_UPDATES: dict[str, ManualPayload] = {
    "가뿐하게 서명 톡": ManualPayload(
        title="연수 서명 톡 사용 가이드",
        description=(
            "연수 생성부터 링크 공유, 서명 확인, 출력까지 실제 운영 흐름만 간단히 정리했습니다."
        ),
        sections=[
            SectionPayload(
                title="연수 만들기",
                badge_text="Step 1",
                content=(
                    "1. /signatures/ 에서 새 연수를 만듭니다.\n"
                    "2. 연수 제목, 강사명, 일시, 장소를 입력합니다.\n"
                    "3. 생성 즉시 서명 받기 활성화를 켜면 바로 참여 링크를 배포할 수 있습니다."
                ),
            ),
            SectionPayload(
                title="참여 링크 공유 및 서명 수집",
                badge_text="Step 2",
                content=(
                    "1. 연수 상세 화면의 링크 공유 영역에서 참여 링크를 복사합니다.\n"
                    "2. 메신저/문자/게시글로 링크를 전달합니다.\n"
                    "3. 참석자는 로그인 없이 이름과 서명을 입력해 제출할 수 있습니다."
                ),
            ),
            SectionPayload(
                title="서명 확인 및 문서 출력",
                badge_text="Step 3",
                content=(
                    "1. 연수 상세 화면에서 서명 목록과 진행 상태를 확인합니다.\n"
                    "2. 필요하면 참석자 명단(텍스트/CSV/XLSX) 업로드로 매칭을 보완합니다.\n"
                    "3. 출력 화면에서 인쇄하거나 브라우저의 PDF 저장 기능으로 보관합니다."
                ),
            ),
        ],
    ),
    "왁자지껄 교실 윷놀이": ManualPayload(
        title="왁자지껄 교실 윷놀이 이용방법",
        description="교실 화면에서 바로 진행할 수 있도록 실제 조작 흐름 중심으로 정리했습니다.",
        sections=[
            SectionPayload(
                title="게임 시작",
                badge_text="Step 1",
                content=(
                    "1. /products/yut/ 에 접속합니다.\n"
                    "2. 화면 우측의 윷 던지기 버튼으로 턴을 진행합니다.\n"
                    "3. 결과가 나오면 이동 가능한 말을 클릭해 이동합니다."
                ),
            ),
            SectionPayload(
                title="진행 화면 읽기",
                badge_text="Step 2",
                content=(
                    "1. 현재 턴, 팀별 나온 말, 게임 로그를 보며 진행 상황을 확인합니다.\n"
                    "2. 잡기/겹치기 등 상황이 로그에 표시되므로 학생들과 규칙 설명에 활용하기 좋습니다.\n"
                    "3. 빔/TV 화면에 띄우고 조작 담당 1명을 정하면 수업 진행이 안정적입니다."
                ),
            ),
            SectionPayload(
                title="수업 운영 팁",
                badge_text="Tip",
                content=(
                    "1. 한 판이 끝나면 게임 초기화 버튼으로 즉시 다음 판을 시작할 수 있습니다.\n"
                    "2. 휴대폰 환경에서는 화면이 제한될 수 있으므로 PC/태블릿 사용을 권장합니다."
                ),
            ),
        ],
    ),
    "토닥토닥 선생님 운세": ManualPayload(
        title="토닥토닥 선생님 운세 이용방법",
        description="입력, 해석, 보관까지 실제 사주 서비스 흐름에 맞춰 구성했습니다.",
        sections=[
            SectionPayload(
                title="분석 시작",
                badge_text="Step 1",
                content=(
                    "1. /fortune/ 에 로그인 후 접속합니다.\n"
                    "2. 일반 사주 또는 교직 사주 모드를 선택합니다.\n"
                    "3. 이름, 성별, 생년월일(필수)과 출생 시간(선택)을 입력해 분석을 시작합니다."
                ),
            ),
            SectionPayload(
                title="결과 해석",
                badge_text="Step 2",
                content=(
                    "1. 결과 화면에서 핵심 요약과 해석 항목을 확인합니다.\n"
                    "2. 필요한 문장은 수업/상담 메모용으로 복사해 활용합니다.\n"
                    "3. 같은 입력값으로 재분석해 표현을 비교할 수 있습니다."
                ),
            ),
            SectionPayload(
                title="기록 관리",
                badge_text="Step 3",
                content=(
                    "1. 저장 기능을 사용하면 보관함에서 다시 열람할 수 있습니다.\n"
                    "2. /fortune/history/ 에서 이전 결과를 확인하고 정리합니다."
                ),
            ),
        ],
    ),
    "몽글몽글 미술 수업": ManualPayload(
        title="몽글몽글 미술 수업 이용방법",
        description="Gemini 수동 복붙으로 단계를 만들고 편집하는 실제 사용 순서로 안내합니다.",
        sections=[
            SectionPayload(
                title="Gemini 프롬프트 준비",
                badge_text="Step 1",
                content=(
                    "1. /artclass/ 에서 유튜브 영상 URL을 입력합니다.\n"
                    "2. 프롬프트용 대상 영상 URL 칸에 URL을 확인하거나 메인 주소 불러오기를 누릅니다.\n"
                    "3. 프롬프트 복사 버튼으로 Gemini 지시문을 복사합니다."
                ),
            ),
            SectionPayload(
                title="결과 붙여넣기 및 검증",
                badge_text="Step 2",
                content=(
                    "1. Gemini에서 생성한 JSON 결과를 결과 붙여넣기 칸에 넣고 적용을 누릅니다.\n"
                    "2. 파서가 형식을 점검해 단계 목록으로 반영합니다.\n"
                    "3. 단계는 6~12개를 권장하며 24개 초과 시 앞 24개만 자동 반영됩니다."
                ),
            ),
            SectionPayload(
                title="단계 편집 및 수업 실행",
                badge_text="Step 3",
                content=(
                    "1. 단계 추가/삭제, 이미지 첨부, 클립보드 붙여넣기로 수업안을 다듬습니다.\n"
                    "2. 자동 전환 간격(초)을 설정한 뒤 수업 시작하기를 누릅니다.\n"
                    "3. 라이브러리에서 다른 선생님의 공유 수업도 참고할 수 있습니다."
                ),
            ),
        ],
    ),
    "글솜씨 뚝딱! 소식지": ManualPayload(
        title="글솜씨 뚝딱! 소식지 이용방법",
        description="실제 3단계(입력→AI 초안→편집/다운로드)로만 구성한 운영 가이드입니다.",
        sections=[
            SectionPayload(
                title="정보 입력",
                badge_text="Step 1",
                content=(
                    "1. /autoarticle/ 에 로그인 후 접속합니다.\n"
                    "2. 학년/행사명/키워드/사진 등 기본 정보를 입력합니다.\n"
                    "3. AI 초안 만들기를 눌러 1차 기사 초안을 생성합니다."
                ),
            ),
            SectionPayload(
                title="초안 편집",
                badge_text="Step 2",
                content=(
                    "1. 제목, 본문, 해시태그를 교실 상황에 맞게 수정합니다.\n"
                    "2. 문장 톤과 표현을 학부모 공지 톤에 맞춰 최종 조정합니다."
                ),
            ),
            SectionPayload(
                title="결과 보존 및 다운로드",
                badge_text="Step 3",
                content=(
                    "1. 저장 후 결과 화면에서 문서 버전을 확인합니다.\n"
                    "2. 필요 시 PDF/PPT/Word/카드뉴스 형식으로 내려받아 배포합니다.\n"
                    "3. 아카이브에서 이전 기사 재열람 및 재편집이 가능합니다."
                ),
            ),
        ],
    ),
    "유튜브 탈알고리즘": ManualPayload(
        title="유튜브 탈알고리즘 이용방법",
        description=(
            "이 서비스는 외부 페이지에서 운영됩니다. 접속 후 화면 안내를 따라 탐색을 시작하세요."
        ),
        sections=[
            SectionPayload(
                title="외부 서비스 접속",
                badge_text="Step 1",
                content=(
                    "1. 대시보드에서 서비스 시작을 누르면 외부 페이지로 이동합니다.\n"
                    "2. 첫 화면 안내에 따라 탐색 기준(주제/관심사)을 설정합니다."
                ),
            ),
            SectionPayload(
                title="콘텐츠 탐색",
                badge_text="Step 2",
                content=(
                    "1. 제안되는 영상 목록을 순서대로 확인합니다.\n"
                    "2. 기존 추천과 다른 관점의 콘텐츠를 수업 주제로 선별합니다."
                ),
            ),
            SectionPayload(
                title="교실 활용",
                badge_text="Tip",
                content=(
                    "1. 같은 주제를 서로 다른 출처로 비교해 토론 질문을 만듭니다.\n"
                    "2. 출처/발행 시점 확인을 함께 지도하면 미디어 리터러시 활동에 유용합니다."
                ),
            ),
        ],
    ),
    "학교 통합 지원 스쿨잇": ManualPayload(
        title="학교 통합 지원 스쿨잇 이용방법",
        description="외부 스쿨잇 서비스 기준으로 실제 사용 순서를 간단히 정리했습니다.",
        sections=[
            SectionPayload(
                title="외부 서비스 접속",
                badge_text="Step 1",
                content=(
                    "1. 대시보드에서 스쿨잇 시작을 눌러 외부 사이트로 이동합니다.\n"
                    "2. 기관 정보 또는 계정 정보를 확인해 로그인/가입을 완료합니다."
                ),
            ),
            SectionPayload(
                title="요청 등록",
                badge_text="Step 2",
                content=(
                    "1. 필요한 업무 유형(채용/업체 매칭 등)을 선택합니다.\n"
                    "2. 조건과 요청 사항을 입력해 등록합니다."
                ),
            ),
            SectionPayload(
                title="진행 확인",
                badge_text="Step 3",
                content=(
                    "1. 등록한 요청의 진행 상태를 주기적으로 확인합니다.\n"
                    "2. 매칭 결과는 학교 내부 절차에 맞춰 검토 후 확정합니다."
                ),
            ),
        ],
    ),
    "인사이트": ManualPayload(
        title="인사이트 이용방법",
        description="영상 기반 인사이트 기록/공유의 실제 화면 흐름만 정리했습니다.",
        sections=[
            SectionPayload(
                title="라이브러리 탐색",
                badge_text="Step 1",
                content=(
                    "1. /insights/ 에서 최근순/인기순/오래된순으로 목록을 탐색합니다.\n"
                    "2. 카드의 영상 썸네일을 눌러 원본 영상을 확인합니다."
                ),
            ),
            SectionPayload(
                title="새 인사이트 작성",
                badge_text="Step 2",
                content=(
                    "1. 로그인 후 기록하기(또는 새 인사이트 등록)로 작성 화면에 진입합니다.\n"
                    "2. 제목, 카테고리, 내용을 입력하고 필요하면 영상 URL/태그/메모를 추가합니다.\n"
                    "3. 저장 후 상세 페이지에서 내용을 확인합니다."
                ),
            ),
            SectionPayload(
                title="상호작용 및 관리",
                badge_text="Step 3",
                content=(
                    "1. 좋아요 기능으로 유용한 인사이트를 모아볼 수 있습니다.\n"
                    "2. 본인 작성 글은 수정 화면에서 업데이트할 수 있습니다."
                ),
            ),
        ],
    ),
    "AI 도구 가이드": ManualPayload(
        title="AI 도구 가이드 이용방법",
        description="카테고리 필터와 상세 모달 중심의 실제 화면 흐름으로 교체했습니다.",
        sections=[
            SectionPayload(
                title="카테고리별 탐색",
                badge_text="Step 1",
                content=(
                    "1. /tools/ 에서 카테고리 탭으로 관심 분야를 먼저 좁힙니다.\n"
                    "2. 카드 목록에서 도구 이름과 요약을 빠르게 비교합니다."
                ),
            ),
            SectionPayload(
                title="상세 정보 확인",
                badge_text="Step 2",
                content=(
                    "1. 카드를 클릭하면 상세 모달에서 업데이트 요약과 핵심 포인트를 볼 수 있습니다.\n"
                    "2. 최신 업데이트 항목을 읽고 수업/업무 적합성을 판단합니다."
                ),
            ),
            SectionPayload(
                title="도구 실행",
                badge_text="Step 3",
                content=(
                    "1. 상세 모달의 바로가기 버튼으로 원 서비스에 이동합니다.\n"
                    "2. 적용 전에는 소규모 테스트로 학교 환경 적합성을 먼저 확인하세요."
                ),
            ),
        ],
    ),
    "AI 프롬프트 레시피": ManualPayload(
        title="AI 프롬프트 레시피 이용방법",
        description="카드 선택 → 모달 복사 → 실제 도구 적용 흐름으로 정리했습니다.",
        sections=[
            SectionPayload(
                title="레시피 선택",
                badge_text="Step 1",
                content=(
                    "1. /prompts/ 에서 목적에 맞는 레시피 카드를 선택합니다.\n"
                    "2. 카드 제목과 태그를 기준으로 필요한 템플릿을 고릅니다."
                ),
            ),
            SectionPayload(
                title="복사 및 맞춤화",
                badge_text="Step 2",
                content=(
                    "1. 모달에서 프롬프트를 복사합니다.\n"
                    "2. 대상 학년/수업 맥락/출력 형식에 맞게 일부 문장을 수정합니다."
                ),
            ),
            SectionPayload(
                title="실행 및 개선",
                badge_text="Step 3",
                content=(
                    "1. 사용하는 AI 도구에 붙여넣어 실행합니다.\n"
                    "2. 결과가 길거나 모호하면 조건(분량/톤/형식)을 추가해 재실행합니다."
                ),
            ),
        ],
    ),
    "HWP to PDF 변환기": ManualPayload(
        title="HWP to PDF 변환기 이용방법",
        description=(
            "프로그램 다운로드부터 변환 실행까지 실제 운영 환경에 맞는 최소 절차를 안내합니다."
        ),
        sections=[
            SectionPayload(
                title="프로그램 다운로드",
                badge_text="Step 1",
                content=(
                    "1. 서비스 시작 버튼으로 배포 파일을 다운로드합니다.\n"
                    "2. 압축 파일이 제공되면 먼저 압축을 해제한 뒤 실행 파일 위치를 확인합니다.\n"
                    "3. 다운로드 링크: {launch_url}"
                ),
            ),
            SectionPayload(
                title="실행 환경 확인",
                badge_text="Step 2",
                content=(
                    "1. Windows 환경에서 한글(Hancom Office)이 설치되어 있어야 합니다.\n"
                    "2. 변환할 HWP/HWPX 파일이 다른 프로그램에서 열려 있으면 먼저 닫아주세요."
                ),
            ),
            SectionPayload(
                title="변환 실행",
                badge_text="Step 3",
                content=(
                    "1. 프로그램에서 변환할 파일(또는 폴더)을 선택합니다.\n"
                    "2. 출력 폴더를 지정하고 변환을 실행합니다.\n"
                    "3. 결과 PDF를 열어 글자 깨짐/페이지 누락 여부를 확인합니다."
                ),
            ),
        ],
    ),
}


class Command(BaseCommand):
    help = "Fix service manual mismatches and signature modal copy drift."

    def _render_content(self, content: str, product: Product) -> str:
        launch_url = product.external_url or ""
        return content.format(launch_url=launch_url)

    def _upsert_manual(self, product_title: str, payload: ManualPayload) -> tuple[bool, int]:
        product = Product.objects.filter(title=product_title).first()
        if not product:
            self.stdout.write(self.style.WARNING(f"[SKIP] Product not found: {product_title}"))
            return False, 0

        manual, _ = ServiceManual.objects.get_or_create(product=product)
        changed_fields: list[str] = []

        if manual.title != payload.title:
            manual.title = payload.title
            changed_fields.append("title")
        if manual.description != payload.description:
            manual.description = payload.description
            changed_fields.append("description")
        if not manual.is_published:
            manual.is_published = True
            changed_fields.append("is_published")

        if changed_fields:
            manual.save(update_fields=changed_fields)

        manual.sections.all().delete()
        for idx, section in enumerate(payload.sections, start=1):
            ManualSection.objects.create(
                manual=manual,
                title=section.title,
                content=self._render_content(section.content, product),
                badge_text=section.badge_text,
                layout_type=section.layout_type,
                display_order=idx,
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"[OK] Manual updated: {product_title} (manual_id={manual.id}, sections={len(payload.sections)})"
            )
        )
        return True, len(payload.sections)

    def _update_signature_modal_copy(self) -> bool:
        product = Product.objects.filter(title="가뿐하게 서명 톡").first()
        if not product:
            self.stdout.write(self.style.WARNING("[SKIP] Product not found: 가뿐하게 서명 톡"))
            return False

        changed_fields: list[str] = []
        desired_lead = "바쁜 쉬는 시간, 결재판 들고 교무실 내려갈 필요 없어요. 내 자리에서 링크 하나로 서명 끝!"
        desired_desc = (
            "\"연수 때마다 종이 명단 돌리고 사인받기 귀찮으셨죠?\" "
            "이제 참여 링크 공유로 간편하게 서명을 수집하세요. "
            "연수 상세 화면에서 서명 현황을 확인하고, 출력 화면에서 인쇄/PDF 저장으로 문서를 보관할 수 있습니다."
        )

        if product.lead_text != desired_lead:
            product.lead_text = desired_lead
            changed_fields.append("lead_text")
        if product.description != desired_desc:
            product.description = desired_desc
            changed_fields.append("description")

        if changed_fields:
            product.save(update_fields=changed_fields)

        desired_features = [
            (
                "링크 공유로 빠른 서명 수집",
                "연수 상세 화면의 참여 링크를 복사해 메신저/문자/게시글로 배포할 수 있습니다.",
            ),
            (
                "실시간 참석 확인",
                "누가 서명을 완료했는지 상세 화면에서 즉시 확인하고 미완료 대상을 관리할 수 있습니다.",
            ),
            (
                "출석부 출력 및 PDF 저장",
                "출력 화면에서 인쇄하거나 브라우저의 PDF 저장 기능으로 결과 문서를 보관할 수 있습니다.",
            ),
        ]

        existing = list(ProductFeature.objects.filter(product=product).order_by("id"))
        for i, (title, description) in enumerate(desired_features):
            if i < len(existing):
                feature = existing[i]
                dirty: list[str] = []
                if feature.title != title:
                    feature.title = title
                    dirty.append("title")
                if feature.description != description:
                    feature.description = description
                    dirty.append("description")
                if dirty:
                    feature.save(update_fields=dirty)
            else:
                ProductFeature.objects.create(
                    product=product,
                    icon="fa-solid fa-check",
                    title=title,
                    description=description,
                )

        self.stdout.write(self.style.SUCCESS("[OK] Signature modal copy updated"))
        return True

    @transaction.atomic
    def handle(self, *args, **options):
        updated_manuals = 0
        updated_sections = 0
        for product_title, payload in MANUAL_UPDATES.items():
            ok, section_count = self._upsert_manual(product_title, payload)
            if ok:
                updated_manuals += 1
                updated_sections += section_count

        signature_ok = self._update_signature_modal_copy()

        self.stdout.write("-" * 72)
        self.stdout.write(
            self.style.SUCCESS(
                f"[DONE] manuals={updated_manuals}, sections={updated_sections}, signature_modal={int(signature_ok)}"
            )
        )
