import json
import os
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django  # noqa: E402

django.setup()

from django.urls import NoReverseMatch, reverse  # noqa: E402
from products.models import ManualSection, Product, ServiceManual  # noqa: E402


SNAPSHOT_PATH = PROJECT_ROOT / "docs" / "manuals" / "active_services_code_snapshot.json"


TOP10_DEEP = {
    "반짝반짝 우리반 알림판": {
        "pc": [
            "상단 `설정(톱니)`에서 학생 명단/역할/시간표를 먼저 저장합니다.",
            "메인 화면 중앙 타이머 숫자를 눌러 시작/일시정지하고, 하단 `+1분`, `5분`, `10분`으로 조정합니다.",
            "우측 `오늘의 역할`에서 `역할 순환`과 `호명 모드`를 활용해 발표 흐름을 만듭니다.",
            "우측 알림 카드 `펜` 버튼으로 공지를 입력해 즉시 반영합니다.",
        ],
        "mobile": [
            "모바일은 명단/역할 수정 중심으로 사용하고, 메인 노출은 PC/대화면을 권장합니다.",
            "공지는 짧은 문장(줄바꿈 포함)으로 작성하면 학생 화면 가독성이 좋아집니다.",
        ],
    },
    "가뿐하게 서명 톡": {
        "pc": [
            "목록에서 `새 연수 만들기` 후 제목/강사/장소/일시를 입력해 세션을 생성합니다.",
            "상세 화면 `참석자 명단`에서 텍스트 등록 또는 CSV/Excel 업로드를 진행합니다.",
            "`링크 공유`의 `복사`와 `프로젝터용 참여 QR`로 현장 배포합니다.",
            "미매칭 서명은 `~와 연결`로 정리하고, 종료 후 `출력`으로 결과를 보관합니다.",
        ],
        "mobile": [
            "참석자는 모바일 링크 접속 후 바로 서명할 수 있습니다.",
            "교사는 모바일 모니터링은 가능하지만 대량 명단 수정은 PC가 안전합니다.",
        ],
    },
    "동의서는 나에게 맡겨": {
        "pc": [
            "1단계에서 안내문 업로드/제목/안내 메시지를 입력합니다.",
            "2단계 `서명 박스 추가`로 위치를 맞추고 `위치 미리보기`로 검수합니다.",
            "3단계에서 수신자(공유 명단/CSV/직접입력)를 등록하고 상세로 이동합니다.",
            "상세에서 `학부모 링크 발송 시작`, `안내문+링크 복사`, `링크 재발급`으로 운영합니다.",
        ],
        "mobile": [
            "학부모는 모바일 링크에서 확인→서명→완료를 바로 진행합니다.",
            "교사는 모바일 상태 확인은 가능하지만 서명 박스 재배치는 PC를 권장합니다.",
        ],
    },
    "글솜씨 뚝딱! 소식지": {
        "pc": [
            "주제 입력 또는 PDF 업로드 후 `분석 및 생성 시작`을 실행합니다.",
            "결과 화면에서 `출력 디자인`을 선택하고 `적용`으로 톤을 확정합니다.",
            "`뉴스레터 PPT`, `기본 PDF`, `요약 카드뉴스`, `Word`를 목적별로 내려받습니다.",
            "필요 시 `수정하기`에서 편집 후 재다운로드합니다.",
        ],
        "mobile": [
            "모바일은 결과 확인/공유 중심, 긴 편집과 대용량 다운로드는 PC 권장입니다.",
        ],
    },
    "간편 수합": {
        "pc": [
            "대시보드에서 1)기본정보 2)대상자 3)제출형식 순서로 요청을 생성합니다.",
            "상세 화면에서 QR/입장코드/`초대문구 복사`로 참여를 안내합니다.",
            "`수정`, `마감하기/재개하기`, `CSV`, `마감 +1일`, `보관 +7일`로 운영합니다.",
            "종료 시 `전체 파일 다운로드(ZIP)`로 결과를 일괄 회수합니다.",
        ],
        "mobile": [
            "참여자는 모바일 링크/QR로 즉시 제출 가능합니다.",
            "교사는 모바일 점검은 가능하지만 요청 생성/수정은 PC가 빠릅니다.",
        ],
    },
    "최종최최종은 이제그만": {
        "pc": [
            "`새 문서`로 패키지를 만들고 `업로드` 탭에서 버전을 누적합니다.",
            "필요 버전에 `배포본 지정`을 적용해 배포 기준 버전을 고정합니다.",
            "상단 `최신본 받기`/`배포본 받기`를 목적별로 구분해 사용합니다.",
            "`+ 새 공유 링크 생성` 후 활성/비활성 상태를 관리합니다.",
        ],
        "mobile": [
            "모바일은 버전 확인/다운로드 위주, 업로드/정리는 PC 권장입니다.",
        ],
    },
    "학교 예약 시스템": {
        "pc": [
            "학교 생성 후 관리자 대시보드에서 `특별실`, `블랙아웃`, `교시`를 먼저 설정합니다.",
            "`초대 문구 복사`로 예약 링크를 공유합니다.",
            "예약판에서 날짜 이동 후 빈 슬롯 클릭 → `학년/반/이름` 입력 → `예약하기`를 실행합니다.",
            "운영 중 변경은 관리자 화면 저장 즉시 반영됩니다.",
        ],
        "mobile": [
            "`이 기기에서 정보 기억`을 켜면 반복 예약 입력 시간이 줄어듭니다.",
        ],
    },
    "씨앗 퀴즈": {
        "pc": [
            "입력 방식 A(붙여넣기) 또는 B(파일)를 하나 선택해 문제를 생성합니다.",
            "완료 메시지 `방금 만든 세트 열기`로 미리보기 후 `학생에게 배포하기`를 실행합니다.",
            "배포 화면에서 `링크 복사` 또는 `QR 전체화면`으로 학생 참여를 안내합니다.",
            "`학생 대시보드`와 `정답 분석`을 별도 탭으로 열어 수업 중/후 운영합니다.",
        ],
        "mobile": [
            "학생은 QR 스캔 후 번호/이름만 입력하면 즉시 시작됩니다.",
        ],
    },
    "별빛 추첨기": {
        "pc": [
            "모드(`별빛 추첨기`/`사다리 뽑기`)를 선택하고 명단을 불러옵니다.",
            "별빛 모드: 별 선택 → 당첨 공개 → `다음 추첨` 반복",
            "사다리 모드: 참가자 선택 공개 또는 `역할 발표 쇼 시작`",
            "필요 시 `처음으로 돌아가기`/`준비 화면으로`로 세션 리셋",
        ],
        "mobile": [
            "모바일도 동작하지만 시각효과는 대화면 운영이 훨씬 효과적입니다.",
        ],
    },
    "학급 캘린더": {
        "pc": [
            "상단 `새 일정`으로 제목/기간/시간/색상을 입력해 저장합니다.",
            "월 보기에서 일정 밀도를 확인하고, 상세 모달 `수정`/`삭제`로 관리합니다.",
            "필요 시 공유 섹션에서 `공유 링크 활성화`, `링크 복사`, `재발급`을 사용합니다.",
            "협업자는 가입 이메일 기준으로 `협업자 추가`합니다.",
        ],
        "mobile": [
            "모바일은 일정 확인·간단 수정에 적합하고 대량 입력은 PC를 권장합니다.",
        ],
    },
}


def launch_url(route_name, external_url):
    if route_name:
        try:
            return reverse(route_name)
        except NoReverseMatch:
            return external_url or ""
    return external_url or ""


def default_pc_steps(service):
    features = service.get("features") or []
    ftitles = [f.get("title", "").strip() for f in features if f.get("title")]
    steps = [
        "서비스 메인 화면으로 진입해 제목/설정값을 먼저 확인합니다.",
        "수업 목적에 맞게 입력값을 채운 뒤 실행 또는 생성 버튼을 눌러 결과를 만듭니다.",
    ]
    if ftitles:
        preview = ", ".join(ftitles[:3])
        steps.append(f"핵심 기능({preview})을 순서대로 점검해 결과 품질을 확인합니다.")
    steps.append("결과 화면에서 공유/다운로드/저장 동선을 완료합니다.")
    return steps


def default_mobile_steps(service):
    return [
        "모바일에서는 빠른 확인·공유·간단 입력 중심으로 사용합니다.",
        "긴 편집, 대량 데이터 처리, 출력물 최종 점검은 PC에서 진행합니다.",
    ]


def default_classroom_example(service):
    title = service["title"]
    result_text = (service.get("result_text") or "결과물").strip()
    return [
        f"수업 시작 전 `{title}` 화면을 열어 오늘 활동 목표를 안내합니다.",
        "활동 중간에 입력/응답 상태를 점검하고 누락 대상을 즉시 안내합니다.",
        f"수업 종료 직전에 `{result_text}`을(를) 저장·공유해 마무리합니다.",
    ]


def default_troubleshooting(service):
    time_text = (service.get("time_text") or "수 분").strip()
    return [
        f"실행 속도가 느리면 입력 데이터를 줄여서 1차 테스트(권장: {time_text})를 먼저 진행합니다.",
        "결과가 기대와 다르면 핵심 입력값(제목/옵션/대상/형식)을 다시 확인합니다.",
        "공유가 안 될 때는 링크 권한, 만료 상태, 브라우저 팝업 차단 여부를 점검합니다.",
    ]


def to_bullets(items, ordered=False):
    if ordered:
        return "\n".join([f"{idx}. {item}" for idx, item in enumerate(items, start=1)])
    return "\n".join([f"- {item}" for item in items])


def build_sections(service):
    title = service["title"]
    route = service.get("launch_route_name", "")
    url = launch_url(route, service.get("external_url", ""))
    features = service.get("features") or []
    feature_titles = [f.get("title", "").strip() for f in features if f.get("title")]
    feature_text = ", ".join(feature_titles) if feature_titles else "기본 기능"

    deep = TOP10_DEEP.get(title, {})
    pc_steps = deep.get("pc") or default_pc_steps(service)
    mobile_steps = deep.get("mobile") or default_mobile_steps(service)
    classroom_steps = default_classroom_example(service)
    troubleshooting_steps = default_troubleshooting(service)

    return [
        (
            "서비스 한눈에 보기",
            to_bullets(
                [
                    f"서비스명: {title}",
                    f"진입 경로: {url}",
                    f"라우트 이름: {route or '-'}",
                    f"핵심 기능: {feature_text}",
                    f"설명: {(service.get('lead_text') or service.get('description') or '').strip()}",
                ]
            ),
            "핵심",
        ),
        (
            "시작 전 준비",
            to_bullets(
                [
                    "수업 목표(무엇을 수집/생성/운영할지)를 먼저 정합니다.",
                    "필요한 입력 자료(명단/문서/주제/파일)를 사전에 준비합니다.",
                    "대화면 운영 시 PC에서 먼저 테스트 후 공유 링크를 배포합니다.",
                ],
                ordered=True,
            ),
            "준비",
        ),
        ("PC 운영 동선", to_bullets(pc_steps, ordered=True), "PC"),
        ("모바일 운영 동선", to_bullets(mobile_steps), "모바일"),
        ("수업 적용 예시", to_bullets(classroom_steps, ordered=True), "적용"),
        ("자주 묻는 문제와 해결", to_bullets(troubleshooting_steps), "점검"),
    ]


def write_markdown(services):
    today = date.today().isoformat()
    lines = [
        "# Eduitit 패들릿용 서비스 이용방법 (서비스별 상세 가이드)",
        "",
        f"- 생성일: {today}",
        "- 기준 데이터: 코드 기반 활성 서비스 스냅샷 + 실제 라우트/템플릿 동선",
        "- 목적: 패들릿 게시용 서비스별 사용법(PC/모바일, 수업 적용, 문제 해결)",
        "",
    ]

    for svc in services:
        lines.append(f"## {svc['id']}. {svc['title']}")
        lines.append("")
        for idx, (sec_title, sec_content, _) in enumerate(build_sections(svc), start=1):
            lines.append(f"### {idx}. {sec_title}")
            lines.append("")
            lines.append(sec_content)
            lines.append("")
        lines.append("---")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def sync_db(services):
    result = []
    for svc in services:
        title = svc["title"]
        product = Product.objects.filter(title=title, is_active=True).first()
        if not product:
            result.append({"title": title, "updated": False, "reason": "product_not_found"})
            continue

        manual, _ = ServiceManual.objects.get_or_create(
            product=product,
            defaults={
                "title": f"{title} 패들릿 사용 설명서",
                "description": "패들릿 업로드용 상세 사용법",
                "is_published": True,
            },
        )
        manual.title = f"{title} 패들릿 사용 설명서"
        manual.description = "패들릿 업로드용 상세 사용법"
        manual.is_published = True
        manual.save()

        manual.sections.all().delete()
        sections = build_sections(svc)
        for order, (sec_title, sec_content, badge) in enumerate(sections, start=1):
            ManualSection.objects.create(
                manual=manual,
                title=sec_title,
                content=sec_content,
                layout_type="text_only",
                badge_text=badge,
                display_order=order,
            )

        result.append({"title": title, "updated": True, "sections": len(sections)})
    return result


def main():
    if not SNAPSHOT_PATH.exists():
        raise RuntimeError(f"스냅샷 파일 없음: {SNAPSHOT_PATH}")

    services = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    services = sorted(services, key=lambda x: x.get("id", 0))

    docs_dir = PROJECT_ROOT / "docs" / "manuals"
    docs_dir.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()

    md_path = docs_dir / f"PADLET_SERVICE_GUIDE_DETAILED_V2_{today}.md"
    report_path = docs_dir / f"padlet_manual_sync_report_{today}.json"

    md_path.write_text(write_markdown(services), encoding="utf-8")
    report = sync_db(services)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    updated_count = sum(1 for row in report if row.get("updated"))
    print("=" * 72)
    print("패들릿용 서비스 이용방법 생성/DB 동기화 완료")
    print("=" * 72)
    print(f"- Markdown : {md_path}")
    print(f"- Sync report: {report_path}")
    print(f"- Updated manuals: {updated_count}/{len(report)}")


if __name__ == "__main__":
    main()
