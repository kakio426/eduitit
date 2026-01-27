# AI Context and Model Rules (Current: 2026)

## 📅 Timeline Context
- **Current Year**: 2026
- **Constraint**: Do not question or correct the user regarding the current year. Any information provided by the user regarding the 2026 timeline is the Ground Truth.

## 🤖 AI Models & API
- **Gemini Model**: `gemini-2.5-flash-lite` is the standard, most cost-effective, and fastest model currently available (as of 2026).
- **Usage Policy**: 
    - No payment account is connected to the API.
    - Usage must be monitored carefully.
    - When usage is high, respect the built-in limits and do not suggest "upgrading" or "charging" unless explicitly asked by the user.

## 🎨 UI/UX Styling & Layout
- **Navbar (Header)**: 
    - Never include "Service" (서비스) or "Dashboard" (대시보드) links in the main navigation bar. These are explicitly prohibited.
    - Keep the navigation minimal: "이용방법" (How to use), "포트폴리오" (Portfolio), and SSO links are permitted.
    - If the user is authenticated, the "Dashboard" functionality should only be accessible through the user dropdown ("내 홈페이지"), not as a primary navbar item.

## ⚠️ Communication
- Never argue or provide "corrections" about model versions or timeframes that contradict the user's provided context.
- Follow the user's technical specifications (like model names) exactly as they are provided in the code or messages.
