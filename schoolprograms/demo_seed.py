from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.utils import timezone
from django.utils.text import slugify

from .models import (
    InquiryMessage,
    InquiryProposal,
    InquiryReview,
    InquiryThread,
    ListingAttachment,
    ListingImage,
    ListingViewLog,
    ProgramListing,
    ProviderProfile,
)


DEMO_USER_PREFIX = "demo_schoolprograms_"
DEMO_PHONE = "012-345-6789"
DEMO_PASSWORD = "pw-123456"
DEMO_ATTACHMENT_EXTENSIONS = (".pdf", ".hwpx", ".hwp", ".jpg", ".png")

PNG_1X1_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9p2VNl8AAAAASUVORK5CYII="
)
JPG_1X1_BYTES = base64.b64decode(
    "/9j/4AAQSkZJRgABAQAAAQABAAD/2wCEAAkGBxAQEBUQEBAVFRUVFRUVFRUVFRUVFRUVFRUWFhUVFRUYHSggGBolGxUVITEhJSkrLi4uFx8zODMsNygtLisBCgoKDg0OFQ8QFS0dFR0tKy0tLS0rLSstLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLf/AABEIAAEAAgMBIgACEQEDEQH/xAAXAAEBAQEAAAAAAAAAAAAAAAAAAQID/8QAFhEBAQEAAAAAAAAAAAAAAAAAAQAC/9oADAMBAAIQAxAAAAHF4sP/xAAXEAADAQAAAAAAAAAAAAAAAAAAAQIR/9oACAEBAAEFAm2f/8QAFhEAAwAAAAAAAAAAAAAAAAAAAAER/9oACAEDAQE/Aaf/xAAWEQEBAQAAAAAAAAAAAAAAAAAAARH/2gAIAQIBAT8Bp//EABgQAQEBAQEAAAAAAAAAAAAAAAERACEx/9oACAEBAAY/ArRysf/EABoQAQEBAQEBAQAAAAAAAAAAAAERACExQWH/2gAIAQEAAT8hih0nWcl5u9mS6p//2gAMAwEAAgADAAAAEP8A/8QAFxEAAwEAAAAAAAAAAAAAAAAAAAERIf/aAAgBAwEBPxBln//EABYRAQEBAAAAAAAAAAAAAAAAAAABEf/aAAgBAgEBPxBqf//EABsQAQEAAgMBAAAAAAAAAAAAAAERACExQVFh/9oACAEBAAE/EGdb1Kuq3FMuS8M1w0u1qQm9rQkq5s//2Q=="
)


@dataclass(frozen=True)
class DemoListingSpec:
    title: str
    summary: str
    description: str
    category: str
    theme_tags: list[str]
    grade_bands: list[str]
    delivery_mode: str
    province: str
    city: str
    coverage_note: str
    duration_text: str
    capacity_text: str
    price_text: str
    safety_info: str
    materials_info: str
    faq: str
    accent: str
    view_count: int = 0
    recent_log_count: int = 0
    published_days_ago: int = 1
    approval_status: str = ProgramListing.ApprovalStatus.APPROVED
    is_featured: bool = False


@dataclass(frozen=True)
class DemoProviderSpec:
    username_key: str
    provider_name: str
    summary: str
    description: str
    service_area_summary: str
    website: str
    listings: list[DemoListingSpec]


def _demo_email(username_key: str) -> str:
    return f"{DEMO_USER_PREFIX}{username_key}@example.com"


def _set_role(user, *, role: str, nickname: str) -> None:
    profile = user.userprofile
    profile.role = role
    profile.nickname = nickname
    profile.save(update_fields=["role", "nickname"])


def _make_provider_svg(provider_name: str, listing_title: str, accent: str) -> bytes:
    safe_provider = provider_name.replace("&", "&amp;")
    safe_listing = listing_title.replace("&", "&amp;")
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="900" viewBox="0 0 1200 900">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="{accent}" />
      <stop offset="100%" stop-color="#0f172a" />
    </linearGradient>
  </defs>
  <rect width="1200" height="900" fill="url(#bg)" rx="48" ry="48"/>
  <circle cx="1020" cy="150" r="140" fill="rgba(255,255,255,0.14)"/>
  <circle cx="180" cy="760" r="190" fill="rgba(255,255,255,0.10)"/>
  <rect x="72" y="612" width="1056" height="170" rx="34" fill="rgba(15,23,42,0.40)"/>
  <text x="96" y="688" fill="white" font-size="70" font-family="Pretendard, Arial, sans-serif" font-weight="800">{safe_provider}</text>
  <text x="96" y="744" fill="#e2e8f0" font-size="32" font-family="Pretendard, Arial, sans-serif" font-weight="600">{safe_listing}</text>
</svg>""".encode("utf-8")


def _attach_listing_image(listing: ProgramListing, *, accent: str) -> None:
    svg = _make_provider_svg(listing.provider.provider_name, listing.title, accent)
    image = ListingImage(listing=listing, caption=f"{listing.title} 대표 이미지", sort_order=0)
    image.image.save(
        f"{slugify(listing.provider.provider_name, allow_unicode=True)}-{slugify(listing.title, allow_unicode=True)}.svg",
        ContentFile(svg),
        save=True,
    )


def _attachment_payload_for_extension(*, extension: str, listing: ProgramListing) -> tuple[bytes, str]:
    normalized = extension.lower()
    if normalized == ".pdf":
        payload = (
            "%PDF-1.4\n"
            "1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n"
            "2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n"
            "3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 300 144] /Contents 4 0 R >> endobj\n"
            "4 0 obj << /Length 63 >> stream\n"
            "BT /F1 18 Tf 24 88 Td (Demo attachment for schoolprograms) Tj ET\n"
            "endstream endobj\n"
            "trailer << /Root 1 0 R >>\n"
            "%%EOF\n"
        ).encode("utf-8")
        return payload, "application/pdf"
    if normalized == ".hwpx":
        return f"{listing.title} 데모 안내자료 HWPX".encode("utf-8"), "application/vnd.hancom.hwpx"
    if normalized == ".hwp":
        return f"{listing.title} 데모 안내자료 HWP".encode("utf-8"), "application/x-hwp"
    if normalized == ".png":
        return PNG_1X1_BYTES, "image/png"
    if normalized in {".jpg", ".jpeg"}:
        return JPG_1X1_BYTES, "image/jpeg"
    return f"{listing.title} 데모 안내자료".encode("utf-8"), "application/octet-stream"


def _attach_listing_document(listing: ProgramListing, *, index: int) -> None:
    extension = DEMO_ATTACHMENT_EXTENSIONS[index % len(DEMO_ATTACHMENT_EXTENSIONS)]
    base_name = slugify(listing.title, allow_unicode=True)
    filename = f"{base_name}-프로그램안내{extension}"
    payload, content_type = _attachment_payload_for_extension(extension=extension, listing=listing)
    attachment = ListingAttachment(
        listing=listing,
        original_name=filename,
        content_type=content_type,
        file_size=len(payload),
        sort_order=listing.attachments.count(),
    )
    attachment.file.save(filename, ContentFile(payload), save=False)
    attachment.save()


def _build_provider_specs() -> list[DemoProviderSpec]:
    return [
        DemoProviderSpec(
            username_key="urban_trip",
            provider_name="도시탐험 교육연구소",
            summary="학교 안에서 만나는 도시문화·역사 체험",
            description="도시문화와 지역사를 교실형 체험으로 바꿔 학교 안에서 진행합니다. 학년 행사, 교과 연계, 소규모 체험까지 학교 일정에 맞춰 조정합니다.",
            service_area_summary="서울 서부·경기 북서부",
            website="https://example.com/eduitit-demo/urban-trip",
            listings=[
                DemoListingSpec(
                    title="교실 속 우리 동네 도시문화 탐험",
                    summary="교과서 속 도시 이야기를 사진 카드와 만들기 활동으로 연결하는 방문형 수업",
                    description="학생들이 익숙한 동네 공간을 문화·역사·생활 관점으로 다시 보게 만드는 프로그램입니다.",
                    category=ProgramListing.Category.FIELDTRIP,
                    theme_tags=["도시", "역사", "사회"],
                    grade_bands=["elementary_high", "middle"],
                    delivery_mode=ProgramListing.DeliveryMode.VISITING,
                    province="seoul",
                    city="강서구",
                    coverage_note="양천·마포·은평까지 방문 가능",
                    duration_text="90분",
                    capacity_text="학급당 30명, 최대 4개 반",
                    price_text="학급당 32만원부터",
                    safety_info="소형 교구 중심 진행, 학생 이동 없음",
                    materials_info="빔프로젝터와 모둠 책상 배치 권장",
                    faq="학년 맞춤 주제 변경 가능합니다.",
                    accent="#f97316",
                    view_count=48,
                    recent_log_count=7,
                    published_days_ago=16,
                    is_featured=True,
                ),
                DemoListingSpec(
                    title="도시 사진 아카이브 만들기 워크숍",
                    summary="학교 주변 생활권을 사진과 지도 활동으로 기록하는 프로젝트형 클래스",
                    description="학생들이 우리 지역을 기록하고 발표 자료로 정리해 보는 활동형 원데이 클래스입니다.",
                    category=ProgramListing.Category.ONE_DAY_CLASS,
                    theme_tags=["지역기록", "창의", "프로젝트"],
                    grade_bands=["middle", "high"],
                    delivery_mode=ProgramListing.DeliveryMode.VISITING,
                    province="seoul",
                    city="양천구",
                    coverage_note="마포·영등포·구로 가능",
                    duration_text="100분",
                    capacity_text="학급당 30명",
                    price_text="학급당 38만원부터",
                    safety_info="실내 이동 최소화, 스마트기기 대여 가능",
                    materials_info="사진 촬영 가능한 태블릿 또는 스마트기기 권장",
                    faq="학교 홍보 프로젝트형으로도 바꿀 수 있습니다.",
                    accent="#fb923c",
                    view_count=20,
                    recent_log_count=2,
                    published_days_ago=5,
                    approval_status=ProgramListing.ApprovalStatus.DRAFT,
                ),
                DemoListingSpec(
                    title="학교 주변 역사 미션투어 설계안",
                    summary="교내에서 먼저 익히고 교외 적용까지 확장하는 역사 체험 설계형 프로그램",
                    description="학교 상황에 맞는 역사 체험 흐름을 먼저 교내에서 운영할 수 있도록 설계한 프로그램입니다.",
                    category=ProgramListing.Category.FIELDTRIP,
                    theme_tags=["역사", "미션", "체험설계"],
                    grade_bands=["elementary_high", "middle"],
                    delivery_mode=ProgramListing.DeliveryMode.HYBRID,
                    province="seoul",
                    city="은평구",
                    coverage_note="서대문·종로 일정 협의",
                    duration_text="90분",
                    capacity_text="학년 1회",
                    price_text="회차당 85만원부터",
                    safety_info="실외 이동 없는 교내 버전부터 운영",
                    materials_info="프로젝터와 모둠 활동지 제공",
                    faq="교외 연계형 후속 수업도 협의 가능합니다.",
                    accent="#f59e0b",
                    view_count=14,
                    recent_log_count=1,
                    published_days_ago=4,
                    approval_status=ProgramListing.ApprovalStatus.PENDING,
                ),
            ],
        ),
        DemoProviderSpec(
            username_key="green_bus",
            provider_name="초록버스 생태체험랩",
            summary="학교로 찾아가는 생태·환경 체험",
            description="생태 전시물, 관찰 키트, 계절 주제를 묶어 학교 안에서 바로 진행할 수 있는 환경형 체험을 운영합니다.",
            service_area_summary="경기 남부 전역",
            website="https://example.com/eduitit-demo/green-bus",
            listings=[
                DemoListingSpec(
                    title="찾아오는 계절 생태 실험교실",
                    summary="봄·여름·가을·겨울 주제를 바꿔 운영하는 생태 관찰형 체험",
                    description="생태 표본과 관찰 활동을 활용해 학급 단위로 차분하게 운영할 수 있는 방문형 프로그램입니다.",
                    category=ProgramListing.Category.FIELDTRIP,
                    theme_tags=["환경", "생태", "과학"],
                    grade_bands=["elementary_low", "elementary_high"],
                    delivery_mode=ProgramListing.DeliveryMode.VISITING,
                    province="gyeonggi",
                    city="수원",
                    coverage_note="용인·화성·성남·평택 가능",
                    duration_text="80분",
                    capacity_text="학급당 28명, 최대 5개 반",
                    price_text="학급당 35만원부터",
                    safety_info="알레르기 유발 재료 없이 운영 가능",
                    materials_info="세면대 이용 가능하면 좋고, 교실 진행도 가능합니다.",
                    faq="우천 시에도 교내 진행으로 변경 가능합니다.",
                    accent="#16a34a",
                    view_count=64,
                    recent_log_count=9,
                    published_days_ago=13,
                    is_featured=True,
                ),
            ],
        ),
        DemoProviderSpec(
            username_key="science_onwheels",
            provider_name="움직이는 과학실 온휠",
            summary="강당·교실 어디서나 가능한 과학 쇼 앤 메이킹",
            description="과학 공연형 도입과 만들기 활동을 결합해 학교 행사와 학급 체험에 모두 대응하는 팀입니다.",
            service_area_summary="전국 주요 권역 순회",
            website="https://example.com/eduitit-demo/science-onwheels",
            listings=[
                DemoListingSpec(
                    title="강당형 사이언스 퍼포먼스 데이",
                    summary="강당에서 시작해 학급별 미니 실험으로 이어지는 과학 행사형 프로그램",
                    description="학생 참여 비중이 높고, 전교 행사용으로도 자주 운영하는 과학 체험 행사입니다.",
                    category=ProgramListing.Category.SCHOOL_EVENT,
                    theme_tags=["과학", "공연", "실험"],
                    grade_bands=["elementary_high", "middle", "all_school"],
                    delivery_mode=ProgramListing.DeliveryMode.EVENT_SUPPORT,
                    province="nationwide",
                    city="",
                    coverage_note="수도권·충청·영남 월별 순회",
                    duration_text="120분",
                    capacity_text="전교 1회 또는 학년별 분할 운영",
                    price_text="행사형 180만원부터",
                    safety_info="화기 없는 실험만 사용, 안전 요원 동행",
                    materials_info="강당 음향 또는 무선 마이크 권장",
                    faq="학년별로 내용 난이도를 나눌 수 있습니다.",
                    accent="#2563eb",
                    view_count=70,
                    recent_log_count=10,
                    published_days_ago=11,
                ),
                DemoListingSpec(
                    title="교실형 발명 메이킹 클래스",
                    summary="학급별로 바로 만들고 가져가는 메이커 활동",
                    description="전기·에너지·발명 주제를 학생 눈높이에 맞춰 만드는 교실형 프로그램입니다.",
                    category=ProgramListing.Category.ONE_DAY_CLASS,
                    theme_tags=["발명", "메이커", "창의"],
                    grade_bands=["elementary_high", "middle"],
                    delivery_mode=ProgramListing.DeliveryMode.VISITING,
                    province="nationwide",
                    city="",
                    coverage_note="수도권 중심, 타 권역은 일정 협의",
                    duration_text="100분",
                    capacity_text="학급당 30명",
                    price_text="학급당 42만원부터",
                    safety_info="저전압 재료와 절단 보조도구 제공",
                    materials_info="책상 4인 모둠 배치 권장",
                    faq="행사형 진행과 연계 가능합니다.",
                    accent="#0ea5e9",
                    view_count=31,
                    recent_log_count=4,
                    published_days_ago=8,
                ),
            ],
        ),
        DemoProviderSpec(
            username_key="schoolrun_sports",
            provider_name="스쿨런 스포츠데이",
            summary="학교 맞춤형 운동회·스포츠데이 운영",
            description="학교 운동회, 협동 체육, 스포츠데이, 사제동행 이벤트까지 학교 현장 운영 경험이 많은 행사팀입니다.",
            service_area_summary="부산·울산·경남",
            website="https://example.com/eduitit-demo/schoolrun-sports",
            listings=[
                DemoListingSpec(
                    title="학교 맞춤 스포츠데이 패키지",
                    summary="학년별 난이도 조정이 가능한 협동형 스포츠 이벤트",
                    description="운동장 또는 체육관 환경에 맞춰 게임 구성을 바꾸고, 교사 진행 부담을 줄여주는 스포츠데이 프로그램입니다.",
                    category=ProgramListing.Category.SPORTS_DAY,
                    theme_tags=["협동", "체육", "행사"],
                    grade_bands=["elementary_low", "elementary_high", "middle", "all_school"],
                    delivery_mode=ProgramListing.DeliveryMode.EVENT_SUPPORT,
                    province="gyeongnam",
                    city="창원",
                    coverage_note="김해·양산·부산·울산 가능",
                    duration_text="반일 또는 종일",
                    capacity_text="학년 1회 ~ 전교 운영",
                    price_text="반일 220만원부터",
                    safety_info="종목별 안전 동선 사전 브리핑 진행",
                    materials_info="운동장 사용 가능 여부 사전 확인 필요",
                    faq="우천 시 체육관형 종목으로 대체 가능합니다.",
                    accent="#db2777",
                    view_count=55,
                    recent_log_count=6,
                    published_days_ago=9,
                ),
            ],
        ),
        DemoProviderSpec(
            username_key="ai_workshop",
            provider_name="에이아이 클래스 공방",
            summary="학생 체험과 교사 연수를 함께 운영하는 AI·디지털 전문팀",
            description="학생 체험, 교사 연수, 학부모 공개수업까지 AI·디지털 리터러시 주제를 학교 현장에 맞게 커스터마이징합니다.",
            service_area_summary="서울·경기·인천",
            website="https://example.com/eduitit-demo/ai-workshop",
            listings=[
                DemoListingSpec(
                    title="교사 업무자동화 실습 연수",
                    summary="학교 문서와 수업 준비를 줄이는 실습형 AI 연수",
                    description="교사가 바로 따라하면서 결과물을 가져갈 수 있는 실습형 연수로, 교무회의 시간에도 맞출 수 있습니다.",
                    category=ProgramListing.Category.TEACHER_TRAINING,
                    theme_tags=["AI", "업무자동화", "연수"],
                    grade_bands=["teacher_only"],
                    delivery_mode=ProgramListing.DeliveryMode.HYBRID,
                    province="seoul",
                    city="송파구",
                    coverage_note="강남·하남·성남 가능",
                    duration_text="120분",
                    capacity_text="교직원 15명~60명",
                    price_text="연수형 90만원부터",
                    safety_info="개인정보 예시 제외 자료 사용",
                    materials_info="노트북 또는 태블릿 준비 권장",
                    faq="초급/중급 버전 선택 가능합니다.",
                    accent="#7c3aed",
                    view_count=44,
                    recent_log_count=5,
                    published_days_ago=7,
                ),
                DemoListingSpec(
                    title="학생 AI 창작 메이킹 클래스",
                    summary="AI 도구를 활용해 그림·영상·이야기를 만드는 체험형 클래스",
                    description="체험 위주로 구성해 학생들이 어렵지 않게 디지털 창작을 경험할 수 있도록 돕습니다.",
                    category=ProgramListing.Category.ONE_DAY_CLASS,
                    theme_tags=["AI", "창작", "디지털"],
                    grade_bands=["elementary_high", "middle", "high"],
                    delivery_mode=ProgramListing.DeliveryMode.VISITING,
                    province="gyeonggi",
                    city="성남",
                    coverage_note="판교·분당·수지 중심 방문",
                    duration_text="90분",
                    capacity_text="학급당 28명",
                    price_text="학급당 38만원부터",
                    safety_info="계정 없이 체험 가능한 환경 제공",
                    materials_info="와이파이와 스크린이 있으면 좋습니다.",
                    faq="노트북이 없으면 시연 중심으로도 가능합니다.",
                    accent="#8b5cf6",
                    view_count=29,
                    recent_log_count=3,
                    published_days_ago=6,
                ),
            ],
        ),
        DemoProviderSpec(
            username_key="jangdan_field",
            provider_name="우리장단 체험마당",
            summary="국악·전통놀이를 학교 행사와 수업으로 풀어내는 팀",
            description="전통 악기 체험, 장단 놀이, 마당형 활동까지 함께 운영해 학생 참여도가 높은 프로그램을 제공합니다.",
            service_area_summary="전북·충남·광주권",
            website="https://example.com/eduitit-demo/jangdan-field",
            listings=[
                DemoListingSpec(
                    title="찾아오는 국악·전통놀이 한마당",
                    summary="국악기 체험과 전통놀이를 함께 즐기는 참여형 프로그램",
                    description="체험과 공연의 균형이 좋아 학년 행사나 집중 체험일 운영에 잘 맞는 프로그램입니다.",
                    category=ProgramListing.Category.SCHOOL_EVENT,
                    theme_tags=["국악", "전통", "예술"],
                    grade_bands=["elementary_low", "elementary_high", "middle"],
                    delivery_mode=ProgramListing.DeliveryMode.EVENT_SUPPORT,
                    province="jeonbuk",
                    city="전주",
                    coverage_note="익산·군산·논산 가능",
                    duration_text="100분",
                    capacity_text="학년 단위 또는 2개 반 순환",
                    price_text="회차당 95만원부터",
                    safety_info="대형 구조물 없이 교구 중심 운영",
                    materials_info="체육관 또는 다목적실 권장",
                    faq="학교 축제 버전으로도 변경 가능합니다.",
                    accent="#ea580c",
                    view_count=36,
                    recent_log_count=4,
                    published_days_ago=10,
                ),
            ],
        ),
        DemoProviderSpec(
            username_key="safety_hero",
            provider_name="안전히어로 체험단",
            summary="학교 안전교육을 몰입형 체험으로 바꾸는 프로그램",
            description="재난, 생활안전, 응급대처를 교실과 강당에서 단계별 체험으로 진행하는 학교 안전교육 전문팀입니다.",
            service_area_summary="전국 순회",
            website="https://example.com/eduitit-demo/safety-hero",
            listings=[
                DemoListingSpec(
                    title="찾아오는 생활안전 체험부스",
                    summary="재난·응급·생활안전을 부스형으로 경험하는 안전교육 프로그램",
                    description="학교 행사나 체험주간에 맞춰 다양한 안전 주제를 부스형으로 운영할 수 있습니다.",
                    category=ProgramListing.Category.FIELDTRIP,
                    theme_tags=["안전", "응급", "재난"],
                    grade_bands=["elementary_low", "elementary_high", "middle", "all_school"],
                    delivery_mode=ProgramListing.DeliveryMode.EVENT_SUPPORT,
                    province="nationwide",
                    city="",
                    coverage_note="전국 가능, 제주/도서권은 추가 협의",
                    duration_text="90분~180분",
                    capacity_text="부스 수에 따라 60명~300명",
                    price_text="행사형 160만원부터",
                    safety_info="전기·화기 사용 없는 안전교육 장비만 사용",
                    materials_info="복도형/체육관형 모두 가능",
                    faq="학년별 안전 주제 조정 가능합니다.",
                    accent="#dc2626",
                    view_count=58,
                    recent_log_count=8,
                    published_days_ago=5,
                ),
            ],
        ),
        DemoProviderSpec(
            username_key="career_theater",
            provider_name="진로극장 스튜디오",
            summary="진로·직업 세계를 연극형 체험으로 연결하는 팀",
            description="연극, 역할 몰입, 직업 시뮬레이션 요소를 살려 학생들이 진로를 어렵지 않게 체험하도록 돕습니다.",
            service_area_summary="부산·울산·경남 동부",
            website="https://example.com/eduitit-demo/career-theater",
            listings=[
                DemoListingSpec(
                    title="교실 속 진로 롤플레잉 씨어터",
                    summary="직업 역할극과 토론을 결합한 참여형 진로 체험",
                    description="학생들이 여러 직업의 관점을 돌아가며 경험하고 진로 선택 질문을 자연스럽게 나누는 프로그램입니다.",
                    category=ProgramListing.Category.ONE_DAY_CLASS,
                    theme_tags=["진로", "직업", "역할극"],
                    grade_bands=["elementary_high", "middle", "high"],
                    delivery_mode=ProgramListing.DeliveryMode.VISITING,
                    province="busan",
                    city="해운대구",
                    coverage_note="기장·수영·남구 가능",
                    duration_text="100분",
                    capacity_text="학급당 32명",
                    price_text="학급당 40만원부터",
                    safety_info="이동 없는 역할 카드 활동 중심",
                    materials_info="교실 또는 시청각실 가능",
                    faq="고등학교 버전은 진학 주제로도 바뀝니다.",
                    accent="#0f766e",
                    view_count=27,
                    recent_log_count=3,
                    published_days_ago=4,
                ),
            ],
        ),
        DemoProviderSpec(
            username_key="sense_art",
            provider_name="감각예술 워크룸",
            summary="미술·감정표현·협업을 묶은 예술형 원데이 클래스",
            description="학급 분위기 환기, 관계형성, 예술 체험이 함께 필요한 학교에 맞는 감성형 예술 프로그램을 운영합니다.",
            service_area_summary="대전·세종·충청권",
            website="https://example.com/eduitit-demo/sense-art",
            listings=[
                DemoListingSpec(
                    title="우리 반 협업 아트 원데이 클래스",
                    summary="공동 작품을 완성하며 관계 형성을 돕는 예술 체험",
                    description="미술 실력보다 협업 경험을 강조해 학기 초 관계형성, 학급 특별활동으로 활용하기 좋습니다.",
                    category=ProgramListing.Category.ONE_DAY_CLASS,
                    theme_tags=["미술", "협업", "감정표현"],
                    grade_bands=["elementary_low", "elementary_high", "middle"],
                    delivery_mode=ProgramListing.DeliveryMode.VISITING,
                    province="daejeon",
                    city="유성구",
                    coverage_note="세종·청주·공주 가능",
                    duration_text="90분",
                    capacity_text="학급당 30명",
                    price_text="학급당 34만원부터",
                    safety_info="무독성 재료 사용",
                    materials_info="작업용 책상 보호지 제공",
                    faq="완성작은 전시형으로 남길 수 있습니다.",
                    accent="#ec4899",
                    view_count=33,
                    recent_log_count=4,
                    published_days_ago=3,
                ),
            ],
        ),
        DemoProviderSpec(
            username_key="festival_mate",
            provider_name="학교축제 메이트",
            summary="학교행사와 체험부스를 함께 설계하는 운영 파트너",
            description="축제, 체험주간, 진로행사, 학부모 공개 행사까지 학교 운영 동선을 고려해 기획부터 현장 진행까지 함께합니다.",
            service_area_summary="인천·부천·김포",
            website="https://example.com/eduitit-demo/festival-mate",
            listings=[
                DemoListingSpec(
                    title="학교행사 체험부스 큐레이션 패키지",
                    summary="학교 상황에 맞춰 체험부스와 운영 인력을 묶어 제안하는 행사 패키지",
                    description="학교 축제나 공개 행사에서 체험형 동선을 만들고 싶은 학교에 적합한 운영형 프로그램입니다.",
                    category=ProgramListing.Category.SCHOOL_EVENT,
                    theme_tags=["축제", "체험부스", "운영"],
                    grade_bands=["all_school", "teacher_only"],
                    delivery_mode=ProgramListing.DeliveryMode.EVENT_SUPPORT,
                    province="incheon",
                    city="연수구",
                    coverage_note="부천·김포·시흥 가능",
                    duration_text="반일 또는 종일",
                    capacity_text="부스 3개~10개 구성",
                    price_text="행사형 250만원부터",
                    safety_info="행사 보험과 인력 안전 브리핑 포함",
                    materials_info="야외/실내 모두 가능, 전기 사용 여부 사전 협의",
                    faq="학교 예산 범위에 맞춰 축소형 구성 가능합니다.",
                    accent="#14b8a6",
                    view_count=41,
                    recent_log_count=5,
                    published_days_ago=2,
                ),
            ],
        ),
    ]


def _reset_demo_users() -> int:
    user_model = get_user_model()
    deleted, _ = user_model.objects.filter(username__startswith=DEMO_USER_PREFIX).delete()
    return deleted


def _build_demo_provider(spec: DemoProviderSpec):
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username=f"{DEMO_USER_PREFIX}{spec.username_key}",
        email=_demo_email(spec.username_key),
        password=DEMO_PASSWORD,
    )
    _set_role(user, role="company", nickname=spec.provider_name)
    provider = ProviderProfile.objects.create(
        user=user,
        provider_name=spec.provider_name,
        summary=spec.summary,
        description=spec.description,
        contact_email="",
        contact_phone=DEMO_PHONE,
        website=spec.website,
        service_area_summary=spec.service_area_summary,
    )
    provider.verification_document.save(
        f"{slugify(spec.provider_name, allow_unicode=True)}-verification.txt",
        ContentFile(f"{spec.provider_name} 데모용 증빙 문서".encode("utf-8")),
        save=True,
    )

    listings = []
    now = timezone.now()
    for spec_index, listing_spec in enumerate(spec.listings, start=1):
        listing = ProgramListing.objects.create(
            provider=provider,
            title=listing_spec.title,
            summary=listing_spec.summary,
            description=listing_spec.description,
            category=listing_spec.category,
            theme_tags=listing_spec.theme_tags,
            grade_bands=listing_spec.grade_bands,
            delivery_mode=listing_spec.delivery_mode,
            province=listing_spec.province,
            city=listing_spec.city,
            coverage_note=listing_spec.coverage_note,
            duration_text=listing_spec.duration_text,
            capacity_text=listing_spec.capacity_text,
            price_text=listing_spec.price_text,
            safety_info=listing_spec.safety_info,
            materials_info=listing_spec.materials_info,
            faq=listing_spec.faq,
            approval_status=listing_spec.approval_status,
            is_featured=listing_spec.is_featured,
            view_count=listing_spec.view_count,
        )
        if listing_spec.approval_status == ProgramListing.ApprovalStatus.APPROVED:
            listing.published_at = now - timedelta(days=listing_spec.published_days_ago)
            listing.submitted_at = listing.published_at - timedelta(days=2)
            listing.save(update_fields=["published_at", "submitted_at"])
            _attach_listing_image(listing, accent=listing_spec.accent)
            _attach_listing_document(listing, index=spec_index - 1)
            if listing_spec.recent_log_count:
                ListingViewLog.objects.bulk_create(
                    [
                        ListingViewLog(
                            listing=listing,
                            viewer_key=f"demo-viewer:{listing.slug}:{index}",
                            viewed_at=now - timedelta(days=index % 5, hours=index),
                        )
                        for index in range(listing_spec.recent_log_count)
                    ]
                )
        listings.append(listing)
    return provider, listings


def _build_demo_teacher(*, key: str, nickname: str):
    user_model = get_user_model()
    teacher = user_model.objects.create_user(
        username=f"{DEMO_USER_PREFIX}teacher_{key}",
        email=_demo_email(f"teacher_{key}"),
        password=DEMO_PASSWORD,
    )
    _set_role(teacher, role="school", nickname=nickname)
    return teacher


def _create_closed_thread_with_review(
    *,
    listing: ProgramListing,
    teacher_key: str,
    teacher_nickname: str,
    school_region: str,
    target_audience: str,
    expected_participants: int,
    headline: str,
    body: str,
    recommended_for: str,
    days_ago: int,
) -> None:
    teacher = _build_demo_teacher(key=teacher_key, nickname=teacher_nickname)
    thread = InquiryThread.objects.create(
        listing=listing,
        provider=listing.provider,
        teacher=teacher,
        category=listing.category,
        school_region=school_region,
        preferred_schedule="희망 학기 내 협의",
        target_audience=target_audience,
        expected_participants=expected_participants,
        budget_text="추후 협의",
        status=InquiryThread.Status.CLOSED,
        is_agreement_reached=True,
        last_message_at=timezone.now() - timedelta(days=days_ago),
        last_message_preview="[합의 완료] 제안 내용 기준으로 진행 확정",
        last_message_sender_role=InquiryThread.SenderRole.TEACHER,
    )
    proposal = InquiryProposal.objects.create(
        thread=thread,
        sent_by=listing.provider.user,
        price_text=listing.price_text,
        included_items="강사, 체험 재료, 진행 안내문",
        schedule_note="학교 일정에 맞춰 오전/오후 조정 가능",
        preparation_note="빔프로젝터 또는 스크린이 있으면 더 좋습니다.",
        followup_request="정확한 반 수와 진행 공간을 알려 주세요.",
    )
    proposal.created_at = timezone.now() - timedelta(days=days_ago + 1)
    proposal.updated_at = proposal.created_at
    proposal.save(update_fields=["created_at", "updated_at"])
    InquiryReview.objects.create(
        thread=thread,
        listing=listing,
        provider=listing.provider,
        teacher=teacher,
        headline=headline,
        body=body,
        recommended_for=recommended_for,
        status=InquiryReview.Status.PUBLISHED,
        published_at=timezone.now() - timedelta(days=days_ago),
    )


def _seed_vendor_reference_threads(provider: ProviderProfile, approved_listing: ProgramListing) -> None:
    teacher_new = _build_demo_teacher(key="vendor_new", nickname="목업 교사 A")
    awaiting = InquiryThread.objects.create(
        listing=approved_listing,
        provider=provider,
        teacher=teacher_new,
        category=approved_listing.category,
        school_region="서울 양천구",
        preferred_schedule="5월 넷째 주 오전",
        target_audience="초등 5학년 4개 반",
        expected_participants=112,
        budget_text="학급당 30만원대 희망",
        status=InquiryThread.Status.AWAITING_VENDOR,
        last_message_at=timezone.now() - timedelta(days=2),
        last_message_preview="강당 진행 가능 여부와 준비물을 먼저 알고 싶습니다.",
        last_message_sender_role=InquiryThread.SenderRole.TEACHER,
    )
    InquiryMessage.objects.create(
        thread=awaiting,
        sender=teacher_new,
        sender_role=InquiryThread.SenderRole.TEACHER,
        body="강당 진행 가능 여부와 준비물을 먼저 알고 싶습니다.",
    )

    teacher_progress = _build_demo_teacher(key="vendor_progress", nickname="목업 교사 B")
    proposal_thread = InquiryThread.objects.create(
        listing=approved_listing,
        provider=provider,
        teacher=teacher_progress,
        category=approved_listing.category,
        school_region="경기 고양",
        preferred_schedule="6월 초",
        target_audience="초등 6학년 3개 반",
        expected_participants=92,
        budget_text="총액 120만원대 희망",
        status=InquiryThread.Status.PROPOSAL_SENT,
        last_message_at=timezone.now() - timedelta(days=1),
        last_message_preview="제안 카드 확인 후 내부 협의 중입니다.",
        last_message_sender_role=InquiryThread.SenderRole.TEACHER,
    )
    InquiryMessage.objects.create(
        thread=proposal_thread,
        sender=teacher_progress,
        sender_role=InquiryThread.SenderRole.TEACHER,
        body="강당과 교실을 나눠 쓸 수 있는지 궁금합니다.",
    )
    InquiryMessage.objects.create(
        thread=proposal_thread,
        sender=provider.user,
        sender_role=InquiryThread.SenderRole.VENDOR,
        body="가능합니다. 반별 이동 동선까지 같이 제안드리겠습니다.",
    )
    InquiryProposal.objects.create(
        thread=proposal_thread,
        sent_by=provider.user,
        price_text=approved_listing.price_text,
        included_items="강사, 체험 재료, 진행 인력",
        schedule_note="6월 첫째 주 화/목 오전 가능",
        preparation_note="강당 음향 또는 마이크가 있으면 좋습니다.",
        followup_request="학교 일정표와 반 수를 알려 주세요.",
    )

    teacher_hold = _build_demo_teacher(key="vendor_hold", nickname="목업 교사 C")
    hold_thread = InquiryThread.objects.create(
        listing=approved_listing,
        provider=provider,
        teacher=teacher_hold,
        category=approved_listing.category,
        school_region="서울 은평구",
        preferred_schedule="2학기 초",
        target_audience="초등 4학년 5개 반",
        expected_participants=135,
        budget_text="추후 협의",
        status=InquiryThread.Status.ON_HOLD,
        last_message_at=timezone.now() - timedelta(days=3),
        last_message_preview="예산 검토 후 다시 연락드리겠습니다.",
        last_message_sender_role=InquiryThread.SenderRole.TEACHER,
    )
    InquiryProposal.objects.create(
        thread=hold_thread,
        sent_by=provider.user,
        price_text=approved_listing.price_text,
        included_items="강사, 활동지, 진행 키트",
        schedule_note="2학기 첫 달 집중 운영 가능",
        preparation_note="교실형 진행 기준입니다.",
        followup_request="학사일정 확정 후 다시 말씀해 주세요.",
    )


def seed_schoolprograms_demo() -> dict[str, int]:
    _reset_demo_users()

    provider_specs = _build_provider_specs()
    created_providers = []
    approved_listings = []
    vendor_reference_listing = None

    for provider_index, provider_spec in enumerate(provider_specs):
        provider, listings = _build_demo_provider(provider_spec)
        created_providers.append(provider)
        approved = [listing for listing in listings if listing.approval_status == ProgramListing.ApprovalStatus.APPROVED]
        approved_listings.extend(approved)
        if provider_index == 0 and approved:
            vendor_reference_listing = approved[0]

    review_specs = [
        {
            "listing_title": "교실 속 우리 동네 도시문화 탐험",
            "teacher_key": "urban_1",
            "teacher_nickname": "서울하늘초 교사",
            "school_region": "서울 양천구",
            "target_audience": "초등 5학년 4개 반",
            "expected_participants": 112,
            "headline": "학생들이 자기 동네를 새롭게 보는 반응이 좋았어요",
            "body": "도입 설명이 어렵지 않았고 활동 카드가 잘 준비돼 있어서 담임이 개입할 일이 많지 않았습니다. 사회 수업 연계용으로도 좋았습니다.",
            "recommended_for": "사회 연계 체험, 학급 단위 방문형 수업",
            "days_ago": 20,
        },
        {
            "listing_title": "찾아오는 계절 생태 실험교실",
            "teacher_key": "green_1",
            "teacher_nickname": "수원온빛초 교사",
            "school_region": "경기 수원",
            "target_audience": "초등 4학년 5개 반",
            "expected_participants": 138,
            "headline": "차분한 진행이라 학급 운영 부담이 적었습니다",
            "body": "생태 재료가 깔끔하게 정리돼 있었고, 교실에서 바로 진행 가능한 점이 특히 편했습니다. 학생 질문 대응도 안정적이었습니다.",
            "recommended_for": "과학주간, 환경 주제 집중활동",
            "days_ago": 18,
        },
        {
            "listing_title": "강당형 사이언스 퍼포먼스 데이",
            "teacher_key": "science_1",
            "teacher_nickname": "대구큰길중 교사",
            "school_region": "대구 수성구",
            "target_audience": "중학교 1학년 전체",
            "expected_participants": 210,
            "headline": "행사 분위기를 살리면서도 통제가 잘 됐어요",
            "body": "강당 진행이라 걱정했는데 학생 참여 타이밍을 잘 잡아줘서 산만하지 않았습니다. 이후 학급별 활동으로 이어지기 좋았습니다.",
            "recommended_for": "학년 행사, 강당형 체험, 과학의 날",
            "days_ago": 15,
        },
        {
            "listing_title": "학교 맞춤 스포츠데이 패키지",
            "teacher_key": "sports_1",
            "teacher_nickname": "창원바다초 교사",
            "school_region": "경남 창원",
            "target_audience": "초등 전교생",
            "expected_participants": 420,
            "headline": "운영 스태프 동선이 좋아서 교사 개입이 적었습니다",
            "body": "학년별 경기 전환이 빠르고 안전선 안내가 분명했습니다. 운동회 준비 부담을 많이 줄여주는 팀이었습니다.",
            "recommended_for": "전교 스포츠데이, 운동회 대체 행사",
            "days_ago": 13,
        },
        {
            "listing_title": "교사 업무자동화 실습 연수",
            "teacher_key": "ai_1",
            "teacher_nickname": "서울새빛고 교사",
            "school_region": "서울 송파구",
            "target_audience": "교직원 28명",
            "expected_participants": 28,
            "headline": "실습 위주라 연수 만족도가 높았습니다",
            "body": "이론만 듣는 연수가 아니라 바로 써볼 수 있어서 반응이 좋았습니다. 학교 업무 예시로 설명해 준 점이 특히 좋았습니다.",
            "recommended_for": "교사연수, 교무회의 시간 연계 연수",
            "days_ago": 12,
        },
        {
            "listing_title": "학교행사 체험부스 큐레이션 패키지",
            "teacher_key": "festival_1",
            "teacher_nickname": "인천해오름초 교사",
            "school_region": "인천 연수구",
            "target_audience": "학부모 공개행사 및 전교 체험부스",
            "expected_participants": 300,
            "headline": "행사 동선과 부스 구성이 깔끔해서 보기 좋았습니다",
            "body": "학교에서 요구한 톤에 맞게 부스를 정리해 줬고, 학부모 공개행사에서도 어수선하지 않게 운영됐습니다.",
            "recommended_for": "축제, 공개수업 연계 행사, 체험주간",
            "days_ago": 9,
        },
    ]

    listings_by_title = {listing.title: listing for listing in approved_listings}
    for review_spec in review_specs:
        listing = listings_by_title[review_spec["listing_title"]]
        _create_closed_thread_with_review(
            listing=listing,
            teacher_key=review_spec["teacher_key"],
            teacher_nickname=review_spec["teacher_nickname"],
            school_region=review_spec["school_region"],
            target_audience=review_spec["target_audience"],
            expected_participants=review_spec["expected_participants"],
            headline=review_spec["headline"],
            body=review_spec["body"],
            recommended_for=review_spec["recommended_for"],
            days_ago=review_spec["days_ago"],
        )

    if vendor_reference_listing is not None:
        _seed_vendor_reference_threads(vendor_reference_listing.provider, vendor_reference_listing)

    return {
        "providers": ProviderProfile.objects.filter(user__username__startswith=DEMO_USER_PREFIX).count(),
        "approved_listings": ProgramListing.objects.filter(
            provider__user__username__startswith=DEMO_USER_PREFIX,
            approval_status=ProgramListing.ApprovalStatus.APPROVED,
        ).count(),
        "pending_listings": ProgramListing.objects.filter(
            provider__user__username__startswith=DEMO_USER_PREFIX,
            approval_status=ProgramListing.ApprovalStatus.PENDING,
        ).count(),
        "draft_listings": ProgramListing.objects.filter(
            provider__user__username__startswith=DEMO_USER_PREFIX,
            approval_status=ProgramListing.ApprovalStatus.DRAFT,
        ).count(),
        "published_reviews": InquiryReview.objects.filter(
            provider__user__username__startswith=DEMO_USER_PREFIX,
            status=InquiryReview.Status.PUBLISHED,
        ).count(),
        "threads": InquiryThread.objects.filter(provider__user__username__startswith=DEMO_USER_PREFIX).count(),
    }
