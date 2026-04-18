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

    def test_event_forms_hide_color_picker_ui(self):
        template_path = (
            Path(__file__).resolve().parents[1]
            / "templates"
            / "classcalendar"
            / "_calendar_app.html"
        )
        content = template_path.read_text(encoding="utf-8")

        self.assertNotIn('x-model="createForm.color"', content)
        self.assertNotIn('x-model="editForm.color"', content)
        self.assertIn("body.set('color', this.createForm.color);", content)
        self.assertIn("body.set('color', this.editForm.color);", content)

    def test_day_modal_uses_narrower_width_for_forms_than_overview(self):
        template_path = (
            Path(__file__).resolve().parents[1]
            / "templates"
            / "classcalendar"
            / "_calendar_app.html"
        )
        content = template_path.read_text(encoding="utf-8")

        self.assertIn("dayModalMode === 'create' || dayModalMode === 'edit'", content)
        self.assertIn("'max-w-3xl'", content)
        self.assertIn("dayModalMode === 'confirm-delete' ? 'max-w-xl' : 'max-w-4xl'", content)
