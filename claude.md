# **Feature Planner (Terminal-First Edition)**

## **Purpose**

Generate structured, phase-based plans where:

* Each phase delivers complete, runnable functionality  
* **Terminal-First Verification**: Use CLI tools (pytest, curl, npm test) instead of browser automation  
* Quality gates enforce validation via command line  
* Progress tracked via markdown checkboxes  
* Each phase is 1-4 hours maximum

## **Planning Workflow**

### **Step 1: Requirements Analysis**

1. Read relevant files to understand codebase architecture  
2. Identify dependencies and integration points  
3. Assess complexity and risks  
4. Determine appropriate scope (small/medium/large)

### **Step 2: Phase Breakdown with TDD Integration**

Break feature into 3-7 phases where each phase:

* **Test-First**: Write tests BEFORE implementation  
* **Headless Validation**: Verify logic without opening a GUI (Speed Priority)  
* Delivers working, testable functionality  
* Takes 1-4 hours maximum  
* Follows Red-Green-Refactor cycle  
* Has measurable test coverage requirements  
* Can be rolled back independently

**Phase Structure**:

* Phase Name: Clear deliverable  
* Goal: What working functionality this produces  
* **Test Strategy**: Unit/Integration tests (Terminal based)  
* Tasks (ordered by TDD workflow):  
  1. **RED Tasks**: Write failing unit tests first  
  2. **GREEN Tasks**: Implement minimal code to make tests pass  
  3. **REFACTOR Tasks**: Improve code quality while tests stay green  
* Quality Gate: CLI command verification  
* Dependencies: What must exist before starting  
* **Coverage Target**: Specific percentage or checklist for this phase

### **Step 3: Plan Document Creation**

Use https://www.google.com/search?q=plan-template.md to generate: docs/plans/PLAN\_\<feature-name\>.md

Include:

* Overview and objectives  
* Architecture decisions with rationale  
* Complete phase breakdown with checkboxes  
* Quality gate checklists (CLI focused)  
* Risk assessment table  
* Rollback strategy per phase  
* Progress tracking section  
* Notes & learnings area

### **Step 4: User Approval**

**CRITICAL**: Use AskUserQuestion to get explicit approval before proceeding.

Ask:

* "Does this phase breakdown make sense for your project?"  
* "Any concerns about the proposed approach?"  
* "Should I proceed with creating the plan document?"

Only create plan document after user confirms approval.

### **Step 5: Document Generation**

1. Create docs/plans/ directory if not exists  
2. Generate plan document with all checkboxes unchecked  
3. Add clear instructions in header about quality gates  
4. Inform user of plan location and next steps

## **⚡ Verification Protocol (CRITICAL)**

To ensure speed and stability, adhere to these verification rules:

**Phase 1-3 (Logic & Backend)**:

* ⛔ **NO BROWSER**: Do not open Chrome/Puppeteer.  
* ✅ **USE**: pytest, npm test, curl, httpie.  
* **Reason**: Logic verification in the terminal is 100x faster.

**Phase 4 (Frontend Logic)**:

* ⛔ **NO BROWSER**: Do not open Chrome.  
* ✅ **USE**: jest/vitest with jsdom. Verify masking, hooks, and utils via unit tests.

**Phase 5 (Final UI Integration)**:

* ⚠️ **BROWSER ALLOWED**: Only open the browser if explicitly necessary for visual check.  
* ✅ **USE**: Playwright (Headless) or manual verification instructions.

## **Quality Gate Standards (Speed Optimized)**

Each phase MUST validate these items before proceeding to next phase.  
⛔ RULE: Do NOT open a browser unless the phase explicitly requires visual UI inspection.  
**Build & Compilation**:

* \[ \] Project builds/compiles without errors (run via terminal)  
* \[ \] No syntax errors

**Test-Driven Development (TDD)**:

* \[ \] Tests written BEFORE production code  
* \[ \] Red-Green-Refactor cycle followed  
* \[ \] **Fast Verification**: Unit tests run in \< 1s  
* \[ \] Unit tests: ≥80% coverage for business logic

**Testing (Terminal Only)**:

* \[ \] All existing tests pass (npm test, pytest)  
* \[ \] New tests added for new functionality  
* \[ \] Test coverage maintained or improved

**Code Quality**:

* \[ \] Linting passes with no errors (npm run lint)  
* \[ \] Type checking passes (tsc, mypy)  
* \[ \] Code formatting consistent

**Functionality**:

* \[ \] **Logic Verified**: Inputs/Outputs verified via unit tests  
* \[ \] **API Verified**: Endpoints checked via curl or httpie  
* \[ \] No regressions in existing functionality

**Security & Performance**:

* \[ \] No new security vulnerabilities  
* \[ \] No performance degradation  
* \[ \] Resource usage acceptable

## **Phase Sizing Guidelines**

**Small Scope** (2-3 phases, 3-6 hours total):

* Single component or simple feature  
* Minimal dependencies  
* Example: Add utility function, create API endpoint

**Medium Scope** (4-5 phases, 8-15 hours total):

* Multiple components or moderate feature  
* Some integration complexity  
* Example: User authentication logic, data processing pipeline

**Large Scope** (6-7 phases, 15-25 hours total):

* Complex feature spanning multiple areas  
* Significant architectural impact  
* Example: AI-powered search, Real-time dashboard

## **Risk Assessment**

Identify and document:

* **Technical Risks**: API changes, performance issues  
* **Dependency Risks**: External library updates  
* **Timeline Risks**: Complexity unknowns  
* **Quality Risks**: Test coverage gaps

For each risk, specify: Probability, Impact, and Mitigation Strategy.

## **Test Specification Guidelines**

### **Test-First Development Workflow (Headless)**

**For Each Feature Component**:

1. **Specify Test Cases** (before writing ANY code)  
   * Define Input \-\> Expected Output  
   * Define Edge Cases  
2. **Write Tests** (Red Phase)  
   * Write tests that run in **TERMINAL**  
   * Verify tests fail for the right reason  
3. **Implement Code** (Green Phase)  
   * Write minimal code to make tests pass  
   * Run tests frequently (every 2-5 minutes)  
4. **Refactor** (Blue Phase)  
   * Improve code quality while tests remain green

### **Test Types & Speed**

**Unit Tests (Priority 1\)**:

* **Target**: Individual functions, logic  
* **Environment**: Terminal (Node/Python)  
* **Speed**: Ultra-fast (\<100ms)

**Integration Tests (Priority 2\)**:

* **Target**: API endpoints, DB queries  
* **Environment**: Terminal (Test DB, Mock Server)  
* **Speed**: Moderate (\<1s)

**E2E Tests (Priority 3 \- Use Sparingly)**:

* **Target**: Full user flows  
* **Environment**: Headless Browser (Playwright/Puppeteer)  
* **Speed**: Slow \-\> **Only use in final phase**

## **Supporting Files Reference**

* [plan-template.md](https://www.google.com/search?q=plan-template.md) \- Complete plan document template


# **Implementation Plan**

Status: 🔄 In Progress  
Started: YYYY-MM-DD  
Last Updated: YYYY-MM-DD  
Estimated Completion: YYYY-MM-DD  
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

\[What this feature does and why it's needed\]

### **Success Criteria**

* \[ \] Criterion 1  
* \[ \] Criterion 2  
* \[ \] Criterion 3

### **User Impact**

\[How this benefits users or improves the product\]

## **🏗️ Architecture Decisions**

| Decision | Rationale | Trade-offs |
| :---- | :---- | :---- |
| \[Decision 1\] | \[Why this approach\] | \[What we're giving up\] |
| \[Decision 2\] | \[Why this approach\] | \[What we're giving up\] |

## **📦 Dependencies**

### **Required Before Starting**

* \[ \] Dependency 1: \[Description\]  
* \[ \] Dependency 2: \[Description\]

### **External Dependencies**

* Package/Library 1: version X.Y.Z  
* Package/Library 2: version X.Y.Z

## **🧪 Test Strategy (Terminal First)**

### **Testing Approach**

TDD Principle: Write tests FIRST, then implement to make them pass.  
Speed Protocol: All tests must run in the TERMINAL without launching a visible browser.

### **Test Pyramid for This Feature**

| Test Type | Coverage Target | Tool & Env |
| :---- | :---- | :---- |
| **Unit Tests** | ≥80% | Jest/Pytest (Terminal) |
| **Integration Tests** | Critical paths | Curl/Httpie/TestClient (Terminal) |
| **E2E Tests** | Key user flows | Playwright (Headless Mode Only) |

### **Test File Organization**

test/  
├── unit/       \# Logic tests (No UI)  
├── integration/\# API/DB tests (No UI)  
└── e2e/        \# Full flow tests (Headless)

### **Test Naming Convention**

// Example structure:  
describe/group: Feature or component name  
  test/it: Specific behavior being tested  
    // Arrange → Act → Assert pattern (Terminal)

## **🚀 Implementation Phases**

### **Phase 1: \[Foundation Phase Name\]**

Goal: \[Specific working functionality this phase delivers\]  
Verification Mode: 🖥️ TERMINAL ONLY (No Browser)  
Status: ⏳ Pending | 🔄 In Progress | ✅ Complete

#### **Tasks**

**🔴 RED: Write Failing Tests First**

* \[ \] **Test 1.1**: Write unit tests for \[specific functionality\]  
  * File(s): test/unit/\[feature\]/\[component\]\_test.\*  
  * Expected: Tests FAIL (red) because feature doesn't exist yet  
  * **Restriction**: Must run in terminal.  
  * Details: Test cases covering:  
    * Happy path scenarios  
    * Edge cases  
* \[ \] **Test 1.2**: Write integration tests for \[component interaction\]  
  * File(s): test/integration/\[feature\]\_test.\*  
  * Expected: Tests FAIL (red)

**🟢 GREEN: Implement to Make Tests Pass**

* \[ \] **Task 1.3**: Implement \[component/module\]  
  * File(s): src/\[layer\]/\[component\].\*  
  * Goal: Make Test 1.1 pass with minimal code  
* \[ \] **Task 1.4**: Implement \[integration/glue code\]  
  * File(s): src/\[layer\]/\[integration\].\*  
  * Goal: Make Test 1.2 pass

**🔵 REFACTOR: Clean Up Code**

* \[ \] **Task 1.5**: Refactor for code quality  
  * Files: Review all new code in this phase  
  * Checklist:  
    * \[ \] Remove duplication (DRY principle)  
    * \[ \] Improve naming clarity  
    * \[ \] Add inline documentation

#### **Quality Gate ✋**

**⚠️ STOP: TERMINAL VERIFICATION ONLY**

**Validation Commands**:

\# Example commands (Customize for your project):  
\# Backend Logic / API  
\# pytest backend/tests/test\_feature.py  
\# curl http://localhost:8000/api/v1/health

\# Frontend Logic  
\# npm test \-- frontend/\_\_tests\_\_/utils/

**Checklist**:

* \[ \] **TDD**: Tests written first and passed  
* \[ \] **Build**: Project builds without errors (npm run build)  
* \[ \] **No Browser**: Verified without opening Chrome  
* \[ \] **Linting**: No lint errors  
* \[ \] **Coverage**: Test coverage meets requirements

### **Phase 2: \[Core Feature Phase Name\]**

Goal: \[Specific deliverable\]  
Verification Mode: 🖥️ TERMINAL ONLY (No Browser)  
Status: ⏳ Pending | 🔄 In Progress | ✅ Complete

#### **Tasks**

**🔴 RED: Write Failing Tests First**

* \[ \] **Test 2.1**: Write unit tests for \[specific functionality\]  
  * File(s): test/unit/\[feature\]/\[component\]\_test.\*  
  * **Restriction**: Must run in terminal.

**🟢 GREEN: Implement to Make Tests Pass**

* \[ \] **Task 2.3**: Implement \[component/module\]  
  * Goal: Make Test 2.1 pass

**🔵 REFACTOR: Clean Up Code**

* \[ \] **Task 2.5**: Refactor for code quality

#### **Quality Gate ✋**

**⚠️ STOP: TERMINAL VERIFICATION ONLY**

**Validation Commands**:

\# Run tests  
\# npm test \-- \[test\_file\]

**Checklist**:

* \[ \] **TDD**: Tests written first and passed  
* \[ \] **Logic**: Core logic returns correct values in terminal  
* \[ \] **No Browser**: Verified without opening Chrome  
* \[ \] **Coverage**: Test coverage meets requirements

### **Phase 3: \[UI/Enhancement Phase Name\]**

Goal: \[Specific deliverable\]  
Verification Mode: 🧪 JSDOM / HEADLESS (Browser Optional)  
Status: ⏳ Pending | 🔄 In Progress | ✅ Complete

#### **Tasks**

**🔴 RED: Write Failing Tests First**

* \[ \] **Test 3.1**: Write component render tests  
  * Tool: React Testing Library (JSDOM)  
  * **Note**: Does not require real browser.

**🟢 GREEN: Implement to Make Tests Pass**

* \[ \] **Task 3.3**: Implement UI Component  
  * Goal: Make Test 3.1 pass

**🔵 REFACTOR: Clean Up Code**

* \[ \] **Task 3.5**: Refactor for code quality

#### **Quality Gate ✋**

**⚠️ STOP: Validate Component Rendering**

**Validation Commands**:

\# Verify UI Components via JSDOM  
\# npm test \-- frontend/\_\_tests\_\_/components/

**Checklist**:

* \[ \] **Rendering**: Component renders in test environment  
* \[ \] **Interaction**: Clicks/Inputs work in test environment  
* \[ \] **Manual Check**: (Only if visual styling is critical) Open browser briefly

## **⚠️ Risk Assessment**

| Risk | Probability | Impact | Mitigation Strategy |
| :---- | :---- | :---- | :---- |
| \[Risk 1: e.g., API changes\] | Low/Med/High | Low/Med/High | \[Mitigation\] |
| \[Risk 2\] | Low/Med/High | Low/Med/High | \[Mitigation\] |

## **🔄 Rollback Strategy**

### **If Phase 1 Fails**

**Steps to revert**:

* Undo code changes in: \[list files\]  
* Restore configuration: \[specific settings\]  
* Remove dependencies: \[if any were added\]

## **📊 Progress Tracking**

### **Completion Status**

* **Phase 1**: ⏳ 0% | 🔄 50% | ✅ 100%  
* **Phase 2**: ⏳ 0% | 🔄 50% | ✅ 100%  
* **Phase 3**: ⏳ 0% | 🔄 50% | ✅ 100%

**Overall Progress**: X% complete

### **Time Tracking**

| Phase | Estimated | Actual | Variance |
| :---- | :---- | :---- | :---- |
| Phase 1 | X hours | Y hours | \+/- Z hours |
| Phase 2 | X hours | \- | \- |
| Phase 3 | X hours | \- | \- |

## **📝 Notes & Learnings**

### **Implementation Notes**

* \[Add insights discovered during implementation\]

### **Blockers Encountered**

* **Blocker 1**: \[Description\] → \[Resolution\]

### **Improvements for Future Plans**

* \[What would you do differently next time?\]

## **📚 References**

* \[Link to docs\]  
* \[Link to API references\]

## **✅ Final Checklist**

**Before marking plan as COMPLETE**:

* \[ \] All phases completed with quality gates passed  
* \[ \] Full integration testing performed  
* \[ \] Documentation updated  
* \[ \] Security review completed  
* \[ \] Plan document archived