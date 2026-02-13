# **Implementation Plan: Saju Chatbot Service**

Status: ✅ Complete
Started: 2026-02-13
Last Updated: 2026-02-13
Estimated Completion: 2026-02-14

**⚠️ CRITICAL INSTRUCTIONS**: After completing each phase:
1. ✅ Check off completed task checkboxes
2. 🧪 Run all quality gate validation commands in **TERMINAL**
3. ⚠️ Verify ALL quality gate items pass
4. 📅 Update "Last Updated" date above
5. 📝 Document learnings in Notes section
6. ➡️ Only then proceed to next phase

⛔ DO NOT OPEN BROWSER unless explicitly instructed in Phase 3.
⛔ DO NOT skip quality gates or proceed with failing checks

## **📋 Overview**

### **Feature Description**
A conversational AI service ("Saju Teacher") where users can chat about their Saju analysis. It leverages existing `UserSajuProfile` and `NatalChart` data to provide personalized, context-aware answers using DeepSeek-V3. The system enforces single active sessions and a 7-day data retention policy.

### **Success Criteria**
* [ ] Users can start a chat session based on their Saju profile.
* [ ] **Single Session**: Starting a new chat automatically closes any previous active session.
* [ ] **Retention**: Chat logs are automatically deleted 7 days after creation (via management command).
* [ ] **Manual Save**: Users can save specific chat interactions to `FortuneResult` (Markdown format).
* [ ] **Standards**: UI follows Claymorphism, Logging follows SIS standards, HTMX uses secure CSRF patterns.

### **User Impact**
Users receive immediate, personalized follow-up answers to their Saju analysis in an ephemeral, cost-effective chat interface, with the ability to permanently save key insights.

## **🏗️ Architecture Decisions**

| Decision | Rationale | Trade-offs |
| :---- | :---- | :---- |
| **App Location** | Keep in `fortune` app | Domain logic (`UserSajuProfile`) is tightly coupled. Avoids circular imports. | `fortune/models.py` grows slightly larger. |
| **AI Model** | DeepSeek-V3 (via OpenAI SDK) | Best performance/cost ratio for Korean language. | External dependency on DeepSeek API. |
| **UI Stack** | HTMX + Alpine.js | Consistent with Eduitit tech stack (No React). SIS Compliant. | Requires manual scroll handling with Alpine. |
| **Session Mgmt** | Database-backed (`ChatSession`) | Allows persistence across refreshes and manual history saving. | Requires periodic cleanup (7-day rule). |
| **Streaming** | `StreamingHttpResponse` | Improved UX for long AI responses. | Complexity in HTMX integration. |

## **📦 Dependencies**

### **Required Before Starting**
* [x] `fortune` app exists and is stable.
* [x] DeepSeek API Key is available in environment variables.
* [x] `UserSajuProfile` model exists.
* [x] `FortuneResult` model exists (for saving history).

### **External Dependencies**
* `openai`: Already installed (used for DeepSeek).

## **🧪 Test Strategy (Terminal First)**

### **Testing Approach**
TDD Principle: Write tests FIRST, then implement to make them pass.
Speed Protocol: All tests must run in the TERMINAL without launching a visible browser.

### **Test Pyramid for This Feature**

| Test Type | Coverage Target | Tool & Env |
| :---- | :---- | :---- |
| **Unit Tests** | ≥80% | Pytest (Terminal) |
| **Integration Tests** | Critical paths | TestClient (Terminal) |
| **E2E Tests** | Key user flows | Manual / Playwright (Later) |

## **🚀 Implementation Phases**

### **Phase 1: Backend Foundation (Models & Context)**

Goal: Database models and Context Generation Logic
Verification Mode: 🖥️ TERMINAL ONLY (No Browser)
Status: ✅ Complete

#### **Tasks**

**🔴 RED: Write Failing Tests First**
* [x] **Test 1.1**: Write unit tests for `ChatSession` and `ChatMessage` models.
  * File: `fortune/tests/test_chat_models.py`
  * Expected: Fail (Models do not exist).
  * Details: Verify `expires_at` default (7 days), `is_active` toggle.
* [x] **Test 1.2**: Write unit tests for `build_system_prompt`.
  * File: `fortune/tests/test_chat_logic.py`
  * Expected: Fail (Function does not exist).
  * Details: Verify prompt includes Saju context (Day Master) and **Simple Vocabulary**.

**🟢 GREEN: Implement to Make Tests Pass**
* [x] **Task 1.3**: Implement Models in `fortune/models.py`.
  * `ChatSession`: User, Profile, CreatedAt, ExpiresAt, IsActive, MaxTurns.
  * `ChatMessage`: Session, Role, Content, CreatedAt.
* [x] **Task 1.4**: Implement `build_system_prompt` in `fortune/utils/chat_logic.py`.
  * Use `UserSajuProfile` to generate concise context strings.
* [x] **Task 1.5**: Create Migrations.
  * `python manage.py makemigrations fortune`
  * `python manage.py migrate fortune`

**🔵 REFACTOR: Clean Up Code**
* [x] **Task 1.6**: Refactor `fortune/admin.py` to include new models.
  * **Rule**: Use `select_related` to avoid N+1 queries (SIS Rule).

#### **Quality Gate ✋**
**⚠️ STOP: TERMINAL VERIFICATION ONLY**

**Validation Commands**:
```bash
python manage.py test fortune.tests.test_chat_models
python manage.py test fortune.tests.test_chat_logic
python manage.py check
```

**Checklist**:
* [x] **TDD**: Tests written first and passed.
* [x] **Build**: Project checks pass.
* [x] **No Browser**: Verified without opening Chrome.

### **Phase 2: Core Chat Logic (HTMX & DeepSeek)**

Goal: Working API for sending messages and receiving AI responses.
Verification Mode: 🖥️ TERMINAL ONLY (No Browser)
Status: ✅ Complete

#### **Tasks**

**🔴 RED: Write Failing Tests First**
* [x] **Test 2.1**: Write integration test for `chat_view` (POST).
  * File: `fortune/tests/test_chat_views.py`
  * Verify:
    * Single Active Session enforcement (Old session `is_active=False`).
    * Message saving (User & Assistant).
    * **Standard Logging**: Check for `[Fortune] Action: ...` logs.
* [x] **Test 2.2**: Write test for `cleanup_old_sessions` command.

**🟢 GREEN: Implement to Make Tests Pass**
* [x] **Task 2.3**: Implement `fortune/views_chat.py`.
  * `create_session`: Deactivate old sessions, create new one.
  * `send_message`: Handle user input, call AI, save history.
  * **Rule**: Ensure `get_chart_context` null check and Safe JSON parsing (CLAUDE.md).
* [x] **Task 2.4**: Implement DeepSeek integration in `fortune/utils/chat_ai.py`.
* [x] **Task 2.5**: Implement "Save to History" View.
  * Saves chat content to `FortuneResult` model in **Markdown** format.
* [x] **Task 2.6**: Implement `cleanup_old_sessions` management command.
  * Deletes sessions older than 7 days.

**🔵 REFACTOR: Clean Up Code**
* [x] **Task 2.7**: Ensure error handling (API failures).

#### **Quality Gate ✋**
**⚠️ STOP: TERMINAL VERIFICATION ONLY**

**Validation Commands**:
```bash
python manage.py test fortune.tests.test_chat_views
```

**Checklist**:
* [x] **TDD**: Tests written first and passed.
* [x] **Logic**: Core message flow works in terminal.
* [x] **No Browser**: Verified without opening Chrome.

### **Phase 3: UI/UX Refinement**

Goal: User-facing Chat Interface (SNS Style, Claymorphism).
Verification Mode: 🧪 JSDOM / MANUAL (Browser Allowed)
Status: ✅ Complete

#### **Tasks**

**🔴 RED: Write Failing Tests First**
* [x] **Test 3.1**: Manual UI Check Plan (Browser).
  * Verify Claymorphism shadows and colors.
  * Verify "Expires in 7 days" warning.

**🟢 GREEN: Implement to Make Tests Pass**
* [x] **Task 3.2**: Create `fortune/templates/fortune/chat_main.html`.
  * **Rule**: Claymorphism (`clay-card`, `#E0E5EC`, `bg-purple-500`).
  * **Rule**: Secure HTMX (`hx-headers` for CSRF).
  * **Rule**: Loading Spinner (`htmx-indicator`).
* [x] **Task 3.3**: Create `fortune/templates/fortune/partials/chat_message.html`.
* [x] **Task 3.4**: Add "End Session" / "New Session" buttons.
* [x] **Task 3.5**: Add "Save Chat" button functionality (with `hx-vals` or form for CSRF).
* [x] **Task 3.6**: Update `fortune/templates/fortune/detail.html`.
  * **Rule**: Use `escapejs` for Markdown rendering to prevent `const` crash.

**🔵 REFACTOR: Clean Up Code**
* [x] **Task 3.7**: Verify Mobile Responsiveness (Viewport settings).

#### **Quality Gate ✋**
**⚠️ STOP: Validate Component Rendering**

**Checklist**:
* [x] **Rendering**: Chat bubbles render correctly.
* [x] **Interaction**: Auto-scroll works (Alpine.js / JS).
* [x] **Manual Check**: Visual styling meets Claymorphism standards.

## **⚠️ Risk Assessment**

| Risk | Probability | Impact | Mitigation Strategy |
| :---- | :---- | :---- | :---- |
| **DeepSeek API Latency** | Med | High | Use streaming responses or "typing..." indicators. |
| **Data Growth** | Low | Low | 7-day auto-expiry keeps DB size manageable. |
| **Concurrency** | Low | Med | Enforce single active session; UI shows "Session Expired" if preempted. |
| **CSRF & HTMX** | Med | Med | Use `hx-headers` global config + explicit `hx-vals` for critical buttons. |

## **🔄 Rollback Strategy**

### **If Phase 1 Fails**
* Remove `ChatSession`, `ChatMessage` models.
* Revert `fortune/models.py` and delete migration files.

## **📝 Notes & Learnings**

### **Implementation Notes**
* **Context**: `UserSajuProfile` is rich; `build_system_prompt` must compress this effectively for DeepSeek.
* **Standards**: SIS and CLAUDE.md are strictly followed.
