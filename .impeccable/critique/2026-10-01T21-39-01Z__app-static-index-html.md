---
target: queue, library, settings after Sprint 4 follow-ups
total_score: 29
max_score: 40
na_heuristics: 
p0_count: 0
p1_count: 0
timestamp: 2026-10-01T21-39-01Z
slug: app-static-index-html
---
# Critique: queue, library and settings at 390/1280 after Sprint 4 follow-ups (#63–#67)

Method: dual-agent (A: design review · B: detector + browser)

| # | Heuristic | Score | Key Issue |
|---|---|---|---|
| 1 | Visibility of System Status | 3 | Ready count, field checks, «حُفظ النوع», named moves («نُقل «…» إلى مجلد «…»»); "ready" is defined only in a `title` tooltip |
| 2 | Match System / Real World | 3 | Natural domain Arabic; nav «محرر المكتبة» vs heading «مكتبة الصوتيات»; ملف / صوتية / بطاقة for one thing |
| 3 | User Control and Freedom | 3 | Trash + two-tap delete; still no undo after a confirm (the high-stakes action) |
| 4 | Consistency and Standards | 3 | Signal colours hold; queue refresh has no icon while library rescan has one |
| 5 | Error Prevention | 3 | Confirm-all is now two-tap and names the count; a card's confirm and the sticky confirm-all sit as two identical teal blocks at the phone's bottom edge |
| 6 | Recognition Rather Than Recall | 3 | Destination preview and visible chips; the variants notice counts but doesn't name the spellings |
| 7 | Flexibility and Efficiency | 3 | Deep link, channel genre, next-card focus, genre memory; no "next card needing review" jump, no shortcuts |
| 8 | Aesthetic and Minimalist Design | 3 | Needs-review cards 713–819px (was ~950); the nav + header take the first ~275px of the phone screen |
| 9 | Error Recovery | 3 | Specific, calm messages with a next step; waiting confirm leads to the missing field |
| 10 | Help and Documentation | 2 | Settings hints and debug steps are explained; the queue has no help, "ready" only in a tooltip |
| **Total** | | **29/40** | **Good** (unchanged: last run's issues are fixed, new ones found at the same depth) |

Corrections to A, checked against the source: a single confirm does name where the file went (app.js:2063, «نُقل «…» إلى مجلد «…»»); a Telegram link scrolls to and focuses its card (PR #66), it isn't "located in a list"; the needs-review banner is ~120 CSS px, not 270 (device px). A's P1 (two teal confirms) is real (seen in the 390 screenshot) but downgraded to P2: a mistaken tap on the bar only arms it since #63.

## Design Specificity Verdict
Authored in its information design and copy: the destination shown as the exact folder/file, a confirm that names what's missing, honest failure copy, ready/needs-review split, channel-aware genre. The visual shell (navy, rounded cards, pill nav, teal CTA) is restrained and on-spec but category-generic on its own; the shelf label and brand mark carry what personality the rules allow.
Detector: CLI 0 findings (index.html only; cards are rendered by app.js). Overlay: 54 (390) / 68 (1280) on the queue, 25–26 on library and settings. Mostly known false positives: gray-on-colour fires on pairs that measure 6.1–13.9:1; hairline-with-shadow resolves to a 0×0 `div.container`; AI-palette and clipped counts repeat identically on every route (shell / hidden SPA views; collapsed cards clip by design); "overflow" is the intended `.path-stem` ellipsis. Real, from B's measurements: the title placeholder is the browser default #757575 at 3.45:1 (no `::placeholder` rule); the artist dropdown toggle is 26×26 on desktop; «التفاصيل التقنية» summaries are 32px tall. No horizontal overflow, no console errors on any route.

## Priority Issues
- **[P2] Two identical teal confirms stacked at the bottom of the phone.** A card's full-width «✓ تأكيد ونقل إلى المكتبة» scrolls directly above the sticky «✓ تأكيد ونقل الجاهزة» bar. Same fill, same ✓ stem, different scope. Fix: give the bar its own look (e.g. Shelf Navy with teal text and the count, «نقل الجاهزة (3)»), keeping solid teal for the card in hand. Command: /impeccable layout
- **[P2] The first third of the phone queue is chrome.** Brand row + tab row + heading/count + a refresh button on its own row: the first card starts at ~275px of 844. Fix: one-row nav under ~400px, refresh as an icon beside the heading (or drop it: SSE plus a 15s poll keep the list live). Command: /impeccable adapt
- **[P2] No undo after a confirm.** The move is the one high-stakes action and the success alert has no «تراجع». Fix: an undo in the success alert for a few seconds that returns the file to the queue (needs a backend move-back). Command: /impeccable shape
- **[P3] "Ready" is defined only in a tooltip.** `title` on #itemCount (index.html:46) never shows on touch. Fix: a visible one-line definition or a tap-to-explain count. Command: /impeccable clarify
- **[P3] Vocabulary drift.** Nav «محرر المكتبة» vs heading «مكتبة الصوتيات» (index.html:25, 77); the variants notice says «فنان واحد مكتوب بأكثر من تهجئة» without naming الأكرف / الاكرف. Command: /impeccable clarify

## Persona Red Flags
- **The operator (one person, phone, night, 10–50 cards):** two teal confirms at the thumb edge; ~1/3 of every first screen is chrome; when the LLM is down every needs-review card repeats the same amber paragraph; no jump to the next card that needs review.
- **Interrupted user (Telegram ping → one confirm):** lands on the card (good); after confirming, nothing offers "back to Telegram" or undo.
- **Low-vision night user:** text tokens 6.1–13.9:1 (good); the empty title placeholder at 3.45:1 is the one failure.

## Minor Observations
- Placeholder contrast 3.45:1 (add a `::placeholder` colour, e.g. Margin Text).
- Artist dropdown toggle 26×26 on desktop; «التفاصيل التقنية» summary 32px tall.
- Same amber banner on every no-key card: one queue-level notice when the cause is shared.
- 1280px: two columns put each confirm below the fold; desktop is secondary.
- Variant rows sit apart in the artist list with no inline merge shortcut.

## Questions to Consider
- If a session is 50 cards, where does the screen say "7 of 50" and "next one needing you"?
- Should a ready card need its own confirm at all, or is confirm-all plus a per-card "not this one" the main path?
- What if the destination plate were the confirm button: the path as the label?
