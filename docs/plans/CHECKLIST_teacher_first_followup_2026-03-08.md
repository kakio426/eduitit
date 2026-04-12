## Teacher-First Follow-Up Checklist

### Scope
- `classcalendar`
- `classroom_workspace`

### Goals
- Remove remaining bridge-style teacher guidance screens from the core flow.
- Demote rare admin tools so calendar use starts with calendar work, not setup.
- Keep classroom_workspace focused on the current task instead of management UI.
- Lock the resulting structure with contract tests.

### Implementation Checklist
- [x] `classcalendar:entry` no longer depends on a teacher-facing bridge screen.
- [x] Calendar admin tools stay behind a secondary container and each area is individually collapsed.
- [x] `classroom_workspace` calendar tab shows primary actions first and settings only as a secondary action.
- [x] `classroom_workspace` detail view removes top-level tab-management CTA duplication.
- [x] Grid secondary tools move behind a compact `더보기` container.
- [x] Regression tests cover:
  - [x] no bridge CTA screen in the teacher flow
  - [x] collapsed admin tools
  - [x] classroom_workspace calendar tab keeps only primary actions up front
  - [x] classroom_workspace detail demotes tab management

### Verification
- [x] `python manage.py check`
- [x] `python manage.py test classcalendar.tests.test_entry_route classcalendar.tests.test_entry_route classroom_workspace.tests -v 1`
- [x] `git diff --check`
