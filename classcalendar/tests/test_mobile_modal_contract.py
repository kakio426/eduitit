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
        self.assertNotIn('x-ref="selectedDateAgenda"', content)
        self.assertNotIn("scrollSelectedDateAgendaIntoView()", content)
        self.assertNotIn(".classcalendar-mobile-agenda", content)

    def test_home_mobile_day_click_delegates_to_modal_handler(self):
        template_path = (
            Path(__file__).resolve().parents[1]
            / "templates"
            / "classcalendar"
            / "_calendar_app.html"
        )
        content = template_path.read_text(encoding="utf-8")

        self.assertIn('@click="selectHomeMobileDate(date, $event)"', content)
        self.assertIn(
            """        selectHomeMobileDate(date, triggerEvent = null) {
            if (!(date instanceof Date) || Number.isNaN(date.getTime()) || !this.isCurrentMonth(date)) return;
            this.handleDayCellClick(date, triggerEvent);
        },""",
            content,
        )

    def test_existing_day_uses_day_overview_before_create_on_desktop(self):
        template_path = (
            Path(__file__).resolve().parents[1]
            / "templates"
            / "classcalendar"
            / "_calendar_app.html"
        )
        content = template_path.read_text(encoding="utf-8")

        self.assertIn(
            """        handleDayCellClick(date, triggerEvent = null) {
            if (this.isCompactMobileViewport()) {
                if (this.hasDayOverviewContent(date)) {
                    this.openDayOverview(date, triggerEvent);
                    return;
                }
                this.openCreateModal(date, triggerEvent);
                return;
            }
            if (this.hasDayOverviewContent(date)) {
                this.openDayOverview(date, triggerEvent);
                return;
            }
            this.openCreateModal(date, triggerEvent);
        },""",
            content,
        )
