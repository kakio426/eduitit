# PLAN: Design System Architecture Overhaul (Final Structural Repair)

As the Design System Architect, I acknowledge the high stress caused by inconsistent AI designs. I will now execute a **Structural Repair** based solely on the numerical constraints provided. There will be **zero creative deviation**.

## 🔴 Absolute Numerical Constraints Checklist
I will verify these items are met in every file I touch:
- [ ] **Line-Height**: Global `leading-tight` or `leading-[1.1]` for all Dongle text.
- [ ] **Word-Break**: Mandatory `break-keep` for all Korean text (titles/body).
- [ ] **Text Overflow**: Stringent use of `line-clamp-2` or `truncate`.
- [ ] **Fluid Headers**: `clamp()` functions for H1-H3 (e.g., `text-[clamp(1.5rem,5vw,3.5rem)]`).
- [ ] **Navbar Height**: Desktop `h-16 (64px)` / Mobile `h-14 (56px)`.
- [ ] **Hero Fold**: Entire Hero content must fit within `calc(100vh - 64px)`.
- [ ] **Spacing**: Standard gap usage (`gap-4` or `gap-6`). No `my-20`.
- [ ] **Card Ratio**: Title-to-Body font size ratio of **1.4 : 1**.
- [ ] **Card Padding**: Mobile `p-4` / Desktop `p-6`.
- [ ] **Shadow Opacity**: Reduce shadow opacity by **20%** globally.
- [ ] **Mobile Flex**: Force `flex-col` on `< md` with `y-3` gap max.
- [ ] **Mobile Safe Area**: Mandatory `px-4` or `px-5` lateral padding.
- [ ] **Touch Targets**: Minimum `44px` height for all interactive elements.

---

## Phase Breakdown

### Phase 1: Foundation (base.html & tailwind.config)
**Goal**: Enforce typography rules and shadow depths.
- [ ] **RED**: Analyze current bloated `line-height` and `fontSize` overrides.
- [ ] **GREEN**: Set global `leading-tight`, `break-keep`, and `-20% opacity` shadows.
- [ ] **REFACTOR**: Implement `clamp()` for H1-H3 to ensure mobile headers stay within 2 lines.

### Phase 2: Structural Repair (Navbar & Hero Fold)
**Goal**: Slim down the UI to optimize the first fold.
- [ ] **RED**: Identify elements pushing Hero content below the 100vh fold.
- [ ] **GREEN**: Hard-cap Navbar at `h-16`/`h-14` and Hero at `calc(100vh - 64px)`.
- [ ] **REFACTOR**: Ensure `py-2` padding in Navbar and unified gaps (`gap-4`).

### Phase 3: Component Restoration (Cards & Modals)
**Goal**: Standardize cards/modals and integrate missing School Violence card.
- [ ] **RED**: Locate School Violence Assistant missing from the `home.html` grid.
- [ ] **GREEN**: Insert SV Assistant card. Apply **1.4:1** ratio and `p-4`/`p-6` padding to ALL cards.
- [ ] **REFACTOR**: Standardize `#unifiedModal` padding (`p-6`) and close button size (`w-10 h-10`).

### Phase 4: Mobile First & Global Audit
**Goal**: Final responsive polish and sub-page synchronization.
- [ ] **RED**: Audit `autoarticle`, `portfolio`, etc., for layout-breaking local styles.
- [ ] **GREEN**: Force `flex-col` / `y-3` gap on mobile. Apply `px-4` safe areas.
- [ ] **REFACTOR**: Ensure all buttons meet min `44px` height with `w-full` on mobile.

## Verification Protocol
- **CLI Check**: `curl.exe -I http://127.0.0.1:8000` to ensure server stability.
- **Visual Audit**: Opening all modals (Prompt Lab, Feature Previews) to verify structural integrity.
- **Responsive Check**: Simulating mobile viewport to confirm "Safe Area" and "Touch Target" compliance.
