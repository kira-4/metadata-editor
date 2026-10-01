# Sprint 4 handoff

**Date:** 2026-09-30 · **Plan:** [SPRINT_4_PLAN.md](SPRINT_4_PLAN.md) · **Status:** Sprint 4 is **complete**. Tracks A and B (B0–B9) are merged. The closing critique scored **28/40** (B1: 24/40). Its follow-ups are under Next.

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

- **B5, layout** (#51 queue, #52 library):
  - **Queue:** needs-review/error cards sort last (`sortQueue`, stable; SSE arrivals go to the top of their group). On phones a complete scanner suggestion (`pending` + title + artist + genre) collapses to a `.card-summary` (title; artists · genre; destination path mirrored from the dry-run) plus the real confirm button. Tapping it opens the card for good (`expandedCards`). The sticky `#readyBar` («N من M جاهزة» + confirm-all) replaces the toolbar's confirm-all on phones. `confirmAllRunning` keeps the per-card re-renders from resetting its running state. The folder select is 44px.
  - **Library:** the page header (title, stats line, select/rescan) and the variants notice scroll away. Only `.library-controls` (four equal tabs, search + sort on one row) is sticky, about 127px, at ≤768px. Content now starts at 424px on a 390px phone (was about 595px). The «الفرز» disclosure and `updateMobileFilterControls` are gone. «جميع الصوتيات» is now «الصوتيات».
  - **Selection:** `setMultiSelectButton()` keeps «تحديد متعدد» as a pressed toggle with a fixed label. The bar's «إنهاء التحديد» is the labelled exit. In selection mode phone cards drop their action row (the card is the toggle) and the ✓ glyph is gone (the checkbox shows state).
  - **Counts:** stats, list meta, variant counts and the selection bar use `arabicCount` (`ARTIST_FORMS`, `ALBUM_FORMS` added). The selection bar reads «المحدد: صوتيتان», nominative so every form is correct.
  - The dead single-artist library combobox (about 290 lines JS + CSS) was removed. Its markup went in a8287fd when the batch artist field became `;`-separated.

- **B6, animate** (#54):
  - **The fadeIn replay bug is fixed.** `confirmItem()` and `deleteItem()` no longer rebuild the list. They call `removeItemCardFromDOM()`, the same path as SSE. It is safe to call twice, because the SSE event often lands before the fetch response. It also clears `albumArtistChoice`/`shownAlbumArtist` now.
  - **Exit:** the card plays `card-leave` (200ms). A timer (`CARD_EXIT_MS`; hidden pages run no animations) then calls `removeCardAndCloseGap()`, which FLIPs the later cards into the gap with WAAPI (240ms). The empty state waits until the last card has gone.
  - **Arrival:** `.item-card` has no default animation. `smartUpdatePendingList` adds `.card-arriving`: a fade-up plus a Signal Blue border that settles over 1.2s. The class is dropped on `animationend`. The first load (`renderItems`) never animates.
  - **Ready count:** `READY_CONFIRM_SELECTOR` skips leaving cards. `updatePendingCountUI()` now refreshes the confirm-all button and ready bar.
  - **Expand:** `.card-expanding` fades the fields in (no height animation).
  - **CSS:** motion tokens (`--dur-fast/base/enter`, `--ease-out/in`). All 11 `transition: all` now name their properties. Hover lifts, glows and the card's hover top bar are gone (filled buttons brighten instead). The `#libraryPage` padding transition is gone. There is one `prefers-reduced-motion` block: fades stay; translate, FLIP, sweep and spin go. The detector went from 17 to 15 (`layout-transition`, `side-tab` cleared).
  - `DESIGN.md` gained a **Motion** section (tokens, the four moments, three named rules) and an updated Elevation note.

- **B7, delight** (#55): only the two planned moments, both reporting real outcomes.
  - **Empty queue:** `showEmptyState()` (used by `renderItems` and `updatePendingCountUI`) has two states. **Idle**: «لا ملفات في الانتظار», an inline SVG tray in muted grey (it replaced the 📂). **Cleared** (`.is-cleared`, once `confirmedFolders` is non-empty): «اكتملت المراجعة», how many files went to the library since the page was opened, an «افتح المكتبة» link, and a Settled Teal check in the tray. When the last card's exit finishes, the state fades in and the check draws once (`.is-arriving`, removed after 600ms). It does not replay on route changes. Under reduced motion: fade only. `role="status"`.
  - **Confirm-all summary:** `describeFolders()` names the destination folders: «نُقل 3 ملفات إلى «هيئة الزهراء» و«قناة المواليد».» It shows one folder as «إلى مجلد «…»», 4+ as a count (`FOLDER_FORMS_GENITIVE`, since it follows «إلى»). The alert stays 8s. A single confirm names its folder too. `confirmItem` reads `new_path` from the confirm response (`{album artist}/{title}/{file}`) into `confirmedFolders`. No backend change.

- **B8, optimize** (#56). Measured cold, Slow 4G, 390px, `main` against the branch: **295 → 118 KB** transferred, **FCP 866 → 676 ms**, **3 → 1** hosts.
  - **Cairo self-hosted** (decision: yes). The files are Google's own v31 variable subsets, byte for byte: `fonts/cairo-arabic-v31.woff2` (30 KB, preloaded) and `cairo-latin-v31.woff2` (33 KB, loads only for Latin text). Subsetting further wouldn't save much. What we gain is that the render-blocking third-party stylesheet is gone and no request reaches Google. `OFL.txt` sits next to them. The `/fonts/*.woff2` files get `Cache-Control: immutable`, and everything else is still `no-cache` + ETag.
  - **Gzip:** `GZipExceptStreams` in `main.py` (app.js 152 → 36 KB, style.css 55 → 11 KB, and JSON lists). It skips `/api/events`, because gzip buffers SSE; artwork; and woff2/png/jpg.
  - **Artist rows:** add/remove used to replace the whole card with `outerHTML`. That dropped the status line, the destination preview and typed custom genre, and **left confirm disabled** (no `updateConfirmButton`). Now `renderArtistRows()` rebuilds only `.multi-artist-list` (`renderArtistRowsHtml`, `attachArtistRowListeners`), calls `updateConfirmButton`, and keeps focus on the new or neighbouring row.
  - **Combobox state** is keyed by row id (`"12_artist_0"`), but `cleanupArtistState` compared those keys with item ids, so every cleanup wiped all of it. That's fixed. `closeArtistDropdown` no longer recreates state for a removed row.
  - Tests: `test_static.py` adds gzip, gzip exclusions (a wrapped dummy app) and self-hosted font + cache headers → **164 passed**.
  - Measuring scripts: `.playwright-mcp/b8measure.cjs` (CDP throttling, two servers: `main` in a `git worktree` on :8092 and the branch on :8091) and `b8rows.cjs`.

- **B9, audit + polish** (#57):
  - **Solid fills everywhere.** Primary, confirm, confirm-all, the selected chip, the active nav and both artwork placeholders are solid. The only gradients left are the brand mark and the saving sweep.
  - **Brand:** the app icon (`apple-touch-icon.png`, 180px source shown at 2rem) and a Parchment title replace 🎵 and the gradient text.
  - **Icons:** an inline SVG (`.btn-icon`) replaces 🔄 on rescan. The loading lines no longer use the emoji and read «جارٍ التحميل…».
  - **Flat-At-Rest:** the settings card and nav badge lost their shadows. Only the dropdowns, modal, selection bar and sticky library controls keep one.
  - **Tokens:** signal washes and edges (`--accent/success/warning/error-wash`, `-edge`, `--accent-tint`, `--error-tint`), `--shadow-dropdown/overlay`, `--scrim`, `--glint`, `--sweep-light`, and radii `--radius-xs` and `--radius-pill` (added to the DESIGN.md frontmatter). The detector reports **0** findings (17 at the start of B6).
  - **Focus ring:** 0.35 alpha (0.1 was invisible on navy).
  - **Native controls:** `color-scheme: dark` makes the checkbox, select menus and scrollbars render dark.
  - **Settings headings** are neutral (blue means "you can act"). The rescan button contents are centred.
  - **Path fix:** `formatLibraryPath` keeps the dot outside the extension's LTR isolate. «مولد الإمام عليm4a.» now reads «m4a.مولد الإمام علي».
  - The nav badge has an `aria-label` («N ملفات في الانتظار»).
  - **Critique:** run with two isolated agents. Snapshot: `.impeccable/critique/2026-10-01T06-52-12Z__app-static-index-html.md`. Agent A got three things wrong (it said the ready bar was at the top, that there was no reduced-motion handling, and that settings labels were English-only); the snapshot records the corrections.

### Behaviour changes worth knowing
- Changing the artist (in batch or single edit) no longer silently changes the album artist, which is the folder.
- A genre tag already embedded in a downloaded file is now preselected on its card.
- Delete needs two taps (no `confirm()`). Debug mode is toggled in Settings, not on the queue.

## Next (in order)

Sprint 4 is done. These come from the closing critique.

**Decided 2026-10-01 for the next round:**
- **Focus: review throughput.** Items 1, 2 and 5 first: the needs-review layout, removing the repeated title text, then focus on the next card and genre carry-over.
- **Tone: one signature detail.** Add a single recognisable element within the Night Archive rules: no religious ornament, no gradients on controls, calm. Pick it during `/impeccable shape` or `bolder` (restrained), not by decorating.

1. ~~**[P1] Needs-review card layout**~~ **done** (`feature/needs-review-layout`): three seam-separated groups (name, الوجهة, النوع); checks beside each label; remembered genre first (`metadataEditor.genreMemory`: `last` + `byChannel`, written on a successful single confirm, which confirm-all uses too). Check script: `.playwright-mcp/l1check.cjs`.
2. **[P1] Redundant text** (`/impeccable distill`): a long title appears in the title, the source line and the destination path. Show the source once (inside «التفاصيل التقنية»). Shorten the path to folder + file.
3. **[P2] Delete under confirm** (`/impeccable harden`): demote it to a text action with space from confirm, or use an undo toast (deletes already go to trash).
4. **[P2] Dead disabled confirm** (`/impeccable clarify`): a tap should focus the first missing field.
5. **[P2] Throughput for 50-card sessions:** move focus to the next card after confirm, carry the genre over, and deep-link from the Telegram ping to its card.
6. **[P3]:** explain ✓/○ and "ready" in the queue. Enlarge the «تعديل» chip. The token toggle is 36px tall (it sits inside the input).

### Known loose ends (not scheduled)
- Batch-edit artist suggestions: the batch artist field is a plain `;`-separated input with no suggestions. A combobox that completes the segment after the last `;` would help «one spelling per artist». This is a feature, not scheduled.
- `.impeccable/design.json` is stale relative to `DESIGN.md` (detector: `design-sidecar-stale`). `/impeccable document` refreshes it.

## How each step was run
1. `git checkout main && git pull`, then `git checkout -b feature/<step>`.
2. Load the Impeccable skill with the step's command (`/impeccable animate …`). Run `node ~/.claude/skills/impeccable/scripts/context.mjs --target app/static/style.css` once, then read that command's `reference/<cmd>.md` and `reference/craft-floor.md` before editing.
3. Edit, then do **one** batched browser check at 390×844 and 1280×900 (Playwright MCP), fix, and confirm once.
4. Detectors: `node ~/.claude/skills/impeccable/scripts/detect.mjs --json --scope <type|layout|…> app/static` (B4/B5 left `type` and `layout` clean). Then run `venv/bin/python -m pytest tests/ -q`.
5. Micro commits per concern (see the staging helper below). Push, `gh pr create --base main`, then `gh pr checks <n> --watch` (checks take about 10s to appear), then `gh pr merge <n> --squash --delete-branch`. Update this handoff and `DESIGN.md` in the step's last commit.

## Housekeeping
- **Python** is `venv/bin/python` (there is no bare `python` on PATH). `venv/bin/python -m pytest tests/ -q` → **161 passed** (B4/B5 were frontend and docs only). `node --check app/static/app.js` is a quick syntax check.
- **Scratch environment** (the scratchpad is per-session, so rebuild it). Set `S=<scratchpad>/env`, then:
  ```bash
  mkdir -p $S/{incoming,music,data}
  gen(){ ffmpeg -loglevel error -y -f lavfi -i "sine=frequency=440:duration=2" "$@"; }
  (cd $S/incoming
   gen "قصيدة يا حسين في ليلة العاشر من محرم الحرام بصوت حزين جدا مع جوقة كاملة وتوزيع جديد ومؤثرات خاصة لموسم هذا العام الحالي وما بعده من مواسم قادمة###قناة الأصوات.mp3"
   gen "لطمية جديدة 2026###هيئة الزهراء.mp3"; gen "مولد الإمام علي###قناة المواليد.m4a"; gen "دعاء كميل كامل.mp3")
  (cd $S/music; i=0; for a in الاكرف الأكرف "باسم الكربلائي" "باسم الكربلائي" الاكرف; do i=$((i+1)); mkdir -p "$a/t"
   gen -metadata title="صوتية $i" -metadata artist="$a" -metadata album_artist="$a" -metadata genre="لطميات" -metadata album="ألبوم $i" "$a/t/track$i.mp3"; done)
  ```
  Start the server **as a background task** (`run_in_background`; a `nohup … &` dies with the shell):
  `INCOMING_ROOT=$S/incoming NAVIDROME_ROOT=$S/music DATA_DIR=$S/data OPENROUTER_API_KEY= exec venv/bin/python -m uvicorn app.main:app --port 8091`.
  First run `pgrep -fl "port 8091"`. An older session's server may still hold the port and serve *its* data; `pkill -f "uvicorn app.main:app --port 8091"`.
  With no OpenRouter key every item is needs-review. To get **ready** cards (collapsed summary, ready bar), mark two as complete scanner suggestions:
  `sqlite3 $S/data/metadata_editor.db "update pending_items set status='pending', error_message=NULL, genre='لطميات' where id in (3,4);"`
  Run `curl -X POST localhost:8091/api/library/rescan` to index the library (the الاكرف / الأكرف pair triggers the variants notice). Confirm-all really moves files, so regenerate the env if you need ready cards again.
- **Scratch location:** the session scratchpad can disappear mid-session. B7 built the env under `.playwright-mcp/env` (untracked, inside the repo); `S=$PWD/.playwright-mcp/env` works with the recipe above.
- **Playwright MCP locked:** if the MCP says "Browser is already in use for …mcp-chrome-…", another session's `playwright-mcp` owns the profile. Don't kill it. Run a standalone script with its own Chrome instead: `require('/Users/akbaralhashim/.npm/_npx/9833c18b2d85bc59/node_modules/playwright')`, `chromium.launch({channel: 'chrome'})`, `newPage({viewport, reducedMotion})`. B7's checks were `.playwright-mcp/b7check.cjs` and `b7rm.cjs`.
- **Browser:** changing only the `#/route` doesn't reload the page, so call `location.reload()` after editing static files (the server sends `no-cache`). Screenshots go to `.playwright-mcp/` (untracked; the MCP only writes inside the repo). Don't commit it. Debug mode may be on in that browser's `localStorage`, which shows «معاينة دون كتابة» on cards. A synthetic `keydown` dispatched on `document` throws in `handleLibraryNav` (`event.target.closest`). That's a test artefact, since real keys target an element.
- **Shell:** `ls` is aliased to eza and rejects some args, so use `/bin/ls`. BSD `sed -i ''`.
- **Micro commits:** per concern, squash-merged per step. For `app.js`/`style.css`, where one file holds several concerns, stage hunks by regex with this helper (save it to the scratchpad):
  ```python
  # stage.py FILE INCLUDE_REGEX [EXCLUDE_REGEX]  → stages the hunks of FILE that match
  import re, subprocess, sys
  f, pat = sys.argv[1], re.compile(sys.argv[2])
  neg = re.compile(sys.argv[3]) if len(sys.argv) > 3 else None
  diff = subprocess.run(['git','diff','-U3',f], capture_output=True, text=True).stdout
  head, *hunks = re.split(r'(?m)^(?=@@ )', diff)
  keep = [h for h in hunks if pat.search(h) and not (neg and neg.search(h))]
  print(f'{len(keep)}/{len(hunks)} hunks', file=sys.stderr)
  if keep: subprocess.run(['git','apply','--cached','--recount','-'], input=head+''.join(keep), text=True, check=True)
  ```
  Review with `git diff --cached` before each commit, since a hunk can carry a neighbour's change. A missed hunk can go in with `git commit --fixup=<sha>` + `GIT_SEQUENCE_EDITOR=: git rebase -i --autosquash --autostash <base>`.
- Untracked and not mine: `.claude/`, `docs/superpowers/`.
- An Impeccable skill update (v4.3.1) is available. The user chose "not now".
