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
        self.assertIn(".classcalendar-home-workweek-content {", content)
        self.assertIn("padding: 2.28rem 0 0.62rem;", content)
        self.assertIn("padding: 2.38rem 0 0.68rem;", content)
        self.assertIn(".classcalendar-home-workweek-range-grid {", content)
        self.assertIn("padding: 0;", content)
        self.assertNotIn("padding: 2.28rem 0.4rem 0.62rem;", content)
        self.assertNotIn("padding: 2.38rem 0.46rem 0.68rem;", content)
        self.assertNotIn("margin: 0 0.22rem 0.24rem;", content)

    def test_desktop_workweek_keeps_first_four_single_day_items_in_top_stack(self):
        template_path = (
            Path(__file__).resolve().parents[1]
            / "templates"
            / "classcalendar"
            / "_calendar_app.html"
        )
        content = template_path.read_text(encoding="utf-8")

        self.assertIn("getHomeWorkweekTopLimit() {", content)
        self.assertIn("return this.isCompactMobileViewport() ? 1 : 4;", content)
        self.assertIn("getHomeWorkweekBottomLimit() {", content)
        self.assertIn("return this.isCompactMobileViewport() ? 1 : 0;", content)
        self.assertIn(".classcalendar-home-workweek-day-stack--primary {", content)
        self.assertIn("min-height: 6.36rem;", content)
        self.assertIn("min-height: 6.52rem;", content)
        self.assertIn(".classcalendar-home-workweek-day-stack--secondary {", content)
        self.assertIn("min-height: 2.04rem;", content)
        self.assertIn("min-height: 2.16rem;", content)
        self.assertIn("x-show=\"!week.showSecondaryRow && week.dayBuckets[dateKey(date)].overflow > 0\"", content)
        self.assertIn("showSecondaryRow: Object.values(dayBuckets).some((bucket) => bucket.secondary.length > 0),", content)

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

    def test_home_calendar_today_uses_distinct_cell_and_badge_states(self):
        template_path = (
            Path(__file__).resolve().parents[1]
            / "templates"
            / "classcalendar"
            / "_calendar_app.html"
        )
        content = template_path.read_text(encoding="utf-8")

        self.assertIn(".classcalendar-home-workweek-hitcell.is-today {", content)
        self.assertIn("background: linear-gradient(180deg, rgba(239, 246, 255, 0.88) 0%, rgba(255, 255, 255, 0) 38%);", content)
        self.assertIn(".classcalendar-home-workweek-date.is-today {", content)
        self.assertIn("box-shadow: inset 0 0 0 1.5px #93c5fd, 0 1px 2px rgba(37, 99, 235, 0.08);", content)
        self.assertIn(".classcalendar-home-workweek-day-stack--today {", content)
        self.assertIn("padding-top: 0.58rem;", content)
        self.assertIn("isToday(date) ? 'is-today' : '',", content)
        self.assertIn(":class=\"isToday(date) ? 'classcalendar-home-workweek-day-stack--today' : ''\"", content)
        self.assertIn(".classcalendar-home-mobile-day--today {", content)
        self.assertIn(".classcalendar-home-mobile-day--today.classcalendar-home-mobile-day--selected {", content)

    def test_home_mobile_month_grid_matches_sunday_first_desktop_order(self):
        template_path = (
            Path(__file__).resolve().parents[1]
            / "templates"
            / "classcalendar"
            / "_calendar_app.html"
        )
        content = template_path.read_text(encoding="utf-8")

        self.assertIn("['일', '월', '화', '수', '목', '금', '토']", content)
        self.assertIn("start.setDate(start.getDate() - start.getDay());", content)
        self.assertIn("if (end.getDay() !== 6) end.setDate(end.getDate() + (6 - end.getDay()));", content)
        self.assertNotIn("const mondayOffset = first.getDay() === 0 ? 6 : first.getDay() - 1;", content)
        self.assertNotIn("const sundayOffset = last.getDay() === 0 ? 0 : 7 - last.getDay();", content)

    def test_month_preview_uses_compact_text_rows_without_splitting_range_flow(self):
        template_path = (
            Path(__file__).resolve().parents[1]
            / "templates"
            / "classcalendar"
            / "_calendar_app.html"
        )
        content = template_path.read_text(encoding="utf-8")

        self.assertIn(".classcalendar-day-range-row--continuation {", content)
        self.assertIn(".classcalendar-day-preview-marker {", content)
        self.assertIn(".classcalendar-day-preview-prefix {", content)
        self.assertIn("return this.isCompactMobileViewport() ? 2 : 5;", content)
        self.assertIn("const labeledRangeRows = [];", content)
        self.assertIn("const continuedRangeRows = [];", content)
        self.assertIn("rows.push(...labeledRangeRows);", content)
        self.assertIn("rows.push(...continuedRangeRows);", content)
        self.assertIn("row.showLabel ? '' : 'classcalendar-day-range-row--continuation'", content)
        self.assertIn("class=\"classcalendar-day-preview-marker\" :class=\"row.markerClass\"", content)
        self.assertIn("class=\"classcalendar-day-preview-prefix\" :class=\"row.prefixClass\" x-text=\"row.prefixText\"", content)
        self.assertIn("prefixText: this.getEventSourceLabel(event),", content)
        self.assertIn("markerClass: this.getDayEventPreviewMarkerClass(event),", content)
        self.assertIn("prefixClass: this.getDayEventPreviewPrefixClass(event),", content)
        self.assertIn("prefixText: item.serviceLabel,", content)
        self.assertIn("markerClass: this.getDayHubPreviewMarkerClass(item),", content)
        self.assertIn("prefixClass: this.getDayHubPreviewPrefixClass(item),", content)
