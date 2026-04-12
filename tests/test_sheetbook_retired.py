from django.test import TestCase
from django.urls import reverse


class SheetbookRetiredRouteTests(TestCase):
    def test_index_route_renders_retired_notice(self):
        response = self.client.get(reverse("sheetbook:index"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "학급 기록 보드는 종료되었습니다.")
        self.assertContains(response, reverse("home"))

    def test_detail_route_renders_retired_notice(self):
        response = self.client.get(reverse("sheetbook:detail", kwargs={"pk": 1}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "서비스 종료")

    def test_unknown_legacy_path_is_captured(self):
        response = self.client.get("/sheetbook/legacy/deep/link/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "오늘 일정 보기")
