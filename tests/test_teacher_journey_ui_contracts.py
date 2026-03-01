from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase


class TeacherJourneyUIContractTests(SimpleTestCase):
    def _read(self, relative_path: str) -> str:
        return (Path(settings.BASE_DIR) / relative_path).read_text(encoding="utf-8")

    def test_reservations_contracts(self):
        dashboard = self._read("reservations/templates/reservations/dashboard.html")
        booking_modal = self._read("reservations/templates/reservations/partials/booking_modal.html")
        room_list = self._read("reservations/templates/reservations/partials/room_list.html")
        blackout_list = self._read("reservations/templates/reservations/partials/blackout_list.html")
        reservation_grid = self._read("reservations/templates/reservations/partials/reservation_grid.html")
        recurring_matrix = self._read("reservations/templates/reservations/partials/recurring_matrix.html")

        self.assertIn("(새 탭)", dashboard)
        self.assertIn("hx-indicator=", booking_modal)
        self.assertIn("hx-disabled-elt=", booking_modal)
        self.assertIn("hx-on::response-error=", booking_modal)
        self.assertIn("hx-indicator=", room_list)
        self.assertIn("hx-disabled-elt=", room_list)
        self.assertIn("hx-indicator=", blackout_list)
        self.assertIn("hx-disabled-elt=", blackout_list)
        self.assertIn("hx-indicator=", reservation_grid)
        self.assertIn("hx-disabled-elt=", reservation_grid)
        self.assertIn("hx-indicator=", recurring_matrix)
        self.assertIn("hx-disabled-elt=", recurring_matrix)

    def test_happy_seed_contracts(self):
        classroom_detail = self._read("happy_seed/templates/happy_seed/classroom_detail.html")
        student_row = self._read("happy_seed/templates/happy_seed/partials/student_row.html")
        consent_row = self._read("happy_seed/templates/happy_seed/partials/consent_row.html")

        self.assertIn("(새 탭)", classroom_detail)
        self.assertIn("(새 탭)", consent_row)
        self.assertIn("hx-indicator=", classroom_detail)
        self.assertIn("hx-disabled-elt=", classroom_detail)
        self.assertIn("hx-indicator=", student_row)
        self.assertIn("hx-disabled-elt=", student_row)
        self.assertIn("hx-indicator=", consent_row)
        self.assertIn("hx-disabled-elt=", consent_row)
        self.assertIn("hx-on::response-error=", consent_row)

    def test_core_sns_contracts(self):
        sns_widget = self._read("core/templates/core/partials/sns_widget.html")
        sns_widget_mobile = self._read("core/templates/core/partials/sns_widget_mobile.html")
        post_item = self._read("core/templates/core/partials/post_item.html")
        comment_item = self._read("core/templates/core/partials/comment_item.html")
        post_edit_form = self._read("core/templates/core/partials/post_edit_form.html")
        comment_edit_form = self._read("core/templates/core/partials/comment_edit_form.html")
        dashboard_sns = self._read("core/templates/core/dashboard_sns.html")

        self.assertIn("hx-indicator=", sns_widget)
        self.assertIn("hx-disabled-elt=", sns_widget)
        self.assertIn("hx-indicator=", sns_widget_mobile)
        self.assertIn("hx-disabled-elt=", sns_widget_mobile)
        self.assertIn("(새 탭)", post_item)
        self.assertIn("hx-indicator=", post_item)
        self.assertIn("hx-disabled-elt=", post_item)
        self.assertIn("hx-indicator=", comment_item)
        self.assertIn("hx-disabled-elt=", comment_item)
        self.assertIn("hx-indicator=", post_edit_form)
        self.assertIn("hx-disabled-elt=", post_edit_form)
        self.assertIn("hx-indicator=", comment_edit_form)
        self.assertIn("hx-disabled-elt=", comment_edit_form)
        self.assertIn("hx-indicator=", dashboard_sns)
        self.assertIn("hx-disabled-elt=", dashboard_sns)

    def test_sheetbook_collect_classcalendar_contracts(self):
        sheetbook_detail = self._read("sheetbook/templates/sheetbook/detail.html")
        sheetbook_tab_list = self._read("sheetbook/templates/sheetbook/_tab_list.html")
        collect_submit = self._read("collect/templates/collect/submit.html")
        collect_submissions = self._read("collect/templates/collect/partials/submissions_list.html")
        classcalendar_main = self._read("classcalendar/templates/classcalendar/main.html")

        self.assertIn("hx-indicator=", sheetbook_detail)
        self.assertIn("hx-disabled-elt=", sheetbook_detail)
        self.assertIn("hx-indicator=", sheetbook_tab_list)
        self.assertIn("hx-disabled-elt=", sheetbook_tab_list)
        self.assertIn("(새 탭)", collect_submit)
        self.assertIn("(새 탭)", collect_submissions)
        self.assertIn("(새 탭)", classcalendar_main)
