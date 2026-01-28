# PLAN: AI Service & Resource Optimization

## Overview
Optimization of AI response delivery via streaming, offloading image processing to client-side direct upload, and on-demand document generation.

## Rationale
- **Streaming**: Reduces perceived latency and prevents worker timeout.
- **Direct Upload**: Removes bandwidth/memory bottleneck from Django server.
- **Lazy Generation**: Optimizes CPU usage and accelerates the initial "save" action.

## Risk Assessment
| Risk | Probability | Impact | Mitigation |
| :--- | :--- | :--- | :--- |
| Cloudinary Unsigned Security | Medium | Low | Use strict domain validation in Django and Cloudinary upload presets. |
| Streaming Connection Timeout | Low | Medium | Implement robust client-side retry for chunked fetch. |
| Memory usage during PPT gen | Medium | High | Monitor Railway logs; if fails, consider separate worker service. |

## Phase Breakdown

### Phase 1: Foundation & Mocking
- **Goal**: Setup test structure for streaming and mock external APIs.
- **Test Strategy**: Unit tests for generators.
- [ ] [RED] Create `fortune/tests/test_streaming_logic.py` with failing cases for generator output.
- [ ] [RED] Create `autoarticle/tests/test_direct_upload.py` expecting Cloudinary URL input.
- [ ] [GREEN] Basic test infra passing.

### Phase 1: Foundation & Mocking
- **Goal**: AI Streaming Core Refactoring.
- **Test Strategy**: Verify `yield` output from AI functions.
- [ ] [RED] Refactor `fortune.views.generate_ai_response` for `yield`.
- [ ] [GREEN] Implement streaming logic for Gemini/DeepSeek.
- [ ] [REFACTOR] Cleanup error handling in generators.

... (Continues through all 6 phases)

## Quality Gate (CLI Checklist)
- [ ] `pytest fortune/tests/` passes
- [ ] `pytest autoarticle/tests/` passes
- [ ] `curl -N http://localhost:8000/...` verifies chunked delivery
- [ ] `curl -I` confirms correct headers

## Rollback Plan
- Revert `DJANGO_SETTINGS_MODULE` to safe values.
- Git checkout previous stable branch.
