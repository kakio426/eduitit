# Implementation Plan - Saju DB Integration

Status: 🔄 In Progress
Started: 2026-01-25
Last Updated: 2026-01-25
Estimated Completion: 2026-01-28

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
Integrate a deterministic Database and Logic Engine into the existing Saju (Fortune) service. Currently, the service relies 100% on LLM generation, leading to inconsistencies and calculation errors in the Manse-ryok (chart calculation). This feature implements a "Single Source of Truth" (SSOT) architecture where a Python engine calculates the chart (Four Pillars, Ten Gods, Strength) and the DB stores reference interpretations, which are then fed to the LLM for natural language generation.

### **Success Criteria**
* [ ] **Determinism**: Same input (birth time/location) MUST produce identical Saju characters (Ganji) every time.
* [ ] **Accuracy**: Solar term (Jeolgi) and Time correction (Equation of Time + Longitude) must be mathematically precise.
* [ ] **Consistency**: LLM output matches the calculated chart traits (e.g., if Logic says "Weak Fire", LLM describes "Weak Fire").
* [ ] **Performance**: Chart calculation should happen in < 200ms without LLM latency.

### **User Impact**
Users will receive reliable, consistent fortune readings. Repeated queries will not yield conflicting basic facts (like different Saju characters). Trust in the service's "expert" persona will increase.

## **🏗️ Architecture Decisions**

| Decision | Rationale | Trade-offs |
| :---- | :---- | :---- |
| **Python Logic Engine** | Replacing the proposed Node.js lib with Python equivalents (`korean-lunar-calendar`, `pyswisseph`/`ephem`) to keep the stack unified (Django). | Need to port/verify specific Manse logic in Python if no direct drop-in exists. |
| **DB-First Interpretations** | Storing interpretation fragments in DB allows granular control and easier tuning than editing huge prompts. | Requires initial data constraint/entry effort. |
| **JSON Schema Output** | Forcing LLM to output JSON ensures the UI can render specific data points reliably. | Slightly higher token usage for schema definition. |

## **📦 Dependencies**

### **Required Before Starting**
* [x] `saju db.md` analysis (Completed)
* [ ] `fortune` app (Existing)

### **External Dependencies**
* `korean-lunar-calendar`: For reliable Lunar<->Solar conversion.
* `pyswisseph` or `ephem`: For high-precision Solar Term (Jeolgi) calculation.
* `pytz`: For timezone handling.

## **🧪 Test Strategy (Terminal First)**

### **Testing Approach**
TDD Principle: Write tests FIRST.
Speed Protocol: All logic tests run in `pytest` under 1s.

### **Test Pyramid**
| Test Type | Coverage Target | Tool & Env |
| :---- | :---- | :---- |
| **Unit Tests** | ≥90% (Crucial for Calc Logic) | Pytest (Terminal) |
| **Integration Tests** | DB Models + Logic | Pytest Django (Terminal) |
| **E2E Tests** | API Response Structure | Pytest (Mocking LLM) |

## **🚀 Implementation Phases**

### **Phase 1: Architecture & Models**
Goal: Create the Database Schema for SSOT (Reference Data & User Profiles).
Verification Mode: 🖥️ TERMINAL ONLY
Status: ✅ Complete

#### **Tasks**
**🔴 RED: Write Failing Tests First**
* [x] **Test 1.1**: Test `UserProfile` and `NatalChart` model creation and relationships.
* [x] **Test 1.2**: Test reference models (`Stem`, `Branch`, `SixtyJiazi`) content loading.

**🟢 GREEN: Implement to Make Tests Pass**
* [x] **Task 1.3**: Create models in `fortune/models.py`:
    * `Stem` (Ten Heavenly Stems), `Branch` (Twelve Earthly Branches)
    * `SixtyJiazi` (60 Pillars combination)
    * `UserProfile` (Extended with birth city, lat/long)
    * `NatalChart` (Stores calculated pillars)
* [x] **Task 1.4**: Create a management command `seed_saju_data` to populate the reference tables (Stems, Branches, 60Jiazi basics).

**🔵 REFACTOR: Clean Up Code**
* [x] **Task 1.5**: Ensure field names match the `saju db.md` spec (e.g., `year_stem`, `day_master_strength`).

#### **Quality Gate ✋**
**Validation Commands**:
```bash
python manage.py test fortune.tests.test_models
python manage.py check
```
**Checklist**:
* [x] Models migrate successfully.
* [x] Seed command populates 10 Stems, 12 Branches, 60 Jiazi.

### **Phase 2: Manse-ryok Engine (The Math)**
Goal: Implement the astronomical calculation engine.
Verification Mode: 🖥️ TERMINAL ONLY
Status: ✅ Complete

#### **Tasks**
**🔴 RED: Write Failing Tests First**
* [x] **Test 2.1**: Test Solar Term (Jeolgi) dates (e.g., Verify Lichun time for 2024).
* [x] **Test 2.2**: Test Longitude/Equation of Time correction (Verify Seoul vs Tokyo solar time diff).
* [x] **Test 2.3**: Test Lunar -> Solar conversion accuracy.

**🟢 GREEN: Implement to Make Tests Pass**
* [x] **Task 2.4**: Install `korean-lunar-calendar`, `ephem`.
* [x] **Task 2.5**: Implement `libs/manse.py` (or similar utility):
    * `get_solar_terms(year)`
    * `get_apparent_solar_time(date, long)`
    * `lunar_to_solar(date)`

**🔵 REFACTOR**
* [x] **Task 2.6**: Optimize for speed.

#### **Quality Gate ✋**
**Validation Commands**:
```bash
pytest fortune/tests/test_manse.py
```

### **Phase 3: Logic Engine (Pillars & Strength)**
Goal: Implement the logic to derive the Four Pillars and Analyze Strength.
Verification Mode: 🖥️ TERMINAL ONLY
Status: ✅ Complete

#### **Tasks**
**🔴 RED: Write Failing Tests First**
* [x] **Test 3.1**: Test `Year Pillar` change at Lichun (not Jan 1).
* [x] **Test 3.2**: Test `Hour Pillar` calculation (Five Rats method).
* [x] **Test 3.3**: Test `Ten Gods` derivation logic.

**🟢 GREEN: Implement to Make Tests Pass**
* [x] **Task 3.4**: Implement `Calculator` class in `fortune/logic.py`:
    * `calculate_pillars(solar_date, time)`
    * `determine_ten_gods(day_master, target_stem)`
    * `determine_strength(chart)` (Scoring method from md)

**🔵 REFACTOR**
* [x] **Task 3.5**: Handle edge cases (Midnight sorting, Leap months).

#### **Quality Gate ✋**
**Validation Commands**:
```bash
pytest fortune/tests/test_logic.py
```

### **Phase 4: Interpretation Rules & LLM Integration**
Goal: Integrate the Logic Engine with the View and feed structured data to LLM.
Verification Mode: 🖥️ TERMINAL ONLY (Mock LLM)
Status: ✅ Complete

#### **Tasks**
**🔴 RED: Write Failing Tests First**
* [x] **Test 4.1**: Test View calls Logic Engine before LLM.
* [x] **Test 4.2**: Test Prompt construction includes calculated `NatalChart` JSON.

**🟢 GREEN: Implement to Make Tests Pass**
* [x] **Task 4.3**: Create `InterpretationRule` model and seed basic rules.
* [x] **Task 4.4**: Update `saju_view` in `views.py`:
    * Parse input -> Call Logic Engine -> Get structured Chart.
    * Retrieve relevant Rules from DB.
    * Construct System Prompt with "Persona" and strict Data.
* [x] **Task 4.5**: Update `prompts.py` to accept the JSON context.

**🔵 REFACTOR**
* [x] **Task 4.6**: Implement Caching (Redis/LocMem) for identical inputs.

#### **Quality Gate ✋**
**Validation Commands**:
```bash
python manage.py test fortune.tests.test_views
```

## **⚠️ Risk Assessment**

| Risk | Probability | Impact | Mitigation Strategy |
| :---- | :---- | :---- | :---- |
| **Logic Complexity** | High | High | Use reference library outputs to validat unit tests. |
| **Lat/Long Data** | Med | Med | Use a standard simplified map for Korea (Seoul/Busan/etc) major cities first. |
| **LLM Schema Adherence** | Med | Med | Use strict JSON mode or robust parsers. |

## **🔄 Rollback Strategy**
* Keep the old Prompt-only logic as a fallback flag (`USE_LEGACY_LOGIC = True`).

