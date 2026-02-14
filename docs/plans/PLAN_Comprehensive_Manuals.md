# **Implementation Plan: Comprehensive Service Manuals Generation**

Status: 🔄 In Progress  
Started: 2026-02-14  
Last Updated: 2026-02-14  
Estimated Completion: 2026-02-14  

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
Replace missing or sparse service manuals with "rich," comprehensive content for all internal services. This ensures that users (teachers) can immediately understand how to use each tool in a classroom setting.

### **Success Criteria**
* [ ] Rich manuals (3+ sections each) for at least 6 primary services: 쌤BTI, 우리반 캐릭터 친구 찾기, 교사 백과사전, 간편 수합, DutyTicker, 서명 톡.
* [ ] Manuals follow SIS (Service Integration Standard) regarding Rich Content.
* [ ] Data is persisted in production via a clean Django Data Migration.
* [ ] No regressions in existing ServiceManual/ManualSection structure.

### **User Impact**
Teachers will have professional-grade guidance for every tool, increasing user retention and classroom success.

## **🏗️ Architecture Decisions**

| Decision | Rationale | Trade-offs |
| :---- | :---- | :---- |
| Use Django Data Migration | Ensures production DB is automatically populated upon deployment. | Harder to debug than manual SQL if complex. |
| One-Time Migration | Fast delivery for current missing data. | Requires new migrations for future services. |

## **📦 Dependencies**

### **Required Before Starting**
* [ ] `ServiceManual` and `ManualSection` models existing (Verified: Yes).
* [ ] `Product` records for all services existing in DB (Verified: Yes).

## **🧪 Test Strategy (Terminal First)**

### **Testing Approach**
TDD Principle: Verify data constraints via shell before and after migration.

| Test Type | Coverage Target | Tool & Env |
| :---- | :---- | :---- |
| **Logic Verification** | Manual Counts & Content | `python manage.py shell` |
| **Integrity** | Foreign Key Validity | `python manage.py check` |

## **🚀 Implementation Phases**

### **Phase 1: Content Synthesis & Script Preparation**
Goal: Prepare the Python dictionary/list containing all rich content for the migration.
Verification Mode: 🖥️ TERMINAL ONLY (No Browser)

#### **Tasks**
* [ ] **Task 1.1**: Synthesize rich text for 6+ services (3 sections each).
* [ ] **Task 1.2**: Create a temporary Python script to validate product titles match existing DB records.
* [ ] **Task 1.3**: Verify content length and "richness" (Markdown usage, Tip boxes).

#### **Quality Gate ✋**
* [ ] **Titles**: All titles in script match `Product.objects.all()` output.
* [ ] **Richness**: Each manual has ≥3 sections.

### **Phase 2: Final Migration Generation**
Goal: Generate and apply the migration file.
Verification Mode: 🖥️ TERMINAL ONLY

#### **Tasks**
* [ ] **Task 2.1**: Generate an empty migration in `products`.
* [ ] **Task 2.2**: Paste the prepared content into the `RunPython` forward function.
* [ ] **Task 2.3**: Implement safe `get_or_create` logic to prevent duplicates.
* [ ] **Task 2.4**: Run `python manage.py migrate products`.

#### **Quality Gate ✋**
* [ ] **Success**: Migration applies without error.
* [ ] **Counts**: `ServiceManual.objects.count()` matches expected 8+ count.

## **📊 Progress Tracking**
* **Phase 1**: ✅ 100%
* **Phase 2**: ✅ 100%

## **📝 Notes & Learnings**
* Acknowledged user frustration and shifted to extreme thoroughness.
* Successfully migrated rich content for 10 services.
* Validated section counts (3 each) via shell.
