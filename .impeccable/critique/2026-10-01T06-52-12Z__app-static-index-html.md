---
target: review queue, library and settings at 390/1280 after Sprint 4
total_score: 28
max_score: 40
na_heuristics: 
p0_count: 0
p1_count: 2
timestamp: 2026-10-01T06-52-12Z
slug: app-static-index-html
---
# Critique: review queue + library + settings (390px / 1280px), after Sprint 4 B2–B9

Method: dual-agent (A: design review · B: detector + browser)

## Design Health Score
| # | Heuristic | Score | Key Issue |
|---|---|---|---|
| 1 | Visibility of System Status | 3 | "Ready" is told only by the collapse; no session progress until the queue empties |
| 2 | Match System / Real World | 3 | Domain terms right; «تحديد متعدد» / «مراجعة» / «تعديل» terse |
| 3 | User Control and Freedom | 3 | Trash + two-tap delete; no undo after a confirm |
| 4 | Consistency and Standards | 3 | «تحديث القائمة» full-width bar on phones, pill on desktop |
| 5 | Error Prevention | 3 | Confirm explains what's missing; delete still sits close under confirm |
| 6 | Recognition Rather Than Recall | 3 | Collapsed ready card hides the title until «تعديل» |
| 7 | Flexibility and Efficiency | 2 | Needs-review path is a long scroll; no genre carry-over, no keys, no next-card focus |
| 8 | Aesthetic and Minimalist Design | 3 | Flat and quiet; title repeats in source line + destination path on long titles |
| 9 | Error Recovery | 3 | Reason + checklist on the card; no inline "use channel as artist" |
| 10 | Help and Documentation | 2 | ✓/○ checklist and "ready" never explained in the queue |
| **Total** | | **28/40** | **Good** (was 24/40) |

## Design Specificity Verdict
LLM: specific in structure and behaviour (needs-review checklist, provenance line, destination preview, collapsed ready cards, variant notice, One Meaning colour discipline, RTL with isolated Latin), quiet to the point of anonymity in surface. The brand mark and teal confirm are the only elements no dark admin template would have.
Detector: CLI 0 findings (index.html, app.js, style.css; was 17 at B6 start). Overlay (6 page×viewport runs, hidden SPA routes inflate counts): "gray on colour" on #e8e8e8 / #a0a0a0 over Shelf Navy (≈12:1 and ≈6:1, false positive); "ai palette" on Settled Teal (brand signal, deliberate); hairline + wide shadow on artist suggestions and the sticky library controls (overlays, allowed by Flat-At-Rest); "clipped by overflow" on cards (collapse by design). No gradients computed anywhere, no horizontal overflow at 390, no console errors. Sub-44px at 390: token show/hide toggle (56×36, inside the input).
Corrections to A (verified): the ready bar is bottom-anchored; prefers-reduced-motion exists (B6, fades kept, movement off); settings labels are already Arabic with a Latin hint.

## Priority Issues
- [P1] Needs-review cards are a long, undifferentiated column and the genre grid is 6 equal choices: group identity / destination / genre, offer the last-used or channel genre first, move each ✗ chip next to its field. (/impeccable layout)
- [P1] Redundant text: source line, destination path and title repeat the same long string: show the source once (in details), shorten the path to folder + file. (/impeccable distill)
- [P2] Delete directly under confirm at full width: demote to a text action with space from confirm, or an undo toast. (/impeccable harden)
- [P2] Disabled confirm is a dead end: tapping it should focus the first missing field. (/impeccable clarify)
- [P3] Nothing explains ✓/○ or "ready"; «تعديل» chip is small; token toggle 36px tall. (/impeccable onboard, polish)

## Persona Red Flags
- Alex (50 cards): no next-card focus after confirm, no genre carry-over or keyboard path; confirm-all covers only the ready subset.
- Casey (one hand): delete in the thumb zone beside confirm; long review cards put confirm far down.
- Sam: badge now named («N ملفات في الانتظار», fixed in B9); colour + glyph state is good; RTL screen-reader order with Latin islands untested.
- Night operator from a Telegram ping: lands on the queue but not on the pinged card; no deep link.

## Minor Observations
Full-width «تحديث القائمة» takes first-screen space on phones; brand mark is small; «مراجعة» on the variant notice is weaker than its amber box; desktop header actions float without structure.

## Questions
1. Why does a collapsed ready card lead with the title the operator rarely changes, rather than the artist/folder/genre that decide where it lands?
2. Would one-decision-per-card review (artist or genre) serve the 50-card session better than full cards?
3. What single element would make this tool recognisable in a screenshot?
