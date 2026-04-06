from datetime import date

from django.test import TestCase
from django.urls import reverse

from portfolio.models import Achievement, AchievementPhoto


class AchievementGalleryModelTests(TestCase):
    def test_gallery_images_include_cover_then_sorted_extra_photos(self):
        achievement = Achievement.objects.create(
            title="AI 연수 운영",
            issuer="경기교육청",
            date_awarded=date(2026, 3, 1),
            image="portfolio/achievements/cover.jpg",
        )

        AchievementPhoto.objects.create(
            achievement=achievement,
            image="portfolio/achievements/second.jpg",
            caption="현장 사진 2",
            sort_order=20,
        )
        AchievementPhoto.objects.create(
            achievement=achievement,
            image="portfolio/achievements/first.jpg",
            caption="현장 사진 1",
            sort_order=10,
        )

        gallery_images = achievement.gallery_images

        self.assertEqual(len(gallery_images), 3)
        self.assertEqual(gallery_images[0]["caption"], "")
        self.assertTrue(gallery_images[0]["is_cover"])
        self.assertEqual(
            [item["caption"] for item in gallery_images[1:]],
            ["현장 사진 1", "현장 사진 2"],
        )


class PortfolioGalleryViewTests(TestCase):
    def test_portfolio_list_renders_additional_photo_captions(self):
        achievement = Achievement.objects.create(
            title="AI 수업 컨설팅",
            issuer="테스트 학교",
            date_awarded=date(2026, 4, 1),
            description="대표 실적 설명",
            image="portfolio/achievements/main.jpg",
        )
        AchievementPhoto.objects.create(
            achievement=achievement,
            image="portfolio/achievements/detail-1.jpg",
            caption="교실 적용 장면",
            sort_order=1,
        )
        AchievementPhoto.objects.create(
            achievement=achievement,
            image="portfolio/achievements/detail-2.jpg",
            caption="학생 결과물",
            sort_order=2,
        )

        response = self.client.get(reverse("portfolio:list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "AI 수업 컨설팅")
        self.assertContains(response, "교실 적용 장면")
        self.assertContains(response, "학생 결과물")
