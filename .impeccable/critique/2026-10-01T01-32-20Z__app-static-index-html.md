---
target: review queue and library on a 390px phone
total_score: 24
max_score: 40
na_heuristics: 
p0_count: 0
p1_count: 2
timestamp: 2026-10-01T01-32-20Z
slug: app-static-index-html
---
# Critique: review queue + library (390px)

Method: dual-agent (A: design review · B: detector + browser)

## Design Health Score
| # | Heuristic | Score | Key Issue |
|---|---|---|---|
| 1 | Visibility of System Status | 3 | Disabled confirm gives no reason; no preview on the needs-review card |
| 2 | Match System / Real World | 3 | "الميتاداتا" undecided; "Unknown • ملف بدون فاصل" source unexplained |
| 3 | User Control and Freedom | 2 | Delete uses native confirm(); two "إلغاء التحديد"; no undo after confirm |
| 4 | Consistency and Standards | 2 | Three ways to select a track; library tabs clip; inline edit vs edit/more |
| 5 | Error Prevention | 3 | Confirm gated; 5-artist mis-parse accepted silently |
| 6 | Recognition Rather Than Recall | 3 | Folder select only appears with 2+ artists; easy to miss |
| 7 | Flexibility and Efficiency | 2 | 4 cards = 3500px scroll; confirm-all only at 2+ ready and scrolls away |
| 8 | Aesthetic and Minimalist Design | 2 | Debug toolbar leads the queue; gradients everywhere; equal weight |
| 9 | Error Recovery | 2 | Needs-review card offers no guidance beyond blank fields |
| 10 | Help and Documentation | 2 | No hint for ";", "المجلد", Unknown source |
| **Total** | | **24/40** | **Acceptable** |

## Design Specificity Verdict
LLM: mostly category-interchangeable dark admin. Authored moments are the RTL craft, devotional genre presets, destination preview, multi-artist rows. Default-SaaS: gradient brand title, gradient nav pill, equal-weight rounded buttons, emoji icons, dev toolbar. The Night Archive is not yet visible.
Detector: CLI clean (index.html, app.js). Live overlay: pending 66, library 34, settings 0. Real: #6b6b6b text on navy ~3.0–3.2:1; gradient-text title; thin-border-wide-shadow (card hover lift); ai-color-palette cyan gradients; skipped heading h1→h3; padding-bottom layout transition. 12 `transition: all`; no prefers-reduced-motion. False positive: #e8e8e8 on #16213e "gray-on-color". Only <44px target at 390: album-artist select (38px).

## Priority Issues
- [P1] Queue is a long scroll with no fast path → compact ready cards, sticky "N ready" action on phones, needs-review sorted last. (/impeccable layout, distill)
- [P1] Trust moment is weak: destination path tiny and faint; disabled confirm silent; needs-review card unexplained → path panel above confirm, reason inside disabled confirm, needs-review checklist. (/impeccable clarify, harden)
- [P2] Dev chrome + gradients undercut calm: debug toolbar leads the queue; gradient title/nav/confirm/chips; hover lift → move debug to settings, flatten to solid signal colours, confirm the only saturated fill. (/impeccable quieter, polish)
- [P2] Library chrome stack (~330px) and three selection models; tabs clip; raw checkbox → fit tabs, merge search+sort, one selection model. (/impeccable layout, adapt)
- [P3] Delete uses native confirm(); low-contrast meta text; outline:none on inputs → two-tap delete, 4.5:1 meta text, visible focus. (/impeccable harden, audit)

## Persona Red Flags
- Alex (50 cards): no next-card flow, batch confirm out of view, no ready/needs-review filter.
- Casey (one hand): delete link ~40px below confirm; tabs clip; long genre + artist scroll.
- Sam: outline:none, 3:1 meta text, emoji-only icons, unlabeled checkbox, no reduced motion.
- Night operator via Telegram: lands on the hardest card, not the pinged one; first screen is a debug toggle.

## Minor Observations
Nav badge overlaps pill and duplicates "4 ملف"; desktop 3-column ragged grid misaligns confirms; settings labels mix English (Bot Token, Chat ID); 👁 emoji toggle.

## Questions
1. Why isn't the first thing on screen the first thing to decide?
2. Would one-card-at-a-time review with auto-advance serve both rhythms better?
3. What if confirm were the only saturated element on the page?
