# **Implementation Plan: Chess Logic Refactor & UI Enhancement**

Status: 🔄 In Progress
Started: 2026-02-03
Estimated Completion: 2026-02-03

## **📋 Overview**
Refactor the Chess game logic from inline JavaScript in `play.html` to a dedicated `chess_logic.js` file. Enhance the UI with a difficulty adjustment slider and ensure robust "Pure JS" Stockfish integration.

### **Goals**
1.  **Refactor**: Move game logic to `static/chess/js/chess_logic.js` to clean up `play.html` and fix potential AI compilation/execution scope issues.
2.  **Fix AI**: Ensure the new "Pure JS" Stockfish interacts correctly with the refactored logic.
3.  **UX Constraint**: **STRICTLY "Click-to-Move" only**. No Drag-and-Drop.
4.  **Preserve**: Keep the existing "Difficulty" logic (Django `{{ difficulty }}` variable).

## **📦 Dependencies**
*   `chessboard.js` (CDN)
*   `chess.js` (CDN)
*   `stockfish.js` (Local: `static/chess/js/stockfish.js`)

## **🚀 Implementation Phases**

### **Phase 1: Setup & Logic Extraction**
*   [ ] **Create JS File**: Create `chess/static/chess/js/chess_logic.js`.
*   [ ] **Implement Logic**:
    *   Initialize `Chess`, `Chessboard`, and `Worker` (Pure JS Stockfish).
    *   **Logic Fix**: Ensure `Stockfish` worker is correctly instantiated and message passing works in the separate file.
    *   **Click-to-Move**: Implement robust `onClick` logic (No Drag & Drop).
    *   **Difficulty**: Port existing `easy/medium/hard` logic to the new file.
*   [ ] **Update Template**:
    *   Remove inline JS from `play.html`.
    *   Pass `STOCKFISH_PATH` and `DIFFICULTY` variables to the external JS configuration.

### **Phase 2: Verification**
*   [ ] **Load Test**: Verify `chess_logic.js` loads correctly (200 OK).
*   [ ] **Worker Test**: Verify Stockfish Worker initializes from the external script.
*   [ ] **Game Loop**: Play a full game (Human vs AI).
    *   Check slider limits (0-20).
    *   Verify AI strength changes (subjective/debug logs).

## **🧪 Verification Plan**

### **Automated Checks (Terminal)**
*   `curl -I` to check static file availability.
*   `grep` to ensure `play.html` has no inline game logic.

### **Manual Logic Check**
*   **AI**: Verify AI responds to moves (Game actually starts).
*   **Difficulty**: Verify `Skill Level` is set correctly based on the Django variable.
*   **UX**: Verify "Click-to-Move" works seamlessly on Mobile/PC. (No Dragging).
