# Sprint 4 handoff

**Date:** 2026-09-30 · **Plan:** [SPRINT_4_PLAN.md](SPRINT_4_PLAN.md) · **Paused at:** Track B, step B2 (clarify), partly done.

## Done

### Track A: fixes (all merged, CI green, checked at 390px)

| Ticket | PR | Result |
|---|---|---|
| S4-1 batch edit keep/set/clear | #37 | Fields default to *keep*. *Clear* is explicit (`clear_fields`). A live summary shows the change. Failed tracks stay selected. IDs are deduped and capped at 1000. Setting the artist no longer rewrites the album artist. |
| S4-2 rescan progress | #38 | The scan is reserved atomically, so only one runs. Status gets `started_at`/`finished_at`. A progress line, a retry after a failed poll, and resume after reload. A partial walk (unreadable folder) skips the missing-file cleanup. |
| S4-3 album artist | #39 | The card shows "المجلد:" (a picker when there are 2+ artists) and the RTL destination path from the server's draft dry-run. Confirm sends the album artist shown. |
| S4-4 Telegram | #40 | `enabled` flag (migrated), on/off switch, two-tap disconnect (`DELETE /api/settings/telegram`). The bot token is redacted from all error text. |
| S4-5 favicon | #41 | A 347 KB JPEG-named-.png is replaced by `favicon-32.png` (1.8 KB) and `apple-touch-icon.png` (8.9 KB). |
| S4-6 detail refresh | #42 | `refreshLibraryContext()` reloads the current artist, album, genre or list view after edits. It steps back if the view empties. Stale responses are dropped via `loadSeq`. |
| S4-7 clear + byte-safe names | #43 | Single edit: null/"" clears, omitted keeps, values are validated. Embedded genre is kept on import. Filename parts are capped at 255 UTF-8 bytes. |

Tests went from 123 to 161 (new: `test_batch_edit`, `test_rescan_status`, `test_album_artist_choice`, `test_telegram_settings`, `test_clear_semantics`, plus the icon test).

### Track B: design pass

- **B0** (#44): `PRODUCT.md` and `DESIGN.md` ("The Night Archive") were written, plus the `.impeccable/design.json` sidecar.
- **B1** (#45): a dual-agent critique scored **24/40**. The snapshot is in `.impeccable/critique/`. Decisions:
  - Keep the plan order.
  - Move debug tools into Settings.
  - Use solid fills, with confirm the only saturated element.
  - Include collapsed ready cards and a sticky "N ready" bar in B5.
- **B2** (this branch, `feature/clarify-copy`): **terminology only**.
  - "Metadata" is now **البيانات الوصفية** everywhere (the user's choice).
  - Queue items are **ملف**, library items are **صوتية**. `مقطع` is removed, and a `TRACK_FORMS` count helper is added.
  - Feminine verb agreement is fixed (ستُعدَّل).

### Behaviour changes worth knowing
- Changing the artist (in batch or single edit) no longer silently changes the album artist, which is the folder.
- A genre tag already embedded in a downloaded file is now preselected on its card.

## Next (in order)

1. **Finish B2, clarify** (copy only):
   - **Disabled confirm:** it says why, e.g. "أضف فنانًا للتأكيد" / "اختر النوع".
   - **Needs-review card:** it gets a short checklist instead of only blank fields. Explain the "Unknown" source.
   - **Server errors:** show a human Arabic line, with the technical detail in a folded `<details>`. Server errors are currently English ("File not found", "Track not found", "Failed to update file metadata"). Map them in `parseApiError` or return Arabic `detail` from the API.
   - **Artist match score:** say what it means.
   - **Settings labels:** "Bot Token", "Chat ID", "Topic ID" become Arabic labels, with the Latin name as a hint.
   - **Toolbar copy:** debug toolbar text such as "تفعيل وضع التصحيح" goes away with B3.
2. **B3, harden:**
   - Move the debug toolbar, logs and workflow strip into Settings.
   - Replace `confirm()` in `deleteItem` (app.js) with the two-tap armed button already used for Telegram disconnect.
   - Give saving, saved, failed, empty and offline (SSE disconnected) distinct looks.
   - Handle edge cases: long titles, 5+ artists, missing artwork.
3. **B4, typeset:**
   - Raise `#6b6b6b` hint and placeholder text to at least 4.5:1 on navy (it measured 3.0–3.2:1).
   - Fix the heading order (h1 → h3 in the log panel).
   - Check the Cairo hierarchy, and Arabic versus Latin numerals.
4. **B5, layout:**
   - Collapsed ready cards with a sticky "N ready" bar on phones. Sort needs-review cards last.
   - On the library page: the header currently takes about 330px. Make the tabs fit (they clip "جميع ال"), put search and sort on one row, and use one selection model.
   - Make the folder `<select>` 44px tall (currently 38px).
5. **B6, animate:**
   - Replace the 12 `transition: all` rules and add `prefers-reduced-motion`.
   - Remove the card hover lift and the gradient top bar.
   - Drop the `padding-bottom` transition on `#libraryPage`.
6. **B7, delight:** the empty queue and the confirm-all summary only.
7. **B8, optimize:** Cairo is loaded from Google Fonts (decide whether to self-host a subset), plus DOM work on SSE updates.
8. **B9, audit + polish:** flatten all gradients to solid colours (title, nav pill, buttons, chips, confirm), then re-run `/impeccable critique` and compare with 24/40.

## Housekeeping
- A local test server may still be running on port 8091 with scratch data in the session scratchpad. Stop it with `pkill -f "uvicorn app.main:app --port 8091"`.
- Untracked and not mine: `.claude/`, `docs/superpowers/`.
- An Impeccable skill update (v4.3.1) is available. The user chose "not now".
