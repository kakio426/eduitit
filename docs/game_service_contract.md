# Game Service Contract

## Classroom game contract
- Each game must keep one clear path for `launch`, `rules`, and `play`.
- Unsupported modes must not appear in portal copy, product features, or manuals.
- Student portal launches must preserve `hide_navbar` and avoid duplicate global chrome.
- New games should reuse the current browser-first structure unless a later project explicitly approves a new runtime.

## Supported mode matrix
| Surface | Launch path | Supported modes | Notes |
| --- | --- | --- | --- |
| Chess | `chess:index` | `local`, `ai` | Player can choose mode before play. |
| Janggi | `janggi:index` | `local`, `ai` | Browser AI only, no room sync. |
| Fairy games | `fairy_games:play_*` | `local` only | Applies to Dobutsu, Connect Four, Isolation, Ataxx, Breakthrough, Reversi. |
| Reflex game | `reflex_game:main` | `single`, `battle` | Same-screen activity flow. |
| Yut game | `yut_game` | `local` only | Large-screen optimized; mobile shows a blocked-state reason. |

## Registration rules
- A product `launch_route_name` must point to a real route that opens without extra setup.
- `ServiceManual` must be published and describe only supported modes.
- Student portal descriptions should explain the actual play style in one sentence.
