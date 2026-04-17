from pathlib import Path

from django.test import SimpleTestCase


class CalendarHomeWorkweekLayoutContractTests(SimpleTestCase):
    def test_content_shell_allows_day_hitcell_click_through(self):
        template_path = (
            Path(__file__).resolve().parents[1]
            / "templates"
            / "classcalendar"
            / "_calendar_app.html"
        )
        content = template_path.read_text(encoding="utf-8")

        self.assertIn(".classcalendar-home-workweek-content {", content)
        self.assertIn("pointer-events: none;", content)
        self.assertIn(".classcalendar-home-workweek-item {", content)
        self.assertIn("pointer-events: auto;", content)

    def test_range_items_stay_within_their_grid_track(self):
        template_path = (
            Path(__file__).resolve().parents[1]
            / "templates"
            / "classcalendar"
            / "_calendar_app.html"
        )
        content = template_path.read_text(encoding="utf-8")

        self.assertIn("box-sizing: border-box;", content)
        self.assertIn("width: calc(100% - 0.44rem);", content)
        self.assertIn("justify-self: center;", content)
        self.assertIn("margin: 0 0 0.24rem;", content)
        self.assertNotIn("margin: 0 0.22rem 0.24rem;", content)
