from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import UserProfile
from schoolprograms.models import (
    InquiryProposal,
    InquiryReview,
    InquiryThread,
    ListingAttachment,
    ListingViewLog,
    ProgramListing,
    ProviderProfile,
    SavedListing,
)


User = get_user_model()


def create_user_with_role(*, username, role, nickname=None):
    user = User.objects.create_user(
        username=username,
        email=f"{username}@example.com",
        password="pw-123456",
    )
    profile = user.userprofile
    profile.role = role
    profile.nickname = nickname or username
    profile.save(update_fields=["role", "nickname"])
    return user


def create_provider(*, username="vendor", provider_name="에듀이티잇 체험랩", summary="학교로 찾아가는 환경·과학 체험 프로그램", verified=True):
    user = create_user_with_role(username=username, role="company", nickname=provider_name)
    provider = ProviderProfile.objects.create(
        user=user,
        provider_name=provider_name,
        summary=summary,
        description="학교 현장 맞춤형 체험 수업을 제공합니다.",
        contact_email=f"{username}@company.com",
        service_area_summary="서울·경기",
        verification_document=SimpleUploadedFile("verify.txt", b"verified") if verified else None,
    )
    return user, provider


def create_listing(*, provider, title="찾아오는 환경 체험", approval_status=ProgramListing.ApprovalStatus.APPROVED, **overrides):
    defaults = {
        "provider": provider,
        "title": title,
        "summary": "90분 안에 끝나는 학교 방문형 환경 체험",
        "description": "교실 또는 강당에서 바로 진행하는 체험 수업입니다.",
        "category": ProgramListing.Category.FIELDTRIP,
        "theme_tags": ["환경", "생태"],
        "grade_bands": ["elementary_high"],
        "delivery_mode": ProgramListing.DeliveryMode.VISITING,
        "province": "gyeonggi",
        "city": "수원",
        "coverage_note": "수원·용인·성남 방문 가능",
        "duration_text": "90분",
        "capacity_text": "학급당 30명, 최대 4개 반",
        "price_text": "학급당 35만원부터",
        "safety_info": "안전 지도안과 보험 안내 제공",
        "materials_info": "빔프로젝터와 책상 배치 필요",
        "faq": "우천 시에도 교내 진행 가능합니다.",
        "approval_status": approval_status,
    }
    defaults.update(overrides)
    listing = ProgramListing.objects.create(**defaults)
    if approval_status == ProgramListing.ApprovalStatus.APPROVED:
        listing.published_at = listing.created_at
        listing.save(update_fields=["published_at"])
    return listing


def create_attachment(*, listing, name="program-guide.pdf", content=b"%PDF-1.4 demo", content_type="application/pdf"):
    return ListingAttachment.objects.create(
        listing=listing,
        file=SimpleUploadedFile(name, content, content_type=content_type),
        original_name=name,
        content_type=content_type,
        file_size=len(content),
    )


class SchoolProgramsLandingTests(TestCase):
    def setUp(self):
        self.client = self.client_class()
        self.company_user, self.provider = create_provider()
        self.teacher_user = create_user_with_role(username="teacher", role="school", nickname="교사")

    def test_company_user_redirects_to_vendor_dashboard(self):
        self.client.force_login(self.company_user)

        response = self.client.get(reverse("schoolprograms:landing"))

        self.assertRedirects(response, reverse("schoolprograms:vendor_dashboard"))

    def test_teacher_user_stays_on_public_landing(self):
        create_listing(provider=self.provider)
        self.client.force_login(self.teacher_user)

        response = self.client.get(reverse("schoolprograms:landing"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "학교로 찾아오는 업체를 먼저 둘러보세요")
        self.assertContains(response, self.provider.provider_name)
        self.assertContains(response, "조건 더 보기")
        self.assertNotContains(response, "업체 등록 안내 보기")


class SchoolProgramsDiscoveryTests(TestCase):
    def setUp(self):
        self.client = self.client_class()
        _, self.provider = create_provider(username="vendor1", provider_name="배움 체험연구소")
        _, self.other_provider = create_provider(username="vendor4", provider_name="전국 스포츠 랩")
        self.primary = create_listing(
            provider=self.provider,
            title="찾아오는 환경 체험",
            category=ProgramListing.Category.FIELDTRIP,
            province="gyeonggi",
            grade_bands=["elementary_high"],
            delivery_mode=ProgramListing.DeliveryMode.VISITING,
            theme_tags=["환경", "생태"],
        )
        create_listing(
            provider=self.other_provider,
            title="교사 AI 연수",
            category=ProgramListing.Category.TEACHER_TRAINING,
            province="seoul",
            grade_bands=["teacher_only"],
            delivery_mode=ProgramListing.DeliveryMode.HYBRID,
            theme_tags=["AI", "업무자동화"],
        )
        create_listing(
            provider=self.provider,
            title="심사중 프로그램",
            approval_status=ProgramListing.ApprovalStatus.PENDING,
        )

    def test_public_list_and_detail_show_only_approved_items(self):
        response = self.client.get(reverse("schoolprograms:landing"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "배움 체험연구소")
        self.assertContains(response, "전국 스포츠 랩")
        self.assertNotContains(response, "심사중 프로그램")

        detail = self.client.get(reverse("schoolprograms:listing_detail", args=[self.primary.slug]))
        self.assertEqual(detail.status_code, 200)

    def test_provider_detail_defaults_to_inline_inquiry_flow(self):
        teacher_user = create_user_with_role(username="teacher-inline", role="school", nickname="교사")
        self.client.force_login(teacher_user)

        response = self.client.get(reverse("schoolprograms:provider_detail", args=[self.provider.slug]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "활동을 고르면 오른쪽에서 바로 문의를 시작할 수 있습니다.")
        self.assertContains(response, "이 활동으로 문의 보내기")
        self.assertEqual(response.context["selected_listing"].pk, self.primary.pk)

    def test_provider_and_listing_detail_surface_attachment_downloads(self):
        attachment = create_attachment(listing=self.primary, name="program-guide.pdf")

        provider_response = self.client.get(reverse("schoolprograms:provider_detail", args=[self.provider.slug]))
        listing_response = self.client.get(reverse("schoolprograms:listing_detail", args=[self.primary.slug]))

        download_url = reverse("schoolprograms:download_listing_attachment", args=[self.primary.slug, attachment.id])
        self.assertContains(provider_response, "상세 안내자료")
        self.assertContains(provider_response, download_url)
        self.assertContains(listing_response, "첨부 자료")
        self.assertContains(listing_response, download_url)

    def test_filter_combination_returns_expected_listing(self):
        response = self.client.get(
            reverse("schoolprograms:landing"),
            {
                "province": "gyeonggi",
                "region_text": "수원",
                "category": ProgramListing.Category.FIELDTRIP,
                "grade_band": "elementary_high",
                "delivery_mode": ProgramListing.DeliveryMode.VISITING,
                "q": "환경",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "배움 체험연구소")
        self.assertNotContains(response, "전국 스포츠 랩")

    def test_landing_hides_advanced_filters_by_default_and_removes_internal_metrics(self):
        response = self.client.get(reverse("schoolprograms:landing"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="advanced-filters-panel"', html=False)
        self.assertNotContains(response, 'id="advanced-filters-panel" open', html=False)
        self.assertNotContains(response, "최근 관심")
        self.assertNotContains(response, "누적 조회")

    def test_landing_badges_render_below_image_without_absolute_overlay(self):
        agreed_teacher = create_user_with_role(username="overlay-review-teacher", role="school", nickname="후기교사")
        agreed_thread = InquiryThread.objects.create(
            listing=self.primary,
            provider=self.provider,
            teacher=agreed_teacher,
            category=self.primary.category,
            school_region="경기 수원",
            preferred_schedule="5월 둘째 주 오전",
            target_audience="초등 5학년 4개 반",
            expected_participants=110,
            budget_text="학급당 30만원대 희망",
            status=InquiryThread.Status.CLOSED,
            is_agreement_reached=True,
            last_message_at=timezone.now(),
            last_message_preview="[합의 완료] 진행 확정",
            last_message_sender_role=InquiryThread.SenderRole.TEACHER,
        )
        InquiryReview.objects.create(
            thread=agreed_thread,
            listing=self.primary,
            provider=self.provider,
            teacher=agreed_teacher,
            headline="학급 운영이 매끄러웠어요",
            body="도입과 마무리가 분명해서 진행이 편했습니다.",
            recommended_for="학급 단위 방문형 체험",
            status=InquiryReview.Status.PUBLISHED,
        )

        response = self.client.get(reverse("schoolprograms:landing"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "운영 승인")
        self.assertContains(response, "이용후기 1개")
        self.assertNotContains(response, "absolute left-4 top-4")

    def test_provider_pagination_handles_multiple_pages(self):
        for index in range(1, 14):
            _, provider = create_provider(username=f"bulkvendor{index}", provider_name=f"전국 체험 파트너 {index:02d}")
            create_listing(provider=provider, title=f"대량 프로그램 {index:03d}")

        response = self.client.get(reverse("schoolprograms:landing"), {"page": 2})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "2 /")
        self.assertContains(response, "전국 체험 파트너")

    def test_provider_grid_prioritizes_recent_interest(self):
        _, hot_provider = create_provider(username="hotvendor", provider_name="요즘 인기 체험사")
        hot_listing = create_listing(
            provider=hot_provider,
            title="요즘 인기 체험",
            category=ProgramListing.Category.SCHOOL_EVENT,
            province="gyeonggi",
            city="성남",
            theme_tags=["협동", "행사"],
        )
        ListingViewLog.objects.bulk_create(
            [
                ListingViewLog(listing=hot_listing, viewer_key=f"user:{index}", viewed_at=timezone.now() - timedelta(days=1))
                for index in range(3)
            ]
        )

        response = self.client.get(reverse("schoolprograms:landing"))

        self.assertEqual(response.status_code, 200)
        provider_cards = response.context["page_obj"].object_list
        self.assertGreaterEqual(len(provider_cards), 1)
        self.assertEqual(provider_cards[0]["provider"].pk, hot_provider.pk)

    def test_landing_card_surfaces_published_review_signal(self):
        agreed_teacher = create_user_with_role(username="landing-review-teacher", role="school", nickname="후기교사")
        agreed_thread = InquiryThread.objects.create(
            listing=self.primary,
            provider=self.provider,
            teacher=agreed_teacher,
            category=self.primary.category,
            school_region="경기 수원",
            preferred_schedule="5월 둘째 주 오전",
            target_audience="초등 5학년 4개 반",
            expected_participants=110,
            budget_text="학급당 30만원대 희망",
            status=InquiryThread.Status.CLOSED,
            is_agreement_reached=True,
            last_message_at=timezone.now(),
            last_message_preview="[합의 완료] 진행 확정",
            last_message_sender_role=InquiryThread.SenderRole.TEACHER,
        )
        InquiryReview.objects.create(
            thread=agreed_thread,
            listing=self.primary,
            provider=self.provider,
            teacher=agreed_teacher,
            headline="학급 운영이 매끄러웠어요",
            body="도입과 마무리가 분명해서 진행이 편했습니다.",
            recommended_for="학급 단위 방문형 체험",
            status=InquiryReview.Status.PUBLISHED,
        )

        response = self.client.get(reverse("schoolprograms:landing"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "이용후기 1개")
        self.assertContains(response, "학급 운영이 매끄러웠어요")


class SchoolProgramsInquiryTests(TestCase):
    def setUp(self):
        self.client = self.client_class()
        self.company_user, self.provider = create_provider(username="vendor2", provider_name="행복 체험센터")
        self.other_company_user, self.other_provider = create_provider(username="vendor3", provider_name="다른 업체")
        self.teacher_user = create_user_with_role(username="teacher2", role="school", nickname="담임선생님")
        self.listing = create_listing(provider=self.provider, title="찾아오는 과학 체험")

    def _inquiry_payload(self):
        return {
            "category": self.listing.category,
            "school_region": "경기 수원",
            "preferred_schedule": "5월 둘째 주 오전",
            "target_audience": "초등 5학년 4개 반",
            "expected_participants": 110,
            "budget_text": "학급당 30만원대 희망",
            "request_message": "강당 진행 가능 여부와 준비물 범위를 알고 싶습니다.",
        }

    def _create_agreed_thread(self, *, teacher=None, listing=None, school_region="경기 수원", target_audience="초등 5학년 4개 반"):
        target_listing = listing or self.listing
        target_teacher = teacher or self.teacher_user
        return InquiryThread.objects.create(
            listing=target_listing,
            provider=target_listing.provider,
            teacher=target_teacher,
            category=target_listing.category,
            school_region=school_region,
            preferred_schedule="5월 둘째 주 오전",
            target_audience=target_audience,
            expected_participants=110,
            budget_text="학급당 30만원대 희망",
            status=InquiryThread.Status.CLOSED,
            is_agreement_reached=True,
            last_message_at=timezone.now(),
            last_message_preview="[합의 완료] 제안 내용을 기준으로 진행하겠습니다.",
            last_message_sender_role=InquiryThread.SenderRole.TEACHER,
        )

    def test_anonymous_and_company_cannot_create_teacher_inquiry(self):
        anonymous_response = self.client.post(reverse("schoolprograms:create_inquiry", args=[self.listing.slug]), self._inquiry_payload())
        self.assertEqual(anonymous_response.status_code, 302)
        self.assertIn(reverse("account_login"), anonymous_response.url)

        self.client.force_login(self.company_user)
        company_response = self.client.post(reverse("schoolprograms:create_inquiry", args=[self.listing.slug]), self._inquiry_payload())
        self.assertEqual(company_response.status_code, 403)

    def test_inquiry_category_is_locked_to_listing_even_if_post_is_tampered(self):
        self.client.force_login(self.teacher_user)
        payload = self._inquiry_payload()
        payload["category"] = ProgramListing.Category.TEACHER_TRAINING

        response = self.client.post(reverse("schoolprograms:create_inquiry", args=[self.listing.slug]), payload)

        thread = InquiryThread.objects.get(listing=self.listing, teacher=self.teacher_user)
        self.assertRedirects(response, reverse("schoolprograms:teacher_inquiry_detail", args=[thread.id]))
        self.assertEqual(thread.category, self.listing.category)

    def test_vendor_can_only_access_own_inquiry_and_proposal_updates_teacher_bucket(self):
        self.client.force_login(self.teacher_user)
        create_response = self.client.post(reverse("schoolprograms:create_inquiry", args=[self.listing.slug]), self._inquiry_payload())
        thread = InquiryThread.objects.get(listing=self.listing, teacher=self.teacher_user)
        self.assertRedirects(create_response, reverse("schoolprograms:teacher_inquiry_detail", args=[thread.id]))

        self.client.force_login(self.other_company_user)
        blocked = self.client.get(reverse("schoolprograms:vendor_inquiry_detail", args=[thread.id]))
        self.assertEqual(blocked.status_code, 404)

        self.client.force_login(self.company_user)
        proposal_response = self.client.post(
            reverse("schoolprograms:vendor_inquiry_detail", args=[thread.id]),
            {
                "action": "proposal",
                "price_text": "총액 140만원부터 또는 학급당 35만원",
                "included_items": "강사 파견, 체험 재료, 사후 정리",
                "schedule_note": "5월 둘째 주 화·수 오전 가능",
                "preparation_note": "빔프로젝터와 책상 배치만 부탁드립니다.",
                "followup_request": "정확한 반 수와 강당 여부를 알려 주세요.",
            },
        )
        self.assertRedirects(proposal_response, reverse("schoolprograms:vendor_inquiry_detail", args=[thread.id]))

        thread.refresh_from_db()
        self.assertEqual(thread.status, InquiryThread.Status.PROPOSAL_SENT)
        self.assertEqual(thread.last_message_sender_role, InquiryThread.SenderRole.VENDOR)
        self.assertTrue(InquiryProposal.objects.filter(thread=thread).exists())

        self.client.force_login(self.teacher_user)
        teacher_inquiries = self.client.get(reverse("schoolprograms:teacher_inquiries"), {"tab": "proposal"})
        self.assertEqual(teacher_inquiries.status_code, 200)
        self.assertContains(teacher_inquiries, "찾아오는 과학 체험")
        self.assertContains(teacher_inquiries, "제안 카드 도착")

    def test_teacher_can_create_inquiry_directly_from_provider_detail(self):
        self.client.force_login(self.teacher_user)

        response = self.client.post(
            reverse("schoolprograms:provider_detail", args=[self.provider.slug]),
            {
                "listing_slug": self.listing.slug,
                "school_region": "경기 수원",
                "preferred_schedule": "6월 셋째 주 오전",
                "target_audience": "초등 5학년 3개 반",
                "expected_participants": 90,
                "budget_text": "총액 120만원대 희망",
                "request_message": "체육관 진행 가능 여부를 먼저 알고 싶습니다.",
            },
        )

        thread = InquiryThread.objects.get(listing=self.listing, teacher=self.teacher_user)
        self.assertRedirects(response, reverse("schoolprograms:teacher_inquiry_detail", args=[thread.id]))
        self.assertEqual(thread.school_region, "경기 수원")

    def test_closed_thread_blocks_teacher_and_vendor_followup_posts(self):
        self.client.force_login(self.teacher_user)
        self.client.post(reverse("schoolprograms:create_inquiry", args=[self.listing.slug]), self._inquiry_payload())
        thread = InquiryThread.objects.get(listing=self.listing, teacher=self.teacher_user)

        self.client.post(reverse("schoolprograms:teacher_inquiry_detail", args=[thread.id]), {"action": "close"})
        teacher_message_count = thread.messages.count()

        blocked_teacher = self.client.post(
            reverse("schoolprograms:teacher_inquiry_detail", args=[thread.id]),
            {"action": "message", "body": "종료 후 다시 보내는 메시지"},
        )
        self.assertRedirects(blocked_teacher, reverse("schoolprograms:teacher_inquiry_detail", args=[thread.id]))
        thread.refresh_from_db()
        self.assertEqual(thread.messages.count(), teacher_message_count)

        self.client.force_login(self.company_user)
        blocked_vendor = self.client.post(
            reverse("schoolprograms:vendor_inquiry_detail", args=[thread.id]),
            {
                "action": "proposal",
                "price_text": "총액 130만원",
                "included_items": "강사와 재료",
                "schedule_note": "6월 가능",
                "preparation_note": "",
                "followup_request": "",
            },
        )
        self.assertRedirects(blocked_vendor, reverse("schoolprograms:vendor_inquiry_detail", args=[thread.id]))
        self.assertFalse(InquiryProposal.objects.filter(thread=thread).exists())

    def test_teacher_can_accept_proposal_and_thread_marks_agreement(self):
        self.client.force_login(self.teacher_user)
        self.client.post(reverse("schoolprograms:create_inquiry", args=[self.listing.slug]), self._inquiry_payload())
        thread = InquiryThread.objects.get(listing=self.listing, teacher=self.teacher_user)

        self.client.force_login(self.company_user)
        self.client.post(
            reverse("schoolprograms:vendor_inquiry_detail", args=[thread.id]),
            {
                "action": "proposal",
                "price_text": "총액 140만원부터 또는 학급당 35만원",
                "included_items": "강사 파견, 체험 재료, 사후 정리",
                "schedule_note": "5월 둘째 주 화·수 오전 가능",
                "preparation_note": "빔프로젝터와 책상 배치만 부탁드립니다.",
                "followup_request": "정확한 반 수와 강당 여부를 알려 주세요.",
            },
        )

        self.client.force_login(self.teacher_user)
        response = self.client.post(
            reverse("schoolprograms:teacher_inquiry_detail", args=[thread.id]),
            {"action": "accept_proposal"},
        )

        self.assertRedirects(response, reverse("schoolprograms:teacher_inquiry_detail", args=[thread.id]))
        thread.refresh_from_db()
        self.assertEqual(thread.status, InquiryThread.Status.CLOSED)
        self.assertTrue(thread.is_agreement_reached)
        self.assertEqual(thread.workflow_status_label, "합의 완료")

    def test_agreement_detail_accepts_review_submission_without_rating(self):
        self.client.force_login(self.teacher_user)
        self.client.post(reverse("schoolprograms:create_inquiry", args=[self.listing.slug]), self._inquiry_payload())
        thread = InquiryThread.objects.get(listing=self.listing, teacher=self.teacher_user)

        self.client.force_login(self.company_user)
        self.client.post(
            reverse("schoolprograms:vendor_inquiry_detail", args=[thread.id]),
            {
                "action": "proposal",
                "price_text": "총액 140만원부터 또는 학급당 35만원",
                "included_items": "강사 파견, 체험 재료, 사후 정리",
                "schedule_note": "5월 둘째 주 화·수 오전 가능",
                "preparation_note": "빔프로젝터와 책상 배치만 부탁드립니다.",
                "followup_request": "정확한 반 수와 강당 여부를 알려 주세요.",
            },
        )

        self.client.force_login(self.teacher_user)
        self.client.post(
            reverse("schoolprograms:teacher_inquiry_detail", args=[thread.id]),
            {"action": "accept_proposal"},
        )
        response = self.client.post(
            reverse("schoolprograms:teacher_inquiry_detail", args=[thread.id]),
            {
                "action": "save_review",
                "headline": "교실 진행 흐름이 안정적이었어요",
                "body": "시간 안내가 분명했고 학생들이 끝까지 잘 따라왔습니다.",
                "recommended_for": "학급 단위 체험과 강당 동시 운영",
            },
        )

        self.assertRedirects(response, reverse("schoolprograms:teacher_inquiry_detail", args=[thread.id]))
        review = InquiryReview.objects.get(thread=thread)
        self.assertEqual(review.status, InquiryReview.Status.PENDING)
        detail = self.client.get(reverse("schoolprograms:teacher_inquiry_detail", args=[thread.id]))
        self.assertContains(detail, "남긴 이용후기")
        self.assertContains(detail, "운영 검토 후 업체 상세에 공개됩니다.")
        self.assertContains(detail, "교실 진행 흐름이 안정적이었어요")

    def test_provider_detail_shows_only_published_reviews(self):
        published_thread = self._create_agreed_thread()
        InquiryReview.objects.create(
            thread=published_thread,
            listing=self.listing,
            provider=self.provider,
            teacher=self.teacher_user,
            headline="현장 대응이 빠르고 안정적이었습니다",
            body="시간 배분이 잘 되어 있어서 학급 운영이 편했습니다.",
            recommended_for="학년 행사, 교실 순환형 체험",
            status=InquiryReview.Status.PUBLISHED,
        )
        pending_teacher = create_user_with_role(username="teacher-review-pending", role="school", nickname="다른 교사")
        pending_thread = self._create_agreed_thread(
            teacher=pending_teacher,
            school_region="서울 강서구",
            target_audience="초등 4학년 2개 반",
        )
        InquiryReview.objects.create(
            thread=pending_thread,
            listing=self.listing,
            provider=self.provider,
            teacher=pending_teacher,
            headline="아직 공개되면 안 되는 후기",
            body="운영 검토 전 후기입니다.",
            recommended_for="검토 전",
            status=InquiryReview.Status.PENDING,
        )

        response = self.client.get(reverse("schoolprograms:provider_detail", args=[self.provider.slug]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "실제 진행 후 공개된 후기")
        self.assertContains(response, "현장 대응이 빠르고 안정적이었습니다")
        self.assertContains(response, "학년 행사, 교실 순환형 체험")
        self.assertNotContains(response, "아직 공개되면 안 되는 후기")

    def test_teacher_cannot_leave_review_before_agreement(self):
        self.client.force_login(self.teacher_user)
        self.client.post(reverse("schoolprograms:create_inquiry", args=[self.listing.slug]), self._inquiry_payload())
        thread = InquiryThread.objects.get(listing=self.listing, teacher=self.teacher_user)

        response = self.client.post(
            reverse("schoolprograms:teacher_inquiry_detail", args=[thread.id]),
            {
                "action": "save_review",
                "headline": "미리 남기면 안 되는 후기",
                "body": "합의 전 후기",
                "recommended_for": "",
            },
        )

        self.assertRedirects(response, reverse("schoolprograms:teacher_inquiry_detail", args=[thread.id]))
        self.assertFalse(InquiryReview.objects.filter(thread=thread).exists())

    def test_teacher_can_hold_proposal_and_thread_moves_to_hold_bucket(self):
        self.client.force_login(self.teacher_user)
        self.client.post(reverse("schoolprograms:create_inquiry", args=[self.listing.slug]), self._inquiry_payload())
        thread = InquiryThread.objects.get(listing=self.listing, teacher=self.teacher_user)

        self.client.force_login(self.company_user)
        self.client.post(
            reverse("schoolprograms:vendor_inquiry_detail", args=[thread.id]),
            {
                "action": "proposal",
                "price_text": "총액 140만원부터 또는 학급당 35만원",
                "included_items": "강사 파견, 체험 재료, 사후 정리",
                "schedule_note": "5월 둘째 주 화·수 오전 가능",
                "preparation_note": "빔프로젝터와 책상 배치만 부탁드립니다.",
                "followup_request": "정확한 반 수와 강당 여부를 알려 주세요.",
            },
        )

        self.client.force_login(self.teacher_user)
        response = self.client.post(
            reverse("schoolprograms:teacher_inquiry_detail", args=[thread.id]),
            {"action": "hold_proposal"},
        )

        self.assertRedirects(response, reverse("schoolprograms:teacher_inquiry_detail", args=[thread.id]))
        thread.refresh_from_db()
        self.assertEqual(thread.status, InquiryThread.Status.ON_HOLD)
        self.assertEqual(thread.teacher_bucket, "hold")
        self.assertEqual(thread.vendor_bucket, "hold")

        teacher_inquiries = self.client.get(reverse("schoolprograms:teacher_inquiries"), {"tab": "hold"})
        self.assertContains(teacher_inquiries, "보류 중")
        self.assertContains(teacher_inquiries, "찾아오는 과학 체험")

    def test_teacher_can_request_revision_and_thread_returns_to_progress(self):
        self.client.force_login(self.teacher_user)
        self.client.post(reverse("schoolprograms:create_inquiry", args=[self.listing.slug]), self._inquiry_payload())
        thread = InquiryThread.objects.get(listing=self.listing, teacher=self.teacher_user)

        self.client.force_login(self.company_user)
        self.client.post(
            reverse("schoolprograms:vendor_inquiry_detail", args=[thread.id]),
            {
                "action": "proposal",
                "price_text": "총액 140만원부터 또는 학급당 35만원",
                "included_items": "강사 파견, 체험 재료, 사후 정리",
                "schedule_note": "5월 둘째 주 화·수 오전 가능",
                "preparation_note": "빔프로젝터와 책상 배치만 부탁드립니다.",
                "followup_request": "정확한 반 수와 강당 여부를 알려 주세요.",
            },
        )

        self.client.force_login(self.teacher_user)
        response = self.client.post(
            reverse("schoolprograms:teacher_inquiry_detail", args=[thread.id]),
            {"action": "request_revision"},
        )

        self.assertRedirects(response, reverse("schoolprograms:teacher_inquiry_detail", args=[thread.id]))
        thread.refresh_from_db()
        self.assertEqual(thread.status, InquiryThread.Status.IN_PROGRESS)
        self.assertEqual(thread.teacher_bucket, "progress")
        self.assertEqual(thread.vendor_bucket, "progress")
        self.assertIn("재협의 요청", thread.last_message_preview)


class SchoolProgramsSavedListingTests(TestCase):
    def setUp(self):
        self.client = self.client_class()
        self.company_user, self.provider = create_provider(username="vendor4", provider_name="교실 체험랩")
        self.teacher_user = create_user_with_role(username="teacher3", role="school", nickname="교사")
        self.listing = create_listing(provider=self.provider, title="찾아오는 협동 놀이")
        self.second_listing = create_listing(
            provider=self.provider,
            title="교사 리더십 연수",
            category=ProgramListing.Category.TEACHER_TRAINING,
            province="seoul",
            city="강서구",
            theme_tags=["리더십", "연수"],
            grade_bands=["teacher_only"],
            delivery_mode=ProgramListing.DeliveryMode.HYBRID,
        )
        self.third_listing = create_listing(
            provider=self.provider,
            title="스포츠데이 챌린지",
            category=ProgramListing.Category.SPORTS_DAY,
            province="gyeonggi",
            city="성남",
            theme_tags=["스포츠", "협동"],
        )
        self.fourth_listing = create_listing(
            provider=self.provider,
            title="찾아오는 안전 체험",
            category=ProgramListing.Category.FIELDTRIP,
            province="incheon",
            city="연수구",
            theme_tags=["안전", "체험"],
        )

    def test_teacher_can_save_and_unsave_listing(self):
        self.client.force_login(self.teacher_user)

        save_response = self.client.post(
            reverse("schoolprograms:toggle_saved_listing", args=[self.listing.slug]),
            {"next": reverse("schoolprograms:teacher_saved_listings")},
        )

        self.assertRedirects(save_response, reverse("schoolprograms:teacher_saved_listings"))
        self.assertTrue(SavedListing.objects.filter(user=self.teacher_user, listing=self.listing).exists())

        saved_page = self.client.get(reverse("schoolprograms:teacher_saved_listings"))
        self.assertEqual(saved_page.status_code, 200)
        self.assertEqual(saved_page["X-Robots-Tag"], "noindex, nofollow")
        self.assertContains(saved_page, "찾아오는 협동 놀이")

        unsave_response = self.client.post(
            reverse("schoolprograms:toggle_saved_listing", args=[self.listing.slug]),
            {"next": reverse("schoolprograms:teacher_saved_listings")},
        )
        self.assertRedirects(unsave_response, reverse("schoolprograms:teacher_saved_listings"))
        self.assertFalse(SavedListing.objects.filter(user=self.teacher_user, listing=self.listing).exists())

    def test_anonymous_redirects_and_company_is_forbidden(self):
        anonymous_response = self.client.post(reverse("schoolprograms:toggle_saved_listing", args=[self.listing.slug]))
        self.assertEqual(anonymous_response.status_code, 302)
        self.assertIn(reverse("account_login"), anonymous_response.url)

        self.client.force_login(self.company_user)
        company_response = self.client.post(reverse("schoolprograms:toggle_saved_listing", args=[self.listing.slug]))
        self.assertEqual(company_response.status_code, 403)

    def test_saved_page_supports_teacher_filters(self):
        self.client.force_login(self.teacher_user)
        SavedListing.objects.bulk_create(
            [
                SavedListing(user=self.teacher_user, listing=self.listing),
                SavedListing(user=self.teacher_user, listing=self.second_listing),
                SavedListing(user=self.teacher_user, listing=self.third_listing),
            ]
        )

        response = self.client.get(
            reverse("schoolprograms:teacher_saved_listings"),
            {
                "province": "gyeonggi",
                "region_text": "수원",
                "category": ProgramListing.Category.FIELDTRIP,
                "grade_band": "elementary_high",
                "delivery_mode": ProgramListing.DeliveryMode.VISITING,
                "q": "협동",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "찾아오는 협동 놀이")
        self.assertNotContains(response, "교사 리더십 연수")
        self.assertNotContains(response, "스포츠데이 챌린지")

    def test_teacher_can_build_compare_list_up_to_three_items(self):
        self.client.force_login(self.teacher_user)

        for listing in [self.listing, self.second_listing, self.third_listing]:
            response = self.client.post(
                reverse("schoolprograms:toggle_compare_listing", args=[listing.slug]),
                {"next": reverse("schoolprograms:teacher_compare_listings")},
            )
            self.assertRedirects(response, reverse("schoolprograms:teacher_compare_listings"))

        overflow_response = self.client.post(
            reverse("schoolprograms:toggle_compare_listing", args=[self.fourth_listing.slug]),
            {"next": reverse("schoolprograms:teacher_compare_listings")},
        )
        self.assertRedirects(overflow_response, reverse("schoolprograms:teacher_compare_listings"))

        compare_page = self.client.get(reverse("schoolprograms:teacher_compare_listings"))
        self.assertEqual(compare_page.status_code, 200)
        self.assertEqual(compare_page["X-Robots-Tag"], "noindex, nofollow")
        self.assertContains(compare_page, "찾아오는 협동 놀이")
        self.assertContains(compare_page, "교사 리더십 연수")
        self.assertContains(compare_page, "스포츠데이 챌린지")
        self.assertNotContains(compare_page, "찾아오는 안전 체험")

        session = self.client.session
        self.assertEqual(len(session["schoolprograms_compare_listing_ids"]), 3)

    def test_compare_requires_teacher_role(self):
        anonymous_response = self.client.post(reverse("schoolprograms:toggle_compare_listing", args=[self.listing.slug]))
        self.assertEqual(anonymous_response.status_code, 302)
        self.assertIn(reverse("account_login"), anonymous_response.url)

        self.client.force_login(self.company_user)
        company_toggle = self.client.post(reverse("schoolprograms:toggle_compare_listing", args=[self.listing.slug]))
        self.assertEqual(company_toggle.status_code, 403)

        company_page = self.client.get(reverse("schoolprograms:teacher_compare_listings"))
        self.assertEqual(company_page.status_code, 403)

    def test_teacher_can_send_inquiry_directly_from_compare_page(self):
        self.client.force_login(self.teacher_user)
        session = self.client.session
        session["schoolprograms_compare_listing_ids"] = [self.listing.id, self.second_listing.id]
        session.save()

        response = self.client.post(
            reverse("schoolprograms:create_compare_inquiry", args=[self.second_listing.slug]),
            {
                f"compare-{self.second_listing.id}-school_region": "서울 강서구",
                f"compare-{self.second_listing.id}-preferred_schedule": "6월 첫째 주 오후",
                f"compare-{self.second_listing.id}-target_audience": "교직원 25명",
                f"compare-{self.second_listing.id}-expected_participants": 25,
                f"compare-{self.second_listing.id}-budget_text": "총액 90만원대 희망",
                f"compare-{self.second_listing.id}-request_message": "교사 연수실 진행 가능 여부를 알고 싶습니다.",
            },
        )

        thread = InquiryThread.objects.get(listing=self.second_listing, teacher=self.teacher_user)
        self.assertRedirects(response, reverse("schoolprograms:teacher_inquiry_detail", args=[thread.id]))
        self.assertEqual(thread.category, self.second_listing.category)
        self.assertEqual(thread.school_region, "서울 강서구")

    def test_compare_inquiry_shows_errors_on_same_page(self):
        self.client.force_login(self.teacher_user)
        session = self.client.session
        session["schoolprograms_compare_listing_ids"] = [self.listing.id]
        session.save()

        response = self.client.post(
            reverse("schoolprograms:create_compare_inquiry", args=[self.listing.slug]),
            {
                f"compare-{self.listing.id}-school_region": "",
                f"compare-{self.listing.id}-preferred_schedule": "5월",
                f"compare-{self.listing.id}-target_audience": "초등 5학년",
                f"compare-{self.listing.id}-expected_participants": "",
                f"compare-{self.listing.id}-budget_text": "",
                f"compare-{self.listing.id}-request_message": "",
            },
        )

        self.assertEqual(response.status_code, 400)
        compare_entries = response.context["compare_entries"]
        self.assertEqual(len(compare_entries), 1)
        self.assertIn("school_region", compare_entries[0]["form"].errors)
        self.assertIn("request_message", compare_entries[0]["form"].errors)


class SchoolProgramsVendorWorkflowTests(TestCase):
    def setUp(self):
        self.client = self.client_class()
        self.company_user, self.provider = create_provider(username="vendor5", provider_name="안전 체험 스튜디오")
        self.rejected_listing = create_listing(
            provider=self.provider,
            title="수정 필요한 체험",
            approval_status=ProgramListing.ApprovalStatus.REJECTED,
            admin_note="안전 운영 문구와 준비물 범위를 조금 더 구체적으로 적어 주세요.",
        )
        self.approved_listing = create_listing(
            provider=self.provider,
            title="공개중 체험",
            approval_status=ProgramListing.ApprovalStatus.APPROVED,
        )

    def test_vendor_dashboard_shows_action_items_and_admin_note(self):
        self.client.force_login(self.company_user)

        response = self.client.get(reverse("schoolprograms:vendor_dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "지금 해야 할 일")
        self.assertContains(response, "수정 필요한 체험")
        self.assertContains(response, "안전 운영 문구와 준비물 범위를 조금 더 구체적으로 적어 주세요.")

    def test_approved_listing_edit_keeps_public_save_flow(self):
        self.client.force_login(self.company_user)

        get_response = self.client.get(reverse("schoolprograms:vendor_listing_edit", args=[self.approved_listing.slug]))
        self.assertEqual(get_response.status_code, 200)
        self.assertContains(get_response, "공개 상태로 저장")
        self.assertNotContains(get_response, "수정 후 다시 심사 요청")

        post_response = self.client.post(
            reverse("schoolprograms:vendor_listing_edit", args=[self.approved_listing.slug]),
            {
                "title": self.approved_listing.title,
                "category": self.approved_listing.category,
                "summary": self.approved_listing.summary,
                "description": self.approved_listing.description,
                "theme_tags_text": self.approved_listing.theme_tags_text,
                "grade_bands": self.approved_listing.grade_bands,
                "delivery_mode": self.approved_listing.delivery_mode,
                "province": self.approved_listing.province,
                "city": self.approved_listing.city,
                "coverage_note": self.approved_listing.coverage_note,
                "duration_text": self.approved_listing.duration_text,
                "capacity_text": self.approved_listing.capacity_text,
                "price_text": self.approved_listing.price_text,
                "safety_info": self.approved_listing.safety_info,
                "materials_info": self.approved_listing.materials_info,
                "faq": self.approved_listing.faq,
                "action": "save",
            },
        )

        self.assertRedirects(post_response, reverse("schoolprograms:vendor_listing_edit", args=[self.approved_listing.slug]))
        self.approved_listing.refresh_from_db()
        self.assertEqual(self.approved_listing.approval_status, ProgramListing.ApprovalStatus.APPROVED)

    def test_vendor_without_profile_ready_cannot_submit_review_yet(self):
        incomplete_user, incomplete_provider = create_provider(
            username="vendor-incomplete",
            provider_name="미완료 업체",
            summary="",
            verified=False,
        )
        self.client.force_login(incomplete_user)

        dashboard = self.client.get(reverse("schoolprograms:vendor_dashboard"))
        self.assertEqual(dashboard.status_code, 200)
        self.assertContains(dashboard, "회사 정보 먼저 입력")

        response = self.client.post(
            reverse("schoolprograms:vendor_listing_create"),
            {
                "title": "심사 보내려는 프로그램",
                "category": ProgramListing.Category.FIELDTRIP,
                "summary": "대표 소개",
                "description": "상세 설명",
                "theme_tags_text": "환경, 생태",
                "grade_bands": ["elementary_high"],
                "delivery_mode": ProgramListing.DeliveryMode.VISITING,
                "province": "gyeonggi",
                "city": "수원",
                "coverage_note": "수원·용인",
                "duration_text": "90분",
                "capacity_text": "학급당 30명",
                "price_text": "학급당 35만원",
                "safety_info": "안전 운영 정보",
                "materials_info": "준비물 정보",
                "faq": "FAQ",
                "action": "submit",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "회사 정보와 증빙 서류를 먼저 완료해 주세요.")
        self.assertFalse(ProgramListing.objects.filter(provider=incomplete_provider, title="심사 보내려는 프로그램").exists())

    def test_vendor_can_upload_supported_attachments_and_remove_existing_one(self):
        existing_attachment = create_attachment(listing=self.approved_listing, name="old-guide.pdf")
        self.client.force_login(self.company_user)

        response = self.client.post(
            reverse("schoolprograms:vendor_listing_edit", args=[self.approved_listing.slug]),
            {
                "title": self.approved_listing.title,
                "category": self.approved_listing.category,
                "summary": self.approved_listing.summary,
                "description": self.approved_listing.description,
                "theme_tags_text": self.approved_listing.theme_tags_text,
                "grade_bands": self.approved_listing.grade_bands,
                "delivery_mode": self.approved_listing.delivery_mode,
                "province": self.approved_listing.province,
                "city": self.approved_listing.city,
                "coverage_note": self.approved_listing.coverage_note,
                "duration_text": self.approved_listing.duration_text,
                "capacity_text": self.approved_listing.capacity_text,
                "price_text": self.approved_listing.price_text,
                "safety_info": self.approved_listing.safety_info,
                "materials_info": self.approved_listing.materials_info,
                "faq": self.approved_listing.faq,
                "attachments": [
                    SimpleUploadedFile("program-guide.pdf", b"%PDF-1.4 demo", content_type="application/pdf"),
                    SimpleUploadedFile(
                        "program-sheet.hwpx",
                        b"demo hwpx bytes",
                        content_type="application/octet-stream",
                    ),
                ],
                "remove_attachment_ids": [str(existing_attachment.id)],
                "action": "save",
            },
        )

        self.assertRedirects(response, reverse("schoolprograms:vendor_listing_edit", args=[self.approved_listing.slug]))
        self.assertFalse(ListingAttachment.objects.filter(pk=existing_attachment.pk).exists())
        uploaded_names = set(self.approved_listing.attachments.values_list("original_name", flat=True))
        self.assertIn("program-guide.pdf", uploaded_names)
        self.assertIn("program-sheet.hwpx", uploaded_names)

    def test_vendor_attachment_rejects_unsupported_extension(self):
        self.client.force_login(self.company_user)

        response = self.client.post(
            reverse("schoolprograms:vendor_listing_edit", args=[self.approved_listing.slug]),
            {
                "title": self.approved_listing.title,
                "category": self.approved_listing.category,
                "summary": self.approved_listing.summary,
                "description": self.approved_listing.description,
                "theme_tags_text": self.approved_listing.theme_tags_text,
                "grade_bands": self.approved_listing.grade_bands,
                "delivery_mode": self.approved_listing.delivery_mode,
                "province": self.approved_listing.province,
                "city": self.approved_listing.city,
                "coverage_note": self.approved_listing.coverage_note,
                "duration_text": self.approved_listing.duration_text,
                "capacity_text": self.approved_listing.capacity_text,
                "price_text": self.approved_listing.price_text,
                "safety_info": self.approved_listing.safety_info,
                "materials_info": self.approved_listing.materials_info,
                "faq": self.approved_listing.faq,
                "attachments": [
                    SimpleUploadedFile("malware.exe", b"demo", content_type="application/octet-stream"),
                ],
                "action": "save",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "첨부 자료는 .hwp, .hwpx, .jpeg, .jpg, .pdf, .png 형식만 올릴 수 있습니다.")
        self.assertEqual(self.approved_listing.attachments.count(), 0)

    def test_public_attachment_download_returns_attachment_response(self):
        attachment = create_attachment(
            listing=self.approved_listing,
            name="event-guide.pdf",
            content=b"%PDF-1.4 event guide",
            content_type="application/pdf",
        )

        response = self.client.get(
            reverse("schoolprograms:download_listing_attachment", args=[self.approved_listing.slug, attachment.id])
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["X-Robots-Tag"], "noindex, nofollow")
        self.assertIn("attachment;", response["Content-Disposition"])
        self.assertIn("event-guide.pdf", response["Content-Disposition"])
