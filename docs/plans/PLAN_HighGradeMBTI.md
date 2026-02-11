# **Implementation Plan: High Grade Student MBTI**

Status: 🔄 In Progress  
Started: 2026-02-11  
Last Updated: 2026-02-11  
Estimated Completion: 2026-02-11  

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
Add a "High Grade" (고학년용) version of the Student MBTI test with 28 questions (7 per dimension) to improve accuracy and avoid tie-breaking issues found in even-numbered question sets. The existing "Low Grade" (저학년용) version with 12 questions will be preserved.

### **Success Criteria**
* [ ] Teachers can select "Low Grade" or "High Grade" when creating a session.
* [ ] "Low Grade" (12 Qs) works exactly as before.
* [ ] "High Grade" (28 Qs) displays 28 questions and calculates MBTI correctly.
* [ ] 28 questions are distributed as 7 per dimension (E/I, S/N, T/F, J/P).
* [ ] MBTI calculation logic handles the 7 items per dimension (cutoff of 4) to ensure perfectly balanced results (50/50 probability).
* [ ] Vocabulary is suitable for elementary school students (no difficult words).

### **User Impact**
* **Teachers**: Can use the tool for a wider range of students with better accuracy.
* **Students**: Get more accurate results based on a more comprehensive questionnaire.

## **🏗️ Architecture Decisions**

| Decision | Rationale | Trade-offs |
| :---- | :---- | :---- |
| **28 Questions (7 per dim)** | An odd number of questions per dimension (7) ensures a clear majority (0-3 vs 4-7) and avoids ties (like 3 vs 3 in a 6-item set). This guarantees a 50/50 probability distribution for each type. | Slightly longer test than 24 questions (user request), but mathematically superior. |
| **`TestSession.test_type`** | Store the version in the session model to persistent selection. | Requires migration. |
| **Separate Question Lists** | Keep `STUDENT_QUESTIONS` (renamed to `_LOW`) and `STUDENT_QUESTIONS_HIGH` separate for clarity. | Slight code duplication in structure, but cleaner than a single complex list. |

## **📦 Dependencies**

### **Required Before Starting**
* [x] Existing `studentmbti` app functional.

## **🧪 Test Strategy (Terminal First)**

### **Testing Approach**
TDD Principle: Write tests FIRST, then implement to make them pass.
Speed Protocol: All tests must run in the TERMINAL without launching a visible browser.

### **Test Pyramid for This Feature**
| Test Type | Coverage Target | Tool & Env |
| :---- | :---- | :---- |
| **Unit Tests** | ≥80% | Pytest (Terminal) |
| **Integration Tests** | Critical paths | TestClient (Terminal) |

## **🚀 Implementation Phases**

### **Phase 1: Data & Models**

Goal: Define 28 questions and add `test_type` field.  
Verification Mode: 🖥️ TERMINAL ONLY (No Browser)  
Status: ⏳ Pending

#### **Tasks**

**🔴 RED: Write Failing Tests First**

* [ ] **Test 1.1**: Test `TestSession` model has `test_type` field.
  * File: `studentmbti/tests.py`
  * Expected: Fail (field doesn't exist)
* [ ] **Test 1.2**: Test data constants exist (`STUDENT_QUESTIONS_LOW`, `STUDENT_QUESTIONS_HIGH`).
  * File: `studentmbti/tests.py`
  * Expected: Fail (constants don't exist)

**🟢 GREEN: Implement to Make Tests Pass**

* [ ] **Task 1.3**: Add `test_type` field to `TestSession` (choices: 'low', 'high', default 'low').
  * File: `studentmbti/models.py`
  * Run `makemigrations` and `migrate`.
* [ ] **Task 1.4**: Refactor `student_mbti_data.py`.
  * Rename `STUDENT_QUESTIONS` to `STUDENT_QUESTIONS_LOW`.
  * Add `STUDENT_QUESTIONS_HIGH` with 28 questions (7 per dimension).
  * Add `GET_QUESTION_SET(type)` helper if needed.

**🔵 REFACTOR: Clean Up Code**

* [ ] **Task 1.5**: Update existing views to use `STUDENT_QUESTIONS_LOW` (temporary fix to keep code running).

#### **Quality Gate ✋**

**Validation Commands**:
```bash
python manage.py test studentmbti
```

**Checklist**:
* [ ] **TDD**: Tests written first and passed
* [ ] **Build**: Migrations applied successfully
* [ ] **No Browser**: Verified without opening Chrome

### **Phase 2: Logic & Views**

Goal: Implement session creation with type selection and dynamic analysis logic.  
Verification Mode: 🖥️ TERMINAL ONLY (No Browser)  
Status: ⏳ Pending

#### **Tasks**

**🔴 RED: Write Failing Tests First**

* [ ] **Test 2.1**: Test `session_create` view accepts `test_type`.
* [ ] **Test 2.2**: Test `session_test` view serves correct questions based on session type.
* [ ] **Test 2.3**: Test `analyze` view correctly calculates MBTI for 'high' type (7 per dim).
  * Mock answers: 4 'E' choices -> Result 'E'.
  * Mock answers: 3 'E' choices -> Result 'I'.

**🟢 GREEN: Implement to Make Tests Pass**

* [ ] **Task 2.4**: Update `session_create` view to save `test_type`.
* [ ] **Task 2.5**: Update `session_test`/`session_detail` to use correct question list.
* [ ] **Task 2.6**: Update `analyze` view logic.
  * If `test_type == 'low'`: Use existing logic (3 items, cut-off 2).
  * If `test_type == 'high'`: Use new logic (7 items, cut-off 4).

#### **Quality Gate ✋**

**Validation Commands**:
```bash
python manage.py test studentmbti
```

**Checklist**:
* [ ] **TDD**: Tests written first and passed
* [ ] **Logic**: Calculation verified for both Low (3 items) and High (7 items) versions
* [ ] **No Browser**: Verified without opening Chrome

### **Phase 3: UI Updates**

Goal: Add UI for selecting test type and displaying more questions.  
Verification Mode: 🧪 TERMINAL / Manual  
Status: ⏳ Pending

#### **Tasks**

* [ ] **Task 3.1**: Update `studentmbti/dashboard.html` (Create Session Modal) to include Radio Buttons for Low/High grade.
    * Add field `test_type` to the form.
    * Options:
        * `low`: "저학년 (1~3학년) - 12문항" (Default)
        * `high`: "고학년 (4~6학년) - 28문항"
    * Visuals: Use standard Tailwind radio styling, ensuring it aligns with the existing design.
* [ ] **Task 3.2**: Update `studentmbti/test.html` to handle variable number of questions dynamically.
    * Change hardcoded `const totalSteps = 12;` to `const totalSteps = {{ questions|length }};`.
    * Ensure the progress bar and step counter (`1 / 28`) calculate correctly based on this dynamic value.

#### **Quality Gate ✋**

**Validation Commands**:
```bash
# Manual check of the form
```

**Checklist**:
* [ ] **Rendering**: Form shows options
* [ ] **Interaction**: Can select High Grade and start session

## **⚠️ Risk Assessment**

| Risk | Probability | Impact | Mitigation Strategy |
| :---- | :---- | :---- | :---- |
| **Existing Sessions Break** | Low | High | Default `test_type='low'` in migration preserves existing behavior. |
| **Logic Error in Calculation** | Medium | High | Comprehensive unit tests for boundary conditions (3 vs 4 counts). |

## **📝 Notes & Learnings**
* Using 28 questions (7 per dimension) is mathematically cleaner than 24 (6 per dimension) because it avoids tie-breaking scenarios, ensuring a perfect 50/50 splits probability.

## **📚 References**
* `student_mbti_data.py`: Existing data file.
