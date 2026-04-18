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

    def test_desktop_workweek_keeps_first_two_single_day_items_in_top_stack(self):
        template_path = (
            Path(__file__).resolve().parents[1]
            / "templates"
            / "classcalendar"
            / "_calendar_app.html"
        )
        content = template_path.read_text(encoding="utf-8")

        self.assertIn("getHomeWorkweekTopLimit() {", content)
        self.assertIn("return this.isCompactMobileViewport() ? 1 : 2;", content)
        self.assertIn("getHomeWorkweekBottomLimit() {", content)
        self.assertIn("return this.isCompactMobileViewport() ? 1 : 1;", content)
        self.assertIn(".classcalendar-home-workweek-day-stack--primary {", content)
        self.assertIn("min-height: 4.16rem;", content)
        self.assertIn("min-height: 4.4rem;", content)
        self.assertIn(".classcalendar-home-workweek-day-stack--secondary {", content)
        self.assertIn("min-height: 2.04rem;", content)
        self.assertIn("min-height: 2.16rem;", content)

    def test_repeated_reservations_are_condensed_in_home_workweek(self):
        template_path = (
            Path(__file__).resolve().parents[1]
            / "templates"
            / "classcalendar"
            / "_calendar_app.html"
        )
        content = template_path.read_text(encoding="utf-8")

        self.assertIn("getHomeWorkweekDisplayItems(items) {", content)
        self.assertIn("buildCondensedHomeWorkweekReservationItem(items) {", content)
        self.assertIn("home-week-reservation-group:", content)
        self.assertIn("displayTitle: `${firstItem.title || '특별실 예약'} ${countLabel}`", content)
        self.assertIn("displayTooltip: [firstItem.title || '특별실 예약', periodSummary, countLabel].filter(Boolean).join(' · ')", content)
        self.assertIn("item.displayTitle || item.title", content)
        self.assertIn("item.displayTooltip || item.title", content)
        self.assertIn("if (item.isReservationGroup && item.focusDateKey) {", content)
