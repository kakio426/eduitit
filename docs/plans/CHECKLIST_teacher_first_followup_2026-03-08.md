## Teacher-First Follow-Up Checklist

### Scope
- `classcalendar`
- `sheetbook`

### Goals
- Remove remaining bridge-style teacher guidance screens from the core flow.
- Demote rare admin tools so calendar use starts with calendar work, not setup.
- Keep sheetbook focused on the current task instead of management UI.
- Lock the resulting structure with contract tests.

### Implementation Checklist
- [x] `classcalendar:sheetbook_entry` no longer depends on a teacher-facing bridge screen.
- [x] Calendar admin tools stay behind a secondary container and each area is individually collapsed.
- [x] `sheetbook` calendar tab shows primary actions first and settings only as a secondary action.
- [x] `sheetbook` detail view removes top-level tab-management CTA duplication.
- [x] Grid secondary tools move behind a compact `더보기` container.
- [x] Regression tests cover:
  - [x] no bridge CTA screen in the teacher flow
  - [x] collapsed admin tools
  - [x] sheetbook calendar tab keeps only primary actions up front
  - [x] sheetbook detail demotes tab management

### Verification
- [x] `python manage.py check`
- [x] `python manage.py test tests.test_sheetbook_navigation_contracts classcalendar.tests.test_sheetbook_bridge sheetbook.tests -v 1`
- [x] `git diff --check`
