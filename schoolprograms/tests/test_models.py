from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from schoolprograms.models import InquiryReview, InquiryThread, ProgramListing, ProviderProfile


User = get_user_model()


def create_provider(*, username="vendor-model", provider_name="모델 테스트 업체"):
    user = User.objects.create_user(
        username=username,
        email=f"{username}@example.com",
        password="pw-123456",
    )
    profile = user.userprofile
    profile.role = "company"
    profile.nickname = provider_name
    profile.save(update_fields=["role", "nickname"])
    return ProviderProfile.objects.create(
        user=user,
        provider_name=provider_name,
        summary="학교 방문형 프로그램 운영",
        description="모델 테스트용 업체입니다.",
        verification_document=SimpleUploadedFile("verify.txt", b"verified"),
    )


def create_teacher(*, username="teacher-model", nickname="모델 교사"):
    user = User.objects.create_user(
        username=username,
        email=f"{username}@example.com",
        password="pw-123456",
    )
    profile = user.userprofile
    profile.role = "school"
    profile.nickname = nickname
    profile.save(update_fields=["role", "nickname"])
    return user


def build_listing(provider, **overrides):
    defaults = {
        "provider": provider,
        "title": "모델 테스트 프로그램",
        "summary": "2교시 방문형 프로그램",
        "description": "교실에서 진행하는 프로그램입니다.",
        "category": ProgramListing.Category.FIELDTRIP,
        "theme_tags": ["환경"],
        "grade_bands": ["elementary_high"],
        "delivery_mode": ProgramListing.DeliveryMode.VISITING,
        "province": "gyeonggi",
        "city": "수원",
        "duration_text": "2교시",
        "schedule_basis": ProgramListing.ScheduleBasis.SCHOOL_LEVEL,
        "capacity_text": "30명",
        "price_text": "학급당 35만원",
        "venue_requirements": ["classroom"],
        "venue_note": "빔프로젝터 사용 가능한 교실",
    }
    defaults.update(overrides)
    return ProgramListing(**defaults)


class ProgramListingLifecycleTests(TestCase):
    def setUp(self):
        self.provider = create_provider()

    def test_pending_listing_sets_submitted_at(self):
        listing = build_listing(
            self.provider,
            title="심사 요청 프로그램",
            approval_status=ProgramListing.ApprovalStatus.PENDING,
        )

        listing.save()

        self.assertEqual(listing.approval_status, ProgramListing.ApprovalStatus.PENDING)
        self.assertIsNotNone(listing.submitted_at)
        self.assertIsNone(listing.published_at)

    def test_approved_listing_sets_published_at(self):
        listing = build_listing(
            self.provider,
            title="공개 프로그램",
            approval_status=ProgramListing.ApprovalStatus.APPROVED,
        )

        listing.save()

        self.assertEqual(listing.approval_status, ProgramListing.ApprovalStatus.APPROVED)
        self.assertIsNotNone(listing.published_at)

    def test_approving_pending_listing_preserves_submission_and_adds_publish_time(self):
        listing = build_listing(
            self.provider,
            title="승인 전환 프로그램",
            approval_status=ProgramListing.ApprovalStatus.PENDING,
        )
        listing.save()
        submitted_at = listing.submitted_at

        listing.mark_approved()
        listing.save()

        self.assertEqual(listing.approval_status, ProgramListing.ApprovalStatus.APPROVED)
        self.assertEqual(listing.submitted_at, submitted_at)
        self.assertIsNotNone(listing.published_at)

    def test_schedule_and_venue_helpers_return_school_ready_labels(self):
        listing = build_listing(
            self.provider,
            schedule_basis=ProgramListing.ScheduleBasis.SCHOOL_LEVEL,
            venue_requirements=["auditorium", "computer_room"],
        )

        listing.save()

        self.assertEqual(listing.schedule_basis_note, "초등 40분 · 중등 45분 · 고등 50분 · 쉬는시간 10분")
        self.assertEqual(listing.venue_requirement_labels, ["강당", "컴퓨터실"])


class InquiryReviewModelTests(TestCase):
    def setUp(self):
        self.provider = create_provider(username="vendor-review-model", provider_name="후기 모델 업체")
        self.teacher = create_teacher()
        self.listing = build_listing(self.provider, title="후기 모델 프로그램", approval_status=ProgramListing.ApprovalStatus.APPROVED)
        self.listing.save()
        self.thread = InquiryThread.objects.create(
            listing=self.listing,
            provider=self.provider,
            teacher=self.teacher,
            category=self.listing.category,
            school_region="경기 수원",
            preferred_schedule="5월",
            target_audience="초등 5학년 3개 반",
            expected_participants=90,
            budget_text="총액 120만원",
            status=InquiryThread.Status.CLOSED,
            is_agreement_reached=True,
        )

    def test_published_review_sets_published_at_and_context_label(self):
        review = InquiryReview.objects.create(
            thread=self.thread,
            listing=self.listing,
            provider=self.provider,
            teacher=self.teacher,
            headline="현장 진행이 안정적이었습니다",
            body="시간 운영이 깔끔했습니다.",
            recommended_for="강당 진행이 필요한 학년 행사",
            status=InquiryReview.Status.PUBLISHED,
        )

        self.assertIsNotNone(review.published_at)
        self.assertIn(self.listing.title, review.public_context_label)
        self.assertIn(self.thread.target_audience, review.public_context_label)
