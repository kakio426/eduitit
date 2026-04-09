from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from schoolprograms.models import ProgramListing, ProviderProfile


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


def build_listing(provider, **overrides):
    defaults = {
        "provider": provider,
        "title": "모델 테스트 프로그램",
        "summary": "90분 방문형 프로그램",
        "description": "교실에서 진행하는 프로그램입니다.",
        "category": ProgramListing.Category.FIELDTRIP,
        "theme_tags": ["환경"],
        "grade_bands": ["elementary_high"],
        "delivery_mode": ProgramListing.DeliveryMode.VISITING,
        "province": "gyeonggi",
        "city": "수원",
        "duration_text": "90분",
        "capacity_text": "30명",
        "price_text": "학급당 35만원",
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
