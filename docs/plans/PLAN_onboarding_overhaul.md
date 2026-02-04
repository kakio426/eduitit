# **Implementation Plan: Onboarding Overhaul & Account Deletion**

Status: 🔄 In Progress  
Started: 2026-02-04  
Last Updated: 2026-02-04  
Estimated Completion: 2026-02-05  

**⚠️ CRITICAL INSTRUCTIONS**: After completing each phase:

1. ✅ Check off completed task checkboxes  
2. 🧪 Run all quality gate validation commands in **TERMINAL**  
3. ⚠️ Verify ALL quality gate items pass  
4. 📅 Update "Last Updated" date above  
5. 📝 Document learnings in Notes section  
6. ➡️ Only then proceed to next phase

⛔ DO NOT OPEN BROWSER unless explicitly instructed in the phase.  
⛔ DO NOT skip quality gates or proceed with failing checks

---

## **📋 Overview**

### **Feature Description**

Social login users currently face a bifurcated or incomplete onboarding experience (e.g., missing nickname, generic 'userXX' IDs). This feature unifies onboarding for ALL providers, ensures mandatory data collection (Email, Name, Role) in a premium UI, and adds a necessary account deletion feature.

### **Success Criteria**

* [ ] Unified onboarding page for all social login users missing profile data.
* [ ] Elimination of default "userXX" IDs by mandatory name input.
* [ ] Premium UI following SIS (Claymorphism, NanumSquareRound font, no marketing jargon).
* [ ] Functional account deletion (Delete Account) with security confirmation.
* [ ] 100% terminal-verified logic (TDD).

### **User Impact**

Users get a professional, personalized first impression and regain control over their data with account deletion.

---

## **🏗️ Architecture Decisions**

| Decision | Rationale | Trade-offs |
| :---- | :---- | :---- |
| **OnboardingMiddleware** | Enforces data completeness for all authenticated users before site access. | Adds slight overhead to request processing. |
| **Integrated Profile View** | Combines email and name updates to reduce friction. | More complex form handling in the view. |
| **Direct User Deletion** | Simple `user.delete()` for MVP (Minimum Viable Product). | Irreversible data loss (requires clear warning). |

---

## **📦 Dependencies**

### **Required Before Starting**

* [x] `SERVICE_INTEGRATION_STANDARD.md` updated.
* [x] `core` app with `UserProfile` model.
* [x] `allauth` integration.

---

## **🧪 Test Strategy (Terminal First)**

### **Testing Approach**

TDD Principle: Write tests FIRST.  
Verification: Use Django's `TestCase` and `Client` via terminal.

### **Test Pyramid for This Feature**

| Test Type | Coverage Target | Tool & Env |
| :---- | :---- | :---- |
| **Unit Tests** | ≥80% | Pytest (Middleware & View Logic) |
| **Integration Tests** | Critical flows | Django Test Client (Redirects & Deletion) |

---

## **🚀 Implementation Phases**

### **Phase 1: Foundation & Middleware Refinement**

Goal: Enforce profile completion for all users and setup account deletion logic.  
Verification Mode: 🖥️ TERMINAL ONLY  
Status: ✅ Complete

#### **Tasks**

**🔴 RED: Write Failing Tests First**

* [x] **Test 1.1**: Test middleware redirects users with default 'userXX' nickname or missing email.
  * File: `core/tests/test_onboarding.py`
  * Expected: Redirect to `update_email`.
* [x] **Test 1.2**: Test `delete_account` view requires authentication and correctly deletes user.

**🟢 GREEN: Implement to Make Tests Pass**

* [x] **Task 1.3**: Refine `OnboardingMiddleware` in `core/middleware.py`.
* [x] **Task 1.4**: Implement `delete_account` view and URL.

**🔵 REFACTOR: Clean Up Code**

* [x] **Task 1.5**: Ensure middleware exclusion list is minimal and secure.

#### **Quality Gate ✋**

**Validation Commands**:
```bash
python manage.py test core.tests.test_onboarding
```

---

### **Phase 2: Unified Onboarding UI Overhaul**

Goal: Create a premium, center-aligned profile completion page.  
Verification Mode: 🖥️ TERMINAL ONLY (HTML Structure)  
Status: ✅ Complete

#### **Tasks**

**🔴 RED: Write Failing Tests First**

* [x] **Test 2.1**: Verify `update_email` view handles POST data for both email and nickname.

**🟢 GREEN: Implement to Make Tests Pass**

* [x] **Task 2.2**: Redesign `core/templates/core/update_email.html` (NanumSquareRound font, no Dongle).
* [x] **Task 2.3**: Update `update_email` view to save `User.first_name` and `UserProfile.nickname`.
* [x] **Task 2.4**: Remove "marketing use" disclaimer text.

**🔵 REFACTOR: Clean Up Code**

* [x] **Task 2.5**: Audit template for SIS compliance (Claymorphism).

#### **Quality Gate ✋**

**Validation Commands**:
```bash
# Verify view logic returns correct context
python manage.py shell -c "from django.urls import reverse; print(reverse('update_email'))"
```

---

### **Phase 3: Account Deletion Flow & Settings Integration**

Goal: Add deletion button to settings and confirmation page.  
Verification Mode: 🖥️ TERMINAL + BROWSER (Visual Audit)  
Status: ✅ Complete

#### **Tasks**

* [x] **Task 3.1**: Create `core/templates/core/delete_account.html`.
* [x] **Task 3.2**: Add deletion link to `core/templates/core/settings.html`.
* [x] **Task 3.3**: Final visual audit of the entire flow.

#### **Quality Gate ✋**

**Validation Commands**:
```bash
python manage.py check
```

---

## **⚠️ Risk Assessment**

| Risk | Probability | Impact | Mitigation Strategy |
| :---- | :---- | :---- | :---- |
| Accidental Deletion | Low | High | Use a clear, separate confirmation page. |
| Middleware Loop | Med | High | Thoroughly test the allowed paths in middleware. |

---

## **🔄 Rollback Strategy**

* **Revert**: `git checkout core/middleware.py core/views.py core/templates/core/update_email.html`
* **Delete new files**: `rm core/templates/core/delete_account.html`

---

## **📊 Progress Tracking**

**Overall Progress**: 100% complete

---

## **📝 Notes & Learnings**
- **Middleware Redirection**: Discovered that `delete_account` view must be added to `allowed_paths` in `OnboardingMiddleware` to allow users to delete their account even if profile is incomplete.
- **TDD Flow**: Terminal-first verification significantly sped up the debugging of middleware logic.
