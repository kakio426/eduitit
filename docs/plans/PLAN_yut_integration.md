# Implementation Plan - Yut Noli Integration

The goal is to integrate the "Yut Noli" game (HTML/JS/CSS + MP3s) into the `eduitit` platform as a new service/product.

## Proposed Changes

### Products App

#### [NEW] [yut_game.html](file:///c:/Users/kakio/eduitit/products/templates/products/yut_game.html)
- Extract HTML structure from `index.html`.
- Inherit from `core/base.html`.
- Include CSS and JS (either inline or separated).
- Update Audio paths to use `{% static %}`.
- Refactor CSS to avoid conflicts (scope with `#game-container`).

#### [NEW] Static Files
- Create `products/static/products/yut/`
- Copy `roll.mp3`, `tada.mp3`, `bonus.mp3`, `goal.mp3`, `victory.mp3` to this directory.

#### [MODIFY] [views.py](file:///c:/Users/kakio/eduitit/products/views.py)
- Add `yut_game` view function.
- It should render `products/yut_game.html`.

#### [MODIFY] [urls.py](file:///c:/Users/kakio/eduitit/products/urls.py)
- Add path `yut/` pointing to `yut_game`.

#### [NEW] [0004_add_yut_product.py](file:///c:/Users/kakio/eduitit/products/migrations/0004_add_yut_product.py)
- Data migration to insert "Online Yut Noli" into the Product table so it appears in the product list.

## Verification Plan

### Automated Tests
- Test that `/products/yut/` returns 200 OK.
- Test that static files (mp3) are accessible.

### Manual Verification
- Go to `/products/` and check if "Yut Noli" card appears.
- Click it and verify the game loads.
- Play a turn to ensure Audio plays and canvas renders.
