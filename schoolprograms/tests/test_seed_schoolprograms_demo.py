import shutil
import tempfile

from django.core.management import call_command
from django.test import TestCase, override_settings

from schoolprograms.demo_seed import DEMO_PHONE, DEMO_USER_PREFIX
from schoolprograms.models import InquiryReview, InquiryThread, ListingImage, ProgramListing, ProviderProfile


class SeedSchoolProgramsDemoCommandTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._temp_media_root = tempfile.mkdtemp(prefix="schoolprograms-demo-media-")
        cls._media_override = override_settings(MEDIA_ROOT=cls._temp_media_root)
        cls._media_override.enable()

    @classmethod
    def tearDownClass(cls):
        cls._media_override.disable()
        shutil.rmtree(cls._temp_media_root, ignore_errors=True)
        super().tearDownClass()

    def test_seed_command_creates_demo_marketplace_and_vendor_reference_states(self):
        call_command("seed_schoolprograms_demo")

        providers = ProviderProfile.objects.filter(user__username__startswith=DEMO_USER_PREFIX).order_by("provider_name")
        self.assertEqual(providers.count(), 10)
        self.assertTrue(all(provider.contact_phone == DEMO_PHONE for provider in providers))
        self.assertTrue(all(provider.contact_email == "" for provider in providers))
        self.assertIn("에이아이 클래스 공방", list(providers.values_list("provider_name", flat=True)))
        self.assertIn("우리장단 체험마당", list(providers.values_list("provider_name", flat=True)))
        self.assertIn("스쿨런 스포츠데이", list(providers.values_list("provider_name", flat=True)))
        self.assertNotIn("클래스메이커 AI 랩", list(providers.values_list("provider_name", flat=True)))

        approved_listings = ProgramListing.objects.filter(
            provider__user__username__startswith=DEMO_USER_PREFIX,
            approval_status=ProgramListing.ApprovalStatus.APPROVED,
        )
        self.assertEqual(approved_listings.count(), 12)
        self.assertEqual(
            ProgramListing.objects.filter(
                provider__user__username__startswith=DEMO_USER_PREFIX,
                approval_status=ProgramListing.ApprovalStatus.PENDING,
            ).count(),
            1,
        )
        self.assertEqual(
            ProgramListing.objects.filter(
                provider__user__username__startswith=DEMO_USER_PREFIX,
                approval_status=ProgramListing.ApprovalStatus.DRAFT,
            ).count(),
            1,
        )
        self.assertEqual(ListingImage.objects.filter(listing__in=approved_listings).count(), 12)

        reviews = InquiryReview.objects.filter(
            provider__user__username__startswith=DEMO_USER_PREFIX,
            status=InquiryReview.Status.PUBLISHED,
        )
        self.assertEqual(reviews.count(), 6)
        self.assertEqual(
            InquiryThread.objects.filter(
                provider__user__username__startswith=DEMO_USER_PREFIX,
                status=InquiryThread.Status.AWAITING_VENDOR,
            ).count(),
            1,
        )
        self.assertEqual(
            InquiryThread.objects.filter(
                provider__user__username__startswith=DEMO_USER_PREFIX,
                status=InquiryThread.Status.PROPOSAL_SENT,
            ).count(),
            1,
        )
        self.assertEqual(
            InquiryThread.objects.filter(
                provider__user__username__startswith=DEMO_USER_PREFIX,
                status=InquiryThread.Status.ON_HOLD,
            ).count(),
            1,
        )
        self.assertEqual(
            InquiryThread.objects.filter(
                provider__user__username__startswith=DEMO_USER_PREFIX,
                status=InquiryThread.Status.CLOSED,
                is_agreement_reached=True,
            ).count(),
            6,
        )

    def test_seed_command_is_idempotent(self):
        call_command("seed_schoolprograms_demo")
        first_counts = {
            "providers": ProviderProfile.objects.filter(user__username__startswith=DEMO_USER_PREFIX).count(),
            "approved_listings": ProgramListing.objects.filter(
                provider__user__username__startswith=DEMO_USER_PREFIX,
                approval_status=ProgramListing.ApprovalStatus.APPROVED,
            ).count(),
            "reviews": InquiryReview.objects.filter(
                provider__user__username__startswith=DEMO_USER_PREFIX,
                status=InquiryReview.Status.PUBLISHED,
            ).count(),
        }

        call_command("seed_schoolprograms_demo")

        second_counts = {
            "providers": ProviderProfile.objects.filter(user__username__startswith=DEMO_USER_PREFIX).count(),
            "approved_listings": ProgramListing.objects.filter(
                provider__user__username__startswith=DEMO_USER_PREFIX,
                approval_status=ProgramListing.ApprovalStatus.APPROVED,
            ).count(),
            "reviews": InquiryReview.objects.filter(
                provider__user__username__startswith=DEMO_USER_PREFIX,
                status=InquiryReview.Status.PUBLISHED,
            ).count(),
        }
        self.assertEqual(first_counts, second_counts)
