# Sprint 4: UI follow-ups and design pass

**Follows:** [AUDIT_REVIEW_AND_PLAN.md](AUDIT_REVIEW_AND_PLAN.md) (Sprints 0–3 done) · **Date:** 2026-09-30
**Evidence:** finding numbers like `#27` refer to [PROJECT_INSPECTION_2026-09-30.md](PROJECT_INSPECTION_2026-09-30.md).

The previous sprints fixed data safety, the confirm flow, deployment, and the phone layout. What's left is
UI work. It comes in two tracks:

- **Track A — fixes.** Behavior that is wrong or risky today. Done the usual way: failing test first, one PR each.
- **Track B — design pass.** Looks, motion and copy, driven by `/impeccable` commands. Starts after Track A,
  because animating or restyling screens that are about to change wastes work.

Context for every decision: one operator, mostly on a **phone**, Arabic RTL, reached over Tailscale.
This is an *operate* tool. Speed of reviewing a queue matters more than flourish.

---

## Track A — fixes

| # | Ticket | Simplest fix | Covers |
|---|---|---|---|
| S4-1 | **Batch edit only changes what you touched** | Every field defaults to *keep*. A field becomes *set* when edited, or *clear* when explicitly cleared. Before saving, show "N tracks · fields: genre, year". API: dedupe IDs, cap batch size, and return per-track failures, which the UI shows. | #27, part of #24 |
| S4-2 | **Rescan shows progress and can't get stuck** | Show `processed / total · errors` from `/rescan/status`, which already exists. If a status poll fails, re-enable the button and show the error. On page load, if a scan is running, resume polling. Set the scanning flag before the thread starts, so two quick clicks can't start two scans. | #23 |
| S4-3 | **The album artist you see is the one you get** | The card labels the derived album artist explicitly ("المجلد: {album_artist}"), and you can pick another listed artist. Confirm sends `album_artist`. The destination preview (dry-run) is shown in the normal card, not only in debug mode. | #31 (album-artist part) |
| S4-4 | **Telegram can be turned off** | An `enabled` flag and a "قطع الاتصال" action that clears the token and chat ID. Error text from Telegram is stripped of the bot token before it is logged or shown. | #32 |
| S4-5 | **Favicon: 347 KB → under 10 KB** | Export 32px and 180px (apple-touch) PNGs and replace the link tags. | #34 |
| S4-6 | **Edits inside album/genre views refresh the right list** | After a save, reload the *current* context (detail identity, filter, page) instead of the top-level list. Ignore fetch responses that are older than the latest request. | #21 (remaining) |
| S4-7 | **Clearing a field actually clears it** | Distinguish "not sent" from "sent empty" for year/track/genre in single edit. Pre-fill the genre embedded in the file. Limit filename components by UTF-8 **bytes** (255), so long Arabic titles don't fail at move time. | #24 (remaining) |

Order: **S4-1 → S4-2 → S4-3**. These three are a data risk or a daily annoyance. S4-4/S4-5 are quick wins and can
be done anytime. S4-6/S4-7 come after S4-1, because they touch the same edit code.

Not scheduled: #17 cross-device card updates (single user, rarely two devices open), #12 keyboard and
screen-reader pass (phone-first), #19/#18 large-queue rendering and artwork caching (only if the queue grows).

---

## Track B — design pass with `/impeccable`

Run these in order, one PR per command, and review each on a 390px phone before the next. Each command
names its target so it stays in scope.

### 0. Give the design commands context (once)

```
/impeccable init
```
Writes `PRODUCT.md`: who uses this (one operator, phone, Arabic RTL), what it's for (Pinchflat → Navidrome
review), and the tone (calm, devotional content, no playful gimmicks). Every later command reads it.

```
/impeccable document
```
Writes `DESIGN.md` from the existing tokens in `style.css` (the dark navy palette, Cairo, spacing and radius
scales). This captures the *current* identity so later passes refine it instead of drifting.

### 1. Baseline

```
/impeccable critique the review queue and library on a 390px phone
```
Scored UX review. Use it to adjust the order below. Don't fix anything in this step.

### 2. Words before pixels

```
/impeccable clarify all Arabic UI copy: pick one term for metadata, human-readable errors with technical details tucked away, explain the artist match score, LTR isolation for paths
```
Covers the rest of #31. Pairs with the `ux-writing-arabic` skill. Copy changes height and layout, so do
this before any visual pass.

### 3. States and edge cases

```
/impeccable harden the review card, batch edit dialog, and rescan flow: loading, saving, saved, failed, empty, offline (SSE disconnected)
```
After S4-1/S4-2 the logic is right. This makes every state *look* distinct. Includes long Arabic titles,
5+ artists, and missing artwork.

### 4. Typography

```
/impeccable typeset: Cairo hierarchy for card title/artist/source, Arabic vs Latin numerals, mixed Arabic + Latin path fragments
```

### 5. Layout and rhythm

```
/impeccable layout the library pages (artists, albums, tracks, detail views) on phone and desktop
```
The review card already got its phone pass (S2-8). The library pages haven't.

### 6. Motion

```
/impeccable animate with purpose: card collapse-out after a successful confirm, new-item arrival from SSE, genre chip selection, confirm button saving→done, rescan progress. Add prefers-reduced-motion. Replace the 12 `transition: all` with specific properties. No layout-property animation (the selection-bar padding transition).
```
Covers #35. The motion should explain what happened: the file left the queue, a new file arrived, it saved.
It shouldn't decorate. Keep durations short (150–250ms). This is a tool you go through dozens of
cards in a row.

### 7. One small moment of delight

```
/impeccable delight, restrained: the empty queue ("all files reviewed") and the confirm-all summary
```
Only these two moments. Calm, fitting the content. No confetti.

### 8. Performance

```
/impeccable optimize first load and the queue on a phone: font loading (self-hosted Cairo subset vs Google Fonts), image sizes, DOM work on SSE updates
```

### 9. Verify and finish

```
/impeccable audit
/impeccable polish
```
`audit` re-scores accessibility, performance and responsiveness against the original findings. `polish` is the
last pass: spacing, alignment and consistency. Always last.

### Deliberately skipped

- `bolder`, `overdrive`, `colorize`: the palette works, and contrast was fixed in S2-8. Louder would hurt a review tool.
- `quieter`, `distill`: the UI isn't noisy. Revisit only if `critique` says otherwise.
- `shape`, `onboard`: no new surfaces planned. A one-person tool needs no onboarding.
- `live`: useful later for trying variants of one element in the browser, once the above has landed.

---

## Working rules

Same as before: one ticket = one branch = one PR, a failing test first for Track A, CI must pass
(`pytest` + `node --check`). Track B PRs include before/after screenshots at 390px and 1440px.

## Progress

- [x] S4-1 batch edit keep/set/clear
- [x] S4-2 rescan progress and recovery
- [x] S4-3 visible, selectable album artist + destination preview
- [x] S4-4 Telegram disable/disconnect
- [ ] S4-5 favicon
- [ ] S4-6 detail-view refresh
- [ ] S4-7 clear-field semantics, byte-safe filenames
- [ ] B0 init + document · B1 critique · B2 clarify · B3 harden · B4 typeset · B5 layout · B6 animate · B7 delight · B8 optimize · B9 audit + polish
