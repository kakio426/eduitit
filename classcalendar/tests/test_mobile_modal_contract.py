from pathlib import Path

from django.test import SimpleTestCase


class CalendarMobileModalContractTests(SimpleTestCase):
    def test_compact_mobile_uses_modal_instead_of_inline_agenda_panel(self):
        template_path = (
            Path(__file__).resolve().parents[1]
            / "templates"
            / "classcalendar"
            / "_calendar_app.html"
        )
        content = template_path.read_text(encoding="utf-8")

        self.assertIn("if (this.isCompactMobileViewport()) {", content)
        self.assertIn("this.openDayOverview(date, triggerEvent);", content)
        self.assertIn("isCompactHomeSurfaceViewport()", content)
        self.assertIn("window.matchMedia('(max-width: 1099px)').matches", content)
        self.assertIn("return this.calendarEmbedMode === 'home' && !this.isCompactHomeSurfaceViewport();", content)
        self.assertNotIn('x-ref="selectedDateAgenda"', content)
        self.assertNotIn("scrollSelectedDateAgendaIntoView()", content)
        self.assertNotIn(".classcalendar-mobile-agenda", content)
