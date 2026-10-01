# Sprint 4 handoff

**Date:** 2026-09-30 · **Plan:** [SPRINT_4_PLAN.md](SPRINT_4_PLAN.md) · **Paused at:** Track B, step **B5 (layout)**: not started. B0–B4 are merged.

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
- **B2, clarify** (#46 terminology, #47 the rest):
  - "Metadata" is **البيانات الوصفية**. Queue items are **ملف** (`FILE_FORMS`), library items are **صوتية** (`TRACK_FORMS`). Counts go through `arabicCount()`.
  - **Errors:**
    - `apiError()` / `humanizeServerDetail()` / `describeError()` / `showError()` in `app.js` turn server details (often English) into an Arabic line.
    - Known English strings are mapped in `SERVER_ERROR_TEXT`. The raw text is folded under «التفاصيل التقنية» (`fillAlert`).
    - A `TypeError` from `fetch` means "can't reach the server". The API itself is unchanged.
  - **Disabled confirm** says what is missing («أضف فنانًا واختر النوع») via `MISSING_FIELD_ACTIONS`.
  - **Needs-review card:** a reason from `ITEM_PROBLEMS` (matched on the scanner's `error_message` prefix) and a live checklist. The `Unknown` channel reads «اسم الملف … · القناة غير معروفة» (`formatItemSource`).
  - **Artist score:** «تشابه 87٪» (`formatArtistScore`). It is hidden when the query is empty and amber below `ARTIST_CREATE_THRESHOLD`.
  - **Settings:** Arabic labels with a Latin hint (`.field-latin`), and a text «إظهار/إخفاء» token toggle.
- **B3, harden** (#48):
  - Debug mode, the log viewer and the pipeline steps now live in **Settings → أدوات التشخيص**. Debug mode persists in `localStorage` (`metadataEditor.debug`, try/catch guarded). The queue toolbar is just refresh + confirm-all.
  - **No native dialogs:**
    - Delete uses `armTwoTap()`, which Telegram disconnect shares.
    - The dry-run preview renders inside the card.
  - **States:**
    - confirm `:disabled` (dashed, readable reason), `.is-saving` (sweep), `.is-failed` (red outline + «أعد محاولة النقل»)
    - field status `saving` → `success`, which fades after 3s (`setItemStatus(..., fadeAfter)`)
    - the edit dialog shows «جارٍ الحفظ…» and blocks a double submit
  - **Offline:** the `#connectionStatus` amber banner appears after a 3s grace when SSE drops. It has «أعد الاتصال» and reloads to catch up on reconnect. Silent polls no longer stack error alerts. Manual reconnect after `EventSource.CLOSED`.
  - **Edge cases:**
    - the card title is an auto-growing `<textarea class="title-input">` (Enter blocked; `autosizeTitle` skips hidden pages, and the route to pending re-measures)
    - 4+ artists show `.artist-hint`
    - broken artwork falls back to `♪` (capture-phase `error` listener)
    - list and album names wrap or clamp

- **B4, typeset** (#50):
  - `--text-muted` is `#959bb0` (≥5.1:1 on all four navies; was 2.67–3.54:1).
  - Every `font-size` is a role token: `--text-display` 1.5rem (1.25 at ≤600px, set once on `:root`), `--text-title` 1.0625, `--text-body` 1, `--text-label` 0.875, `--text-caption` 0.8125, `--text-micro` 0.6875 (nav badge only). Icon characters use `--glyph-sm/md/lg/xl`. The detector (`--scope type`) is clean.
  - The card title textarea is 600 at the title size. `.field-label` and `.genre-label` are one rule (label, 600, faded). `.source-text` lost its fake italic.
  - Settings page `h2`, Settings/modal `h3` and `#detailTitle` were on browser defaults; now on the ramp. The Settings heading is no longer accent-coloured, so it matches the other page headings.
  - `tabular-nums` on counts, badge, pagination, library stats, selection info, rescan status, variant count and similarity score.
  - Dead `.header`/`.subtitle` rules were removed. `DESIGN.md` records the ramp, the glyph scale and the No Fake Italic / Steady Digits rules.

### Behaviour changes worth knowing
- Changing the artist (in batch or single edit) no longer silently changes the album artist, which is the folder.
- A genre tag already embedded in a downloaded file is now preselected on its card.
- Delete needs two taps (no `confirm()`). Debug mode is toggled in Settings, not on the queue.

## Next (in order)

1. **B5, layout:**
   - Collapsed ready cards with a sticky "N ready" bar on phones. Sort needs-review cards last.
   - On the library page: the header takes about 330px. Make the tabs fit (they clip "جميع ال"), put search and sort on one row, and use one selection model. There are two «إلغاء التحديد» today: the `#multiSelectBtn` label and the selection bar.
   - Make the folder `<select>` 44px tall (currently 2.25rem).
   - Tabs are at the label size on phones now and still clip «جميع الصوتيات».
2. **B6, animate:**
   - Replace the ~12 `transition: all` rules and add `prefers-reduced-motion`. The new `.confirm-btn.is-saving` sweep animation must also stop under reduced motion.
   - Remove the card hover lift and the gradient top bar (`.item-card::before`).
   - Drop the `padding-bottom` transition on `#libraryPage`.
   - The `fadeIn` on `.item-card` replays on every render. Screenshots taken right after a load catch cards at partial opacity.
   - Card collapse-out after confirm, and new-card arrival from SSE.
3. **B7, delight:** the empty queue and the confirm-all summary only (it already uses `FILE_FORMS`).
4. **B8, optimize:** Cairo is loaded from Google Fonts (decide whether to self-host a subset). Also cut DOM work on SSE updates: `addArtistRow`/`removeArtistRow` re-render the whole card.
5. **B9, audit + polish:**
   - Flatten all gradients to solid colours: title, nav pill, buttons, chips, `.btn-confirm-all`, `.artwork-placeholder`, `.album-artwork`.
   - Replace the 🎵 in the nav brand.
   - Re-run `/impeccable critique` and compare with 24/40.

### Known loose ends (not scheduled)
- `setupLibraryArtistCombobox()` looks for `#libraryArtistDropdownToggle` / `#libraryEditArtistCombobox`, which don't exist in `index.html`, so the batch-edit artist field has no suggestions. It is dead code or a missing wrapper; decide during B5.
- `.impeccable/design.json` is stale relative to `DESIGN.md` (detector: `design-sidecar-stale`). `/impeccable document` refreshes it.

## Housekeeping
- **Scratch server:** `venv/bin/python -m uvicorn app.main:app --port 8091` with `INCOMING_ROOT`/`NAVIDROME_ROOT`/`DATA_DIR` set to the session scratchpad `…/scratchpad/env/{incoming,music,data}` and no OpenRouter key, so every queue item is needs-review. It has 4 queue files (one without `###`, and item 1 has 5 artists and a 150-character title) and 5 library tracks, including the الاكرف / الأكرف variant pair. Stop it with `pkill -f "uvicorn app.main:app --port 8091"`. The scratchpad is session-scoped, so regenerate the files with `ffmpeg -f lavfi -i sine=…` in a new session.
- Python is `venv/bin/python` (there is no bare `python` on PATH): `venv/bin/python -m pytest tests/ -q` → **161 passed** (B4 is CSS/docs only).
- Screenshots go to `.playwright-mcp/` (untracked; the Playwright MCP only writes inside the repo). Don't commit it.
- Micro commits per concern on each branch, squash-merged per step. A hunk-staging helper (`git apply --cached` on a filtered diff) made that practical for `app.js`.
- Untracked and not mine: `.claude/`, `docs/superpowers/`.
- An Impeccable skill update (v4.3.1) is available. The user chose "not now".
