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