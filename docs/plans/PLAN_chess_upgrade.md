# **Implementation Plan: Chess Game Experience Upgrade**

Status: 🔄 In Progress  
Started: 2026-02-09  
Last Updated: 2026-02-09  
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
Upgrade the current chess game from a basic board to a full "Experience" by adding legal move hints, algebraic notation history, captured pieces tracking, a proper pawn promotion UI, and immersive sound effects.

### **Success Criteria**
* [ ] **Visual Clarity**: Last move highlights and King-in-check visualization work correctly.
* [ ] **Guidance**: Users see legal moves for the selected piece.
* [ ] **Recording**: All moves are recorded in standard algebraic notation (SAN).
* [ ] **Completeness**: Pawn promotion allows choosing between Q, R, B, and N.
* [ ] **Audio**: Interactive sounds for move, capture, and check.

### **User Impact**
Greatly improves playability for beginners and provides the "standard" feel of a modern chess application, making it suitable for educational use.

## **🏗️ Architecture Decisions**

| Decision | Rationale | Trade-offs |
| :---- | :---- | :---- |
| **Logic-First SAN** | Calculate SAN in `chess_logic.js` using `chess.js` capabilities. | Requires careful syncing with the move history list. |
| **Custom Promotion Modal** | Use a tailored HTML/CSS modal instead of `window.confirm`. | Increases UI complexity but significantly improves UX. |
| **Terminal Validation** | Use `npm test` or standalone node scripts for logic verification (SAN, material count). | Requires setting up small test scripts for helper functions. |

## **📦 Dependencies**

### **Required Before Starting**
* [x] Chess.js (already integrated)
* [x] Chessboard.js (already integrated)
* [ ] Audio assets for move/capture (need to locate or provide fallbacks)

## **🧪 Test Strategy (Terminal First)**

### **Testing Approach**
TDD Principle: Write logic tests for SAN generation and material calculation FIRST in the terminal.

| Test Type | Coverage Target | Tool & Env |
| :---- | :---- | :---- |
| **Unit Tests** | Logic for SAN & Material | Node.js / JSDOM (Terminal) |
| **Integration Tests** | Move cycle logic | Node.js (Terminal) |
| **E2E Tests** | Promotion/Modal flow | Playwright (Headless) |

## **🚀 Implementation Phases**

### **Phase 1: Game State Logic & Notation**
Goal: Implement material advantage calculation and robust SAN move history.  
Verification Mode: 🖥️ TERMINAL ONLY  
Status: ✅ Complete

#### **Tasks**
**🔴 RED: Write Failing Tests First**
* [x] **Test 1.1**: Write tests for material advantage calculation (counting captured pieces).
* [x] **Test 1.2**: Write tests for SAN move string generation (e.g., verifying `e4`, `Nf3`, `O-O`).

**🟢 GREEN: Implement to Make Tests Pass**
* [x] **Task 1.3**: Implement `getMaterialAdvantage()` in `chess_logic.js`.
* [x] **Task 1.4**: Refactor `updateMoveHistory()` to use standard notation stores.

#### **Quality Gate ✋**
* [x] **Logic**: Material count matches piece count exactly in terminal tests.
* [x] **Notation**: Notation strings match standard chess rules (using chess.js built-in SAN).

---

### **Phase 2: UI Panels & Styles**
Goal: Add History panel and Captured Pieces UI with Last Move/Check highlights.  
Verification Mode: 🧪 JSDOM / HEADLESS  
Status: ✅ Complete

#### **Tasks**
* [x] **Task 2.1**: Update `play.html` CSS for `.highlight-last-move` and `.highlight-check-king`.
* [x] **Task 2.2**: Implement "Captured Pieces" visual containers in `play.html`.
* [x] **Task 2.3**: Update `highlightSquare()` in `chess_logic.js` for these new types.

#### **Quality Gate ✋**
* [x] **Rendering**: Styles apply correctly to chessboard squares in JSDOM.

---

### **Phase 3: Pawn Promotion UI**
Goal: Implement the 4-choice promotion modal.  
Verification Mode: 🧪 JSDOM / HEADLESS  
Status: ✅ Complete

#### **Tasks**
* [x] **Task 3.1**: Create `promotionModal` HTML/CSS.
* [x] **Task 3.2**: Hook `onSquareClick` to pause for promotion if a pawn reaches the 8th rank.
* [x] **Task 3.3**: Finalize move after promotion choice.

#### **Quality Gate ✋**
* [x] **Interaction**: Modal appears and piece choice is correctly passed to `game.move()`.

---

### **Phase 4: Sound & Notifications**
Goal: Add audio feedback and toast notifications.  
Verification Mode: 🖥️ TERMINAL / MANUAL (Final)  
Status: ✅ Complete

#### **Tasks**
* [x] **Task 4.1**: Create `soundManager` utility to load and play move/capture/check sounds.
* [x] **Task 4.2**: Update `handleMoveSuccess` to trigger sounds based on move flags.
* [x] **Task 4.3**: Add "Check!" toast notification.

## **⚠️ Risk Assessment**
| Risk | Probability | Impact | Mitigation Strategy |
| :---- | :---- | :---- | :---- |
| Audio load failure | Medium | Low | Use silent fallbacks or pre-load assets. |
| Promotion sync lag | Low | Medium | Ensure AI waits for promotion choice. |

## **📊 Progress Tracking**
* **Phase 1**: ✅ 100%
* **Phase 2**: ✅ 100%
* **Phase 3**: ✅ 100%
* **Phase 4**: ✅ 100%

**Overall Progress**: 100% complete ✅

## **📚 References**
* [chess.js documentation](https://github.com/jhlywa/chess.js)
* [chessboardjs.com](https://chessboardjs.com/)
