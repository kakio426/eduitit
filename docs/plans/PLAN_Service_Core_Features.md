# **Implementation Plan: Service Core Features (Foundation)**

**Status**: 🔄 In Progress  
**Started**: 2026-02-08  
**Last Updated**: 2026-02-08  
**Estimated Completion**: 2026-02-12  

**⚠️ CRITICAL INSTRUCTIONS**: Follow the Terminal-First protocol. No browser until Phase 7.

## **📋 Overview**

### **Feature Description**
Implement 7 essential service features to enhance reliability, visibility, and user experience of the Eduitit platform. This includes global notifications, error tracking, feedback loops, SEO, analytics, backups, and UI feedback.

### **Success Criteria**
* [ ] 1. Global banner controllable via Admin/Product model.
* [ ] 2. Sentry integration for real-time error logging.
* [ ] 3. Functional feedback widget capturing student/teacher input.
* [ ] 4. Dynamic OpenGraph tags for MBTI results.
* [ ] 5. Stats dashboard displaying Daily/Weekly visitors.
* [ ] 6. Automated DB backup script.
* [ ] 7. Alpine.js + Tailwind Toast system for UI feedback.

## **🏗️ Architecture Decisions**

| Decision | Rationale | Trade-offs |
| :---- | :---- | :---- |
| **Unified Core Extension** | Common utilities (Toast, Banner) go to `core` app to avoid app bloat. | Might clutter `core` if not organized. |
| **Product Model Integration** | Banner and Dashboard settings will be linked to `Product` or a new `SiteConfig` model. | Slightly more complex than hardcoding. |
| **HTMX + Alpine.js** | For Toasts and Feedback Widget to keep SPA feel without heavy JS frameworks. | Requires strict HTMX trigger management. |

## **📦 Dependencies**
* [ ] `sentry-sdk`: For error tracking.
* [ ] `django-dbbackup`: For automated backups.
* [ ] `Alpine.js` (Optional, via CDN/Static): For Toast/Modals.

## **🧪 Test Strategy (Terminal First)**
* **Unit Tests**: Business logic for stats and config retrieval.
* **Integration Tests**: Middleware behavior (Maintenance, Banner logic) using `pytest`.
* **API Tests**: Feedback submission via `curl`.

---

## **🚀 Implementation Phases**

### **Phase 1: UI Feedback System (Toast & Layout Foundations)**
**Goal**: Implement a global toast notification system and standard Claymorphism layout updates.  
**Verification Mode**: 🖥️ TERMINAL (Template analysis) / 🧪 JSDOM  

#### **Tasks**
* [ ] **RED**: Write failing test for a global context processor providing toast messages.
* [ ] **GREEN**: Implement `core/context_processors.py` for toast messages.
* [ ] **GREEN**: Add Alpine.js toast container to `base.html`.
* [ ] **REFACTOR**: Standardize `clay-card` across existing templates.

---

### **Phase 2: Management & Visibility (Global Banner & SEO)**
**Goal**: Static/Dynamic banner and improved SNS preview.  
**Verification Mode**: 🖥️ TERMINAL (curl -I check)  

#### **Tasks**
* [ ] **RED**: Write test for `Product` model providing `is_announcing` field.
* [ ] **GREEN**: Update `Product` model and `base.html` to show top banner.
* [ ] **GREEN**: Implement dynamic `meta` tags in `base.html` using a context processor.

---

### **Phase 3: Feedback Loop (Inquiry Widget)**
**Goal**: A floating feedback widget that saves to DB.  
**Verification Mode**: 🖥️ TERMINAL (curl POST)  

#### **Tasks**
* [ ] **RED**: Write model tests for `Feedback` entries.
* [ ] **GREEN**: Create `Feedback` model in `core`.
* [ ] **GREEN**: Create HTMX-powered feedback modal/widget.
* [ ] **REFACTOR**: Ensure widget uses Claymorphism style.

---

### **Phase 4: Operations & Analytics (Admin Dashboard & Visitor Stats)**
**Goal**: Visualize `VisitorLog` data for admins.  
**Verification Mode**: 🖥️ TERMINAL (Management Command check)  

#### **Tasks**
* [ ] **RED**: Write logic tests for aggregating `VisitorLog` by date.
* [ ] **GREEN**: Create a dashboard view (restricted to superusers).
* [ ] **GREEN**: Integrate basic Chart.js or CSS-based bars for stats.

---

### **Phase 5: Stability & Safety (Error Tracking & Backups)**
**Goal**: Integration with Sentry and DB backup scheduling.  
**Verification Mode**: 🖥️ TERMINAL (shell check)  

#### **Tasks**
* [ ] **Task**: Install and configure `sentry-sdk` via `env` variables.
* [ ] **Task**: Setup `django-dbbackup` and a custom management command for cron execution.

---

## **⚠️ Risk Assessment**
| Risk | Probability | Impact | Mitigation Strategy |
| :---- | :---- | :---- | :---- |
| **Performance Overload** | Med | Low | Cache visitor aggregation results. |
| **Sentry Token exposure** | Low | High | Use environment variables (SIS Std). |

## **🔄 Rollback Strategy**
Revert `MIDDLEWARE` changes in `settings.py` if global hooks cause stability issues.

## **📚 References**
* [SIS Guide](file:///c:/Users/kakio/eduitit/SERVICE_INTEGRATION_STANDARD.md)
* [Skill Handbook](file:///c:/Users/kakio/eduitit/skill.md)
