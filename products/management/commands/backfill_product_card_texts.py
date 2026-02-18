from django.core.management.base import BaseCommand

from products.models import Product


BACKFILL_MAP = {
    "우리반 캐릭터 친구 찾기": ("학생 성향을 재미있게 파악해요", "캐릭터 유형 결과", "3분"),
    "반짝반짝 우리반 알림판": ("학급 소식을 빠르게 공유해요", "알림판 공지 카드", "2분"),
    "선생님 사주": ("교사 맞춤 사주를 확인해요", "사주 분석 리포트", "3분"),
    "왁자지껄 교실 윷놀이": ("교실 분위기를 바로 띄워요", "실시간 윷놀이 화면", "1분"),
    "토닥토닥 선생님 운세": ("오늘의 운세를 가볍게 확인해요", "운세 카드", "1분"),
    "가뿐하게 서명 톡": ("서명을 온라인으로 간편 수집해요", "출력용 서명 문서", "2분"),
    "몽글몽글 미술 수업": ("미술 수업 아이디어를 빠르게 준비해요", "수업 활동안", "3분"),
    "글솜씨 뚝딱! 소식지": ("학교 소식지를 AI로 작성해요", "기사/PPT 초안", "5분"),
    "유튜브 탈알고리즘": ("교육 영상 탐색을 더 효율적으로 해요", "추천 영상 목록", "2분"),
    "학교 통합 지원 스쿨잇": ("학교 업무 도구를 한곳에서 관리해요", "통합 대시보드", "1분"),
    "인사이트": ("교육 트렌드를 빠르게 파악해요", "핵심 인사이트 요약", "2분"),
    "AI 도구 가이드": ("필요한 AI 도구를 바로 찾아요", "도구별 사용 가이드", "2분"),
    "AI 프롬프트 레시피": ("수업용 프롬프트를 바로 활용해요", "프롬프트 템플릿", "1분"),
    "두뇌 풀가동! 교실 체스": ("교실 전략 게임 수업을 시작해요", "체스 학습 화면", "1분"),
    "HWP to PDF 변환기": ("한글 문서를 PDF로 변환해요", "PDF 파일", "1분"),
    "두뇌 풀가동! 교실 장기": ("교실에서 장기를 쉽게 진행해요", "장기 게임 화면", "1분"),
    "최종최최종은 이제그만": ("문서 최신본을 안전하게 관리해요", "버전 이력 문서", "2분"),
}


class Command(BaseCommand):
    help = "Backfill Product solve/result/time text for V2 cards (fills only empty fields)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Apply updates. Without this option, command runs in dry-run mode.",
        )

    def handle(self, *args, **options):
        apply_changes = options["apply"]
        target_qs = Product.objects.filter(is_active=True).order_by("display_order", "id")

        scanned = 0
        touched = 0
        skipped = 0

        for product in target_qs:
            scanned += 1
            mapped = BACKFILL_MAP.get(product.title)
            if not mapped:
                skipped += 1
                self.stdout.write(f"[SKIP] no mapping: {product.title}")
                continue

            solve_text, result_text, time_text = mapped
            changed_fields = []

            if not (product.solve_text or "").strip():
                product.solve_text = solve_text
                changed_fields.append("solve_text")
            if not (product.result_text or "").strip():
                product.result_text = result_text
                changed_fields.append("result_text")
            if not (product.time_text or "").strip():
                product.time_text = time_text
                changed_fields.append("time_text")

            if not changed_fields:
                self.stdout.write(f"[KEEP] already filled: {product.title}")
                continue

            touched += 1
            self.stdout.write(f"[UPDATE] {product.title}: {', '.join(changed_fields)}")
            if apply_changes:
                product.save(update_fields=changed_fields)

        mode = "APPLY" if apply_changes else "DRY-RUN"
        self.stdout.write(
            self.style.SUCCESS(
                f"{mode} done | scanned={scanned}, updated={touched}, skipped={skipped}"
            )
        )
