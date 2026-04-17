from pathlib import Path

from django.test import SimpleTestCase


class CalendarDayModalContractTests(SimpleTestCase):
    def test_day_modal_uses_condensed_direct_hub_display_items(self):
        template_path = (
            Path(__file__).resolve().parents[1]
            / "templates"
            / "classcalendar"
            / "_calendar_app.html"
        )
        content = template_path.read_text(encoding="utf-8")

        self.assertIn("getSelectedDateDirectHubDisplayItems()", content)
        self.assertIn("openSelectedDateHubItem(item.clickItem || item, $event)", content)
        self.assertIn("item.isCondensedReservation", content)
        self.assertIn("item.displayCountLabel", content)

    def test_day_modal_can_group_reservation_periods(self):
        template_path = (
            Path(__file__).resolve().parents[1]
            / "templates"
            / "classcalendar"
            / "_calendar_app.html"
        )
        content = template_path.read_text(encoding="utf-8")

        self.assertIn("extractReservationPeriodLabel(item)", content)
        self.assertIn("formatReservationPeriodSummary(periodLabels)", content)
        self.assertIn("buildCondensedReservationHubItem(items)", content)
        self.assertIn("reservation-group:", content)
