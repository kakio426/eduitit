# **Implementation Plan - Teacher Saju Feature**

Status: 🔄 In Progress  
Started: 2026-01-22  
Last Updated: 2026-01-22  
Estimated Completion: 2026-01-22  

**⚠️ CRITICAL INSTRUCTIONS**: After completing each phase:

1. ✅ Check off completed task checkboxes  
2. 🧪 Run all quality gate validation commands in **TERMINAL**  
3. ⚠️ Verify ALL quality gate items pass  
4. 📅 Update "Last Updated" date above  
5. 📝 Document learnings in Notes section  
6. ➡️ Only then proceed to next phase

⛔ DO NOT OPEN BROWSER unless explicitly instructed in the phase.  
⛔ DO NOT skip quality gates or proceed with failing checks

## **📋 Overview**

### **Feature Description**
A "Teacher Saju" (Fortune Telling) service that provides customized fortune analysis for teachers using Google Gemini. It includes two modes:
1.  **Teacher Version**: Focuses on school life, student chemistry, and admin work.
2.  **General Version**: Standard fortune telling (Wealth, Love, Health).
The UI will feature a "Mongle Mongle" (Soft/Fluffy) aesthetic integrated with Eduitit's existing Claymorphism design.

### **Success Criteria**
* [ ] Users can toggle between "Teacher" and "General" modes.
* [ ] Input form accepts birth info and submits correctly.
* [ ] Gemini API generates relevant, detailed markdown responses based on the selected mode.
* [ ] UI matches the requested "Soft/Warm" design while maintaining site consistency.
* [ ] Clean error handling for API failures.

### **User Impact**
Provides fun, relatable content for teachers, increasing engagement and time spent on the platform.

## **🏗️ Architecture Decisions**

| Decision | Rationale | Trade-offs |
| :---- | :---- | :---- |
| **New App `fortune`** | Keeps logic isolated from `core` or generic `products`. | Slight overhead of a new app. |
| **Google Generative AI SDK** | Direct access to Gemini models. | Dependency on Google API. |
| **Dual System Prompts** | Separation of concerns for different user personas. | Maintenance of two prompts. |
| **Tailwind + Custom CSS** | Leverages existing Tailwind setup but adds specific "Mongle" flair. | Need to ensure CSS reuse where possible. |

## **📦 Dependencies**

### **Required Before Starting**
* [ ] `google-generativeai` package installed.
* [ ] `markdown` package installed.
* [ ] Gemini API Key (User provided or in env).

## **🧪 Test Strategy (Terminal First)**

### **Testing Approach**
TDD Principle: Write tests FIRST.
Speed Protocol: All tests run in TERMINAL.

### **Test Pyramid**
| Test Type | Coverage Target | Tool & Env |
| :---- | :---- | :---- |
| **Unit Tests** | Forms, Prompts | Pytest/Unittest (Terminal) |
| **Integration Tests** | Views, Mock API | Pytest/Unittest (Terminal) |
| **E2E Tests** | UI Flow | Manual/Browser (Phase 3) |

## **🚀 Implementation Phases**

### **Phase 1: Foundation (App & Logic)**
Goal: Working Form and Prompt Logic (No UI/API yet)
Verification Mode: 🖥️ TERMINAL ONLY
Status: ⏳ Pending

#### **Tasks**
**🔴 RED: Write Failing Tests First**
* [ ] **Test 1.1**: Test `TeacherSajuForm` validation (valid/invalid data).
* [ ] **Test 1.2**: Test `PromptGenerator` logic (returns correct prompt based on mode).

**🟢 GREEN: Implement to Make Tests Pass**
* [ ] **Task 1.3**: Create `fortune` app (`manage.py startapp fortune`).
* [ ] **Task 1.4**: Register app in `config/settings.py`.
* [ ] **Task 1.5**: Implement `forms.py` with `mode` field.
* [ ] **Task 1.6**: Implement `prompts.py` with `get_prompt(mode, data)` function.

**🔵 REFACTOR: Clean Up Code**
* [ ] **Task 1.7**: Ensure prompts are modular and easy to edit.

#### **Quality Gate ✋**
**Validation Commands**:
`python manage.py test fortune.tests`
**Checklist**:
* [ ] TDD followed.
* [ ] Tests pass in terminal.
* [ ] No Browser used.

### **Phase 2: View & API Integration**
Goal: Working View that calls Gemini (Mocked in tests)
Verification Mode: 🖥️ TERMINAL ONLY
Status: ⏳ Pending

#### **Tasks**
**🔴 RED: Write Failing Tests First**
* [ ] **Test 2.1**: Test `saju_view` POST request (Mocked API).
    *   Verify context contains `result_html`.
    *   Verify correct prompt sent to mock.
* [ ] **Test 2.2**: Test error handling (API failure).

**🟢 GREEN: Implement to Make Tests Pass**
* [ ] **Task 2.3**: Install `google-generativeai` and `markdown`.
* [ ] **Task 2.4**: Implement `views.py` with Gemini integration.
* [ ] **Task 2.5**: Update `urls.py`.

#### **Quality Gate ✋**
**Validation Commands**:
`python manage.py test fortune.tests`
**Checklist**:
* [ ] Logic verified with mocks.
* [ ] API Key configuration checked.

### **Phase 3: UI Integration & Polish**
Goal: Beautiful "Mongle" UI in Browser
Verification Mode: 🧪 JSDOM / BROWSER
Status: ⏳ Pending

#### **Tasks**
* [ ] **Task 3.1**: Create `templates/fortune/saju_form.html`.
    *   Extend `core/base.html`.
    *   Implement "Mongle" styles using Tailwind + Custom CSS.
* [ ] **Task 3.2**: Implement Loading State (JS).
* [ ] **Task 3.3**: Verify responsive design.

#### **Quality Gate ✋**
**Validation**:
*   Manual check of `/fortune/` (or configured URL).
*   Verify "Teacher" vs "General" toggle works visually.
