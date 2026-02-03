# **Implementation Plan: Chess AI & UX Fix**

Status: 🔄 In Progress
Started: 2026-02-03
Last Updated: 2026-02-03
Estimated Completion: 2026-02-03

**⚠️ CRITICAL INSTRUCTIONS**:
1. ✅ Check off completed task checkboxes
2. 🧪 Run all quality gate validation commands in **TERMINAL**
3. ⚠️ Verify ALL quality gate items pass
4. 📝 Document learnings in Notes section
5. ➡️ Only then proceed to next phase

⛔ DO NOT OPEN BROWSER unless explicitly instructed in the phase.

## **📋 Overview**

### **Feature Description**
Fix the Chess game functionality which is currently broken. Specifically:
1.  **UX**: Replace the buggy drag-and-drop interaction with a robust "Click-to-Move" system on both Desktop and Mobile.
2.  **AI**: Ensure the Stockfish AI engine loads correctly from a local file (bypassing CSP/CORS issues) and processes moves without memory errors.

### **Success Criteria**
* [ ] **Drag Disabled**: Chess pieces cannot be dragged on any device.
* [ ] **Click-to-Move**: Clicking a piece highlights it; clicking a valid square moves it.
* [ ] **AI Response**: The AI (Black) automatically responds to the player's move within 5 seconds.
* [ ] **No OOM**: No "Out of Memory" errors in the console.

### **User Impact**
Users will be able to play chess reliably on mobile devices without scroll conflicts, and the AI opponent will actually function.

## **🏗️ Architecture Decisions**

| Decision | Rationale | Trade-offs |
| :---- | :---- | :---- |
| **Local Stockfish** | External CDN was unreliable/blocked. Local file ensures availability. | Increases repository size (~1.5MB). |
| **Disable DnD** | Drag-and-drop caused scroll issues on mobile and user frustration. | Lose "tactile" feel of moving pieces (but gains reliability). |
| **Document Delegation** | `chessboard.js` dynamically creates elements. Binding to `document` ensures events are caught. | Slight performance cost on click (negligible). |

## **📦 Dependencies**

### **Required Before Starting**
* [x] `static/js/stockfish.js` exists in the file system.

## **🧪 Test Strategy (Terminal First)**

### **Testing Approach**
We will verify file existence, configuration correctness, and logic validity using terminal commands (grep, curl, node) before assuming it works in the browser.

## **🚀 Implementation Phases**

### **Phase 1: Asset & Configuration Verification**

Goal: Ensure AI engine files are correctly placed and configured.
Verification Mode: 🖥️ TERMINAL ONLY
Status: ✅ Complete

#### **Tasks**

**🔴 RED: Write Failing Tests First**
* [x] **Test 1.1**: Verify `stockfish.js` is serving correctly.
  * **Restriction**: Use `ls` or `dir` to check file presence and size.

**🟢 GREEN: Implement to Make Tests Pass**
* [x] **Task 1.2**: (Already done) Download `stockfish.js` to `static/js/`.

**🔵 REFACTOR: Clean Up Code**
* [x] **Task 1.3**: Ensure `settings_production.py` allows serving static files correctly (check `STATICFILES_DIRS`).

#### **Quality Gate ✋**
**⚠️ STOP: TERMINAL VERIFICATION ONLY**
* [x] **File Exists**: `static/js/stockfish.js` > 1MB. (Verified: 1,579,948 bytes)
* [x] **Config Check**: `settings_production.py` contains `stockfish.js` in CSP (blobs/self). (Updated)

### **Phase 2: Frontend Logic Fix (Click-To-Move)**

Goal: Completely disable drag-and-drop and implement robust Click-to-Move.
Verification Mode: 🖥️ TERMINAL ONLY (Code Review via Grep)
Status: ✅ Complete

#### **Tasks**

**🔴 RED: Write Failing Tests First**
* [x] **Test 2.1**: Check `play.html` for `draggable: false`.
    * Command: `grep "draggable: false" chess/templates/chess/play.html`

**🟢 GREEN: Implement to Make Tests Pass**
* [x] **Task 2.2**: Modify `play.html`:
    * Set `draggable: false` in `Chessboard` config.
    * implement `onSquareClick` with Document Delegation.
    * Add `highlight-selected` CSS.

**🔵 REFACTOR: Clean Up Code**
* [x] **Task 2.3**: Remove old `onDragStart` logic that is no longer needed.

#### **Quality Gate ✋**
**⚠️ STOP: TERMINAL VERIFICATION ONLY**
* [x] **Config Verified**: `grep` confirms `draggable: false`.
* [x] **Event Binding**: `grep` confirms `$(document).on('click'` usage.

### **Phase 3: AI Integration Fix**

Goal: Ensure AI Worker initializes correctly.
Verification Mode: 🖥️ TERMINAL ONLY (Code Inspection)
Status: ✅ Complete

#### **Tasks**

**🔴 RED: Write Failing Tests First**
* [x] **Test 3.1**: Check for Local Worker initialization.
    * Command: `grep "new Worker" chess/templates/chess/play.html`

**🟢 GREEN: Implement to Make Tests Pass**
* [x] **Task 3.2**: Ensure `play.html` uses `{% static 'js/stockfish.js' %}` for the worker path.
* [x] **Task 3.3**: Verify OOM mitigations (`Hash` value 16).

#### **Quality Gate ✋**
**⚠️ STOP: TERMINAL VERIFICATION ONLY**
* [x] **Syntax Check**: Python logic in template is correct.
* [x] **Path Check**: Static tag usage is correct. (Verified: stockfishPath uses static tag)

## **⚠️ Risk Assessment**

| Risk | Probability | Impact | Mitigation Strategy |
| :---- | :---- | :---- | :---- |
| **Static File Not Served** | Medium | High | Verify `collectstatic` runs on Railway. |
| **Worker Blocked by CSP** | Low | High | We updated CSP to allow `blob:` and `'self'`. |

## **✅ Final Checklist**
* [ ] All phases completed.
* [ ] `git push` performed.
* [ ] User verifies on production.
