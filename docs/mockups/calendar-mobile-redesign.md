# Calendar Mobile Redesign

## Target

- target_app: `classcalendar`
- do_not_touch_apps: other apps, global settings, shared base layout

## Current Problems

1. Mobile month cells are too narrow for both the date chip and the item-count pill on the same row.
2. The count pill and marker dots repeat the same signal inside a very small space.
3. The current tap flow jumps straight into a modal, so the selected-day context is not visible on the page itself.
4. The primary mobile task should be "pick a date, confirm what is there, then act", but the current structure makes the tiny cell carry too much of that burden.

## Keep / Remove / Merge

- Keep: familiar month grid, today highlight, selected-date state, day modal for deep detail/edit flows
- Remove from mobile cells: side-by-side date + count layout
- Merge below the grid: selected-day summary, quick actions, first few items
- Demote inside the cell: detailed meaning stays as a count pill and marker dots only

## Reference Review

1. Google Calendar
   - Source: https://apps.apple.com/my/app/google-calendar-get-organised/id909319292
   - Pattern to borrow: a month view that stays lightweight and lets users switch views quickly without overloading each day cell
2. Apple Calendar on iPhone
   - Source: https://support.apple.com/en-afri/guide/iphone/iphfd1054569/ios
   - Pattern to borrow: month cells can stay compact while detail density moves outside the tiny grid cell
3. Outlook Mobile
   - Source: https://support.microsoft.com/en-us/office/how-do-i-switch-to-month-view-ba6469a3-6bd2-4927-9d66-1ce737390be2
   - Pattern to borrow: selected-day detail is separated from the month grid, which keeps scanning easy
4. NAVER Calendar
   - Source: https://apps.apple.com/us/app/naver-calendar/id592346243
   - Pattern to borrow: monthly view plus an upward detail area, and easy single-date composition from the month surface
5. TimeTree
   - Source: https://support.timetreeapp.com/hc/en-us/articles/900004492623-How-to-use-shared-calendar-app-
   - Pattern to borrow: month jump, current-day recovery, quick create, and a visible activity/detail area outside the cell

## Text Wireframes

### Option A: Compact Stack

```text
[Month toolbar]
[Month grid]
  [10]
  [2]
  [dots]
[Open details button]
```

- Strongest point: smallest implementation change
- Weakness: detail still feels one step away

### Option B: Selected-Day Agenda

```text
[Month toolbar]
[Month grid]
  [10]
  [2]
  [dots]
[Selected day card]
  [Mar 10 Tue]
  [2 events] [1 task] [Add]
  [preview item]
  [preview item]
  [Open full details]
```

- Strongest point: clean month grid plus immediate day context
- Weakness: needs a small interaction change on mobile

### Option C: Task-First Strip

```text
[Today / urgent strip]
[Month grid]
  [10] [2]
[Task-focused card]
```

- Strongest point: very action-oriented
- Weakness: feels heavier and less calendar-first

## Chosen Direction

- Choice: Option B, `Selected-Day Agenda`
- Why it fits this service:
  - Teachers still get the familiar month grid first
  - The mobile cell no longer has to carry both status and detail
  - The selected date becomes visible without requiring explanation text
  - It matches the current modal architecture, so we can keep deep flows stable while improving the page-level experience

## Implementation Checklist

- Make the mobile day cell header stack vertically
- Keep desktop day-cell layout unchanged
- Add a mobile-only selected-day agenda card below the month grid
- On mobile, tapping a day should select it and update the agenda card
- Keep explicit actions for `full details` and `add schedule`
- Reuse existing selected-date data helpers instead of creating a second state source
- Run Django checks and targeted calendar tests
