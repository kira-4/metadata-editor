# Project inspection and development priorities

**Project:** محرر الأصوات الولائية — Pinchflat → metadata review → Navidrome  
**Inspection date:** September 30, 2026  
**Code baseline:** `6fd9783`  
**Main focus:** responsiveness, workflow speed, UX reliability, Arabic RTL layout, and UI mistakes.

## 1. Overall assessment

The project has a useful foundation: a lightweight vanilla JavaScript interface, a separate incoming-file scanner, SQLite indexing, Arabic artist matching, staging before confirmation, and metadata roundtrip tests. The best next investment is making the existing review-and-save workflow dependable and fast.

Several defects currently make the interface appear unreliable: confirmation can use an older title, bulk confirmation can report success when every transfer fails, library errors appear in a hidden page, and mobile navigation overflows. Two more urgent issues affect file safety and untrusted metadata rendering. Address those before expanding the feature set.

**Recommended first five work packages:**

1. Protect completed library files and safely render imported metadata: findings **01–02**.
2. Make saving, confirmation, and scanner failure recovery reliable: **03–04**, **09–11**.
3. Keep the server responsive during file operations: **05**, followed by **18–20**.
4. Repair mobile navigation and accessible interactions: **06**, **12–14**.
5. Make library browsing, counts, and album selection correct: **07–08**, **21**, **25**.

### Audit health score

These are inspection scores, not a certification or a production benchmark.

| Dimension | Score / 4 | Main evidence |
|---|---:|---|
| Accessibility | 1 | Clickable non-focusable library rows, unlabelled fields, modal focus gaps, insufficient contrast |
| Performance | 2 | Some debouncing and incremental updates exist; synchronous I/O blocks async endpoints, artwork is repeatedly extracted, queue rendering scales poorly |
| Responsive design | 1 | Mobile track cards exist, but the shared navigation overflows at 320px and 390px |
| Theming | 2 | Useful central tokens, but undefined token references and inaccessible foreground/background combinations |
| Implementation integrity | 1 | Save/confirm races, inconsistent identifiers, misleading success states, metadata/index divergence |
| **Total** | **7 / 20** | **Poor: substantial corrective work needed** |

**Implementation integrity verdict: fail for consistent behavior.** The product purpose and visual identity are recognizable, but the displayed state does not reliably match saved data or operation outcomes. Preserve the existing identity while correcting these behaviors.

**Backlog total:** 35 findings — 2 P0, 14 P1, 16 P2, and 3 P3 — plus 13 ranked feature ideas.

## 2. Scope, method, and limits

Reviewed all application areas: startup/configuration; pending and library APIs; database models/queries; incoming and library scanners; metadata reads/writes; moving files; OpenRouter inference; Telegram settings/notifications; HTML, CSS, and JavaScript; tests; Docker files; README; maintenance scripts; and the existing library-scan plan.

Verification performed:

| Check | Result |
|---|---|
| Existing suite: `venv/bin/python -m pytest tests/ -q` with temporary paths and blank inference credentials | **30 passed in 0.98s** |
| JavaScript syntax: `node --check app/static/app.js` | Passed |
| Shell syntax: `bash -n scripts/restructure_music.sh scripts/split_monawat.sh` | Passed |
| Installed environment: `venv/bin/python -m pip check` | No broken requirements; this does not establish that the environment exactly matches every pinned requirement |
| Headless Chrome interface checks | Pending, library, and settings at **1440, 768, 390, and 320 CSS pixels**; modal and editing checks |
| Isolated API checks | Real FastAPI routes with an in-memory SQLite database; no application lifespan/scanner startup |
| File-processing checks | Generated disposable MP3/FLAC files; mocked inference and notifications |
| Performance probes | Synthetic queue sizes, 3,500 database records, unchanged-file query counts, and a controlled event-loop blocking probe |
| Mechanical interface detector | Four warnings; manually assessed below |

The browser loaded the actual project HTML/CSS/JS with mocked API responses. External font requests were blocked, so layout measurements represent the supported fallback-font condition. Screenshots were inspected. Browser checks did not use the production database, move real music, call OpenRouter, or send Telegram messages. The existing `.claude/` and `docs/` working-tree content was preserved.

Not measured: production NAS throughput, real OpenRouter latency/cost, a live Navidrome refresh, a freshly built Docker container, screen-reader behavior on a physical device, or a full dependency vulnerability audit. Static risks are identified as such. The performance numbers below are local synthetic observations, not promises about production.

**Evidence labels:** **Reproduced** = observed with fixtures; **Code-confirmed** = directly established by implementation; **Risk** = a plausible consequence requiring deployment or fault testing; **Proposal** = product/design improvement.

### Measured evidence

| Probe | Observation | Interpretation |
|---|---|---|
| 390px viewport, all three pages | Document width **491px** | Shared navigation causes horizontal overflow |
| 320px viewport, all three pages | Document width **491px** | Reflow is also broken at the narrow accessibility reference width |
| 1440px and 768px fixtures | No document overflow | Preserve these working layouts while correcting narrow screens |
| Render 100 pending cards | **13ms**, **4,100 descendants** | Local script execution only; excludes full paint/network cost |
| Render 500 pending cards | **221ms**, **20,500 descendants** | A full refresh can consume a substantial main-thread interval |
| 100 unchanged library-file checks | **100 SQL statements** | Each unchanged file still incurs a database lookup; the probe repeated an existing file to isolate this cost |
| Artist aggregation, 3,500 synthetic tracks | **11.06ms median**, five runs | Not a current local emergency; repeated full aggregation is a scaling opportunity |
| Artist suggestion, same library / 700 distinct fixture artists | **12.65ms**, one call | Preserve debouncing; cache measured hot paths before considering a larger architecture |
| Mock 200ms synchronous Telegram operation inside its real async route | A 20ms timer fired after **206ms** | Direct evidence that synchronous route work holds the event loop |
| Type title → immediate Confirm, delay update response by 400ms | Confirmation observed **old title** | A real UI request-ordering defect, not just a theoretical race |
| Fail both simulated bulk confirmations | UI reported **2 files successfully moved** | Success accounting is incorrect |

## 3. Ranked development backlog

Rank is the recommended implementation order, balancing impact, frequency, and dependencies. Severity describes consequences rather than effort.

- **P0 — urgent:** file-loss or unsafe-input defect; address before wider use.
- **P1 — major:** incorrect results, blocked tasks, substantial UX friction, or accessibility failures.
- **P2 — improvement:** meaningful speed, usability, reliability, or maintenance work.
- **P3 — small adjustment:** polish after the core workflow is sound.

Effort is approximate engineering scope: **S** = hours to about one day; **M** = roughly two to four days; **L** = roughly one to two weeks. Estimates include focused verification, depend on implementation choices, and overlap where findings share a fix.

| Rank | Priority | Development area | Main benefit | Effort |
|---:|---|---|---|---|
| 01 | P0 | Restrict queue deletion to pending/staged files | Prevent library-file loss | S–M |
| 02 | P0 | Safely render all library metadata | Prevent markup injection; support ordinary punctuation | M |
| 03 | P1 | Unify draft state and make confirmation await saved changes | Save exactly what users see | M |
| 04 | P1 | Repair scanner failure recovery | Make manual review recoverable | S |
| 05 | P1 | Remove blocking work from the server event loop | Keep every screen responsive during writes | M–L |
| 06 | P1 | Fix shared mobile navigation and reflow | Make the application usable on phones | S–M |
| 07 | P1 | Sort/filter/count before pagination | Correct search results and page order | M |
| 08 | P1 | Give albums a stable identity | Prevent editing tracks from the wrong album | M |
| 09 | P1 | Verify temporary files before replacement | Preserve original data on failure | M |
| 10 | P1 | Separate indexing from metadata repair | Make rescan predictable and index data truthful | M |
| 11 | P1 | Report operation outcomes accurately | Eliminate false success and support retry | S–M |
| 12 | P1 | Complete keyboard, form, and dialog accessibility | Enable reliable non-pointer operation | M |
| 13 | P1 | Correct contrast in active controls and supporting text | Improve readability and state recognition | S |
| 14 | P1 | Show feedback in the active page and expose empty states | Explain failure, success, and zero results | S |
| 15 | P1 | Define and enforce the network access boundary | Protect unauthenticated write operations | M |
| 16 | P1 | Wait for complete downloads and provide restaging/retry | Avoid incomplete imports becoming stuck | M |
| 17 | P2 | Reconcile live updates without losing edits | Keep tabs and queue state consistent | M |
| 18 | P2 | Cache and resize artwork | Reduce disk, network, and decoding work | M |
| 19 | P2 | Bound queue rendering and reduce DOM work | Keep large queues fast | M |
| 20 | P2 | Decouple discovery, inference, and notifications | Make new arrivals appear sooner | M–L |
| 21 | P2 | Refresh the correct library context after changes | Preserve location and show current tracks | M |
| 22 | P2 | Reduce scan and aggregation database work | Improve large-library performance | M |
| 23 | P2 | Make rescan status and reconciliation recoverable | Remove opaque spinners and stale records | M |
| 24 | P2 | Clarify metadata preservation, clearing, and validation | Prevent surprising edits and failed moves | M |
| 25 | P2 | Correct artist counts and album artwork selection | Make browsing trustworthy | S |
| 26 | P2 | Make artwork behavior consistent across formats | Fix OGG gaps and repeated FLAC covers | M |
| 27 | P2 | Make batch changes explicit and reviewable | Reduce accidental mass edits | M |
| 28 | P2 | Repair deployment health checks and setup documentation | Make installation and diagnosis dependable | S–M |
| 29 | P2 | Add regression coverage around real user workflows | Keep fixes from regressing | M |
| 30 | P2 | Reduce review-card height and improve touch controls | Review more files with less scrolling | S–M |
| 31 | P2 | Clarify Arabic labels, states, and album-artist selection | Reduce guessing and inconsistent terminology | S–M |
| 32 | P2 | Add a clear notification off/disconnect path | Let users control Telegram settings | S |
| 33 | P3 | Repair undefined theme tokens and font inconsistency | Restore visual consistency | S |
| 34 | P3 | Trim static assets and manage the Arabic font | Improve first visit and offline resilience | S |
| 35 | P3 | Respect reduced motion and simplify decorative transitions | Improve comfort and finish | S |

## 4. Detailed findings

### 01. [P0] A queue delete request can remove a completed library file

**Category:** file safety / workflow integrity. **Evidence: reproduced.**

**Location:** [api.py](../app/api.py), `delete_item`, line 402; [database.py](../app/database.py), `mark_as_done`, line 332.

Deletion accepts any item ID without checking its status. Confirmation retains the row, sets it to `done`, and changes `current_path` to the final library path. A subsequent delete therefore unlinks the library file. An isolated `done` fixture returned HTTP 200 and its disposable library file disappeared. A stale page or delayed request can reach this path even though completed items are absent from the normal queue.

**Recommended change:** enforce allowed states; resolve and validate paths against their intended roots; never treat a completed destination as staging. Make destructive transitions atomic. Handle missing items with 404 rather than converting the exception to 500. Surface partial deletion failures instead of deleting the record and reporting success unconditionally.

**Acceptance:** deleting a completed item is rejected and leaves its destination untouched; stale repeated requests are safe; failed filesystem cleanup remains visible and recoverable.

### 02. [P0] Imported library metadata is inserted directly into HTML

**Category:** safe rendering / UI correctness. **Evidence: reproduced markup injection; code-confirmed script-injection risk.**

**Location:** [app.js](../app/static/app.js), `renderArtists` 2260, `renderAlbums` 2279, `renderGenres` 2302, track renderers 2320/2341, and artist detail rendering 2481.

Artist names, albums, genres, and track titles are interpolated into `innerHTML` without the escaping already used by pending cards. A harmless `<span id="audit-marker">…</span>` fixture became a DOM element. Inline click handlers also break on ordinary names: `O'Connor` generated `viewArtistAlbums('O'Connor')`. `encodeURIComponent` does not make a value safe inside a JavaScript string embedded in HTML.

**Recommended change:** create text nodes or consistently escape HTML text, attach event listeners rather than generating inline JavaScript, and look up tracks by ID instead of embedding serialized records in attributes. Imported tags should be treated as data at every rendering boundary.

**Acceptance:** tags containing `<`, `>`, `&`, quotes, Arabic punctuation, and apostrophes display literally and remain clickable; imported values cannot create elements or handlers. No executing payload was needed for this audit.

### 03. [P1] Confirmation can save an older title; artist draft IDs are inconsistent

**Category:** editing UX / data correctness. **Evidence: reproduced.**

**Location:** [app.js](../app/static/app.js), `captureFocusSnapshot` 189, `getItemIdFromRowId` 646, `rebuildArtistValue` 652, `setupArtistInput` 1008, `updateField` 1256, `confirmItem` 1362.

Title/artist edits save on blur. Confirmation immediately requests a dry run and then confirms the server's existing values; it does not await the outstanding save or submit the current form values. With a 400ms update delay, the observed order was **update started → dry run → confirm old title → update completed**.

Artist row IDs produce string item IDs, while queue records and several maps use numbers. Typing an artist populated the string-keyed draft but did not update the numeric record. Focus capture reads `data-id`, although artist inputs have `data-item-id`; it produced `NaN`. Full rendering and cleanup can consequently lose the artist draft/focus. String IDs also affect bulk-confirm/delete local filtering.

**Recommended change:** normalize IDs once; use one draft model per item; track saving/error/dirty state; serialize or version saves; disable confirmation until the latest draft is saved, or atomically submit the reviewed metadata with confirmation. Do not clear a newer draft when an older response returns. Preserve all artist rows and custom genre drafts.

**Acceptance:** type and immediately confirm on a slow connection, edit two artist rows, refresh while typing, and confirm another card. The destination tags must match the visible draft and focus must remain sensible. A failed save must prevent confirmation.

### 04. [P1] A scanner failure leaves a review item pointing at a deleted staged file

**Category:** recovery / task completion. **Evidence: reproduced.**

**Location:** [scanner.py](../app/scanner.py), duplicated `if not success` blocks near lines 291–333; exception cleanup near 359–388.

When the initial metadata write fails, the first branch creates a manual-review record. The duplicated branch references undefined `artist` instead of `artists`, raising `NameError`. The exception handler then deletes the staging directory. The resulting fixture stayed `needs_manual`, but its staged path no longer existed; the incoming original still existed. Duplicate checks prevent straightforward rediscovery.

**Recommended change:** consolidate the failure branch and return after creating a recoverable item. Preserve any staged file referenced by a queue row, or explicitly mark it for restaging and implement that operation. Apply the same invariant to other exception paths.

**Acceptance:** an injected write failure produces one visible item with an existing recoverable source and a working retry/manual-edit path.

### 05. [P1] File operations and synchronous HTTP block async routes

**Category:** performance. **Evidence: code-confirmed; controlled blocking reproduced.**

**Location:** [api.py](../app/api.py), `confirm_item` 242; [library_api.py](../app/library_api.py), update 213, batch update 272, artwork 362/416; [settings_api.py](../app/settings_api.py), test 96.

These `async def` routes directly perform synchronous SQLAlchemy queries, Mutagen reads/writes, whole-file copies/moves, or synchronous Telegram HTTP. Large audio files and batches can therefore delay unrelated requests and SSE delivery. The mocked 200ms Telegram call delayed a 20ms event-loop timer to 206ms.

**Recommended change:** run complete blocking operations in bounded workers, with database sessions owned by those workers. Keep async streaming/event delivery on its event loop. Use a background job with progress for lengthy batches. Add per-file mutation coordination and bounded concurrency before allowing overlapping writes; blindly increasing workers introduces new file races. FastAPI documents the distinction between synchronous route execution and directly called blocking helpers. [FastAPI concurrency guidance](https://fastapi.tiangolo.com/async/)

**Acceptance:** pending lists, search, and status requests remain responsive during a representative large-file write and batch operation. Measure p95 latency and event-loop delay, not only individual request duration.

### 06. [P1] The shared navigation overflows on phones

**Category:** responsive design. **Evidence: reproduced and visually inspected.**

**Location:** [style.css](../app/static/style.css), `.container` 53, `.main-nav` 741, `.nav-links` 761.

The navigation stays in one flex row with large padding and no narrow-screen arrangement. At both 390px and 320px, the document expanded to 491px. Settings/navigation controls spill outside their panel, while the brand wraps into a narrow column. The overflow affects pending, library, and settings.

**Recommended change:** stack or deliberately wrap the brand and navigation at a suitable breakpoint; reduce outer gutters on phones; use flexible/minimum-zero child widths; keep labels readable. Preserve internal horizontal scrolling for the library's tab strip where useful, but eliminate document-level overflow. [W3C reflow guidance](https://www.w3.org/WAI/WCAG22/Understanding/reflow.html)

**Acceptance:** no document horizontal scroll at 320, 360, 390, 768, and 1440px, with long Arabic labels and text enlargement. Every navigation action stays visible and operable.

### 07. [P1] Sorting and totals are wrong across library pages

**Category:** browsing UX / query correctness. **Evidence: reproduced.**

**Location:** [library_api.py](../app/library_api.py), `get_tracks` 144; [database.py](../app/database.py), `get_tracks` 697; [app.js](../app/static/app.js), `updateSortOptions` 2222.

The database applies its default ordering and limit/offset before the route sorts the returned page in Python. A title-ascending, one-item page returned **Zulu**, although **Alpha** existed. A filter matching one of three tracks returned one row but `total: 3`, causing misleading page counts and potentially empty later pages. Switching tabs can also leave `currentSort` set to an option the new tab does not support.

**Recommended change:** use a validated sort mapping in SQL before pagination, add a stable ID tiebreaker, and count using the same filters. Reset invalid sort selections on tab change. Require positive bounded limits and nonnegative offsets; `limit=-1` currently succeeds and removes SQLite's limit.

**Acceptance:** results across all pages equal a fully filtered/sorted reference list, including ties; zero-result searches show zero pages; the visible sort choice matches the request.

### 08. [P1] Different albums with the same name are mixed together

**Category:** data selection / batch-edit safety. **Evidence: reproduced.**

**Location:** [database.py](../app/database.py), album grouping 630 and track filtering 697; [app.js](../app/static/app.js), `viewAlbumTracks` 2545.

Albums are listed by album name, album artist, and year, but clicking one requests tracks using only its name. Two fixtures named `Shared`, owned by different artists, returned both artists' tracks. This also changes what “select all album tracks” selects. Album and genre detail requests stop at 500 tracks without a continuation UI.

**Recommended change:** introduce an album ID or pass the full defined album identity through navigation and queries. Decide how different years/releases belong together. Paginate detail views and define whether selection means the current page or the complete matching album.

**Acceptance:** same-name albums remain distinct, drilling down from an artist preserves the artist context, and all matching tracks remain reachable beyond 500.

### 09. [P1] Metadata verification happens after the original is replaced

**Category:** file integrity / recovery. **Evidence: reproduced with a forced verification failure.**

**Location:** [metadata_processor.py](../app/metadata_processor.py), `update_metadata_safe` 462, replacement 571, verification 583; artwork replacement 668.

The temporary file is copied and edited, then replaces the original before roundtrip verification runs. An injected failed verification returned `False`, but the original file's title had already changed from `Before` to `After`. Callers can report failure and leave the database unchanged despite changed audio tags.

**Recommended change:** verify the temporary file before replacement; preserve a recoverable backup or operation journal where necessary. After replacement, update the database from the verified result. Define recovery if filesystem success is followed by database failure, including the confirm/move flow. Coordinate concurrent edits to the same file.

**Acceptance:** failed validation leaves original bytes/tags unchanged; simulated database failure after a successful move can be reconciled without duplicate files or an unretryable queue record.

### 10. [P1] Rescan silently edits files and can index tags it did not write

**Category:** workflow expectations / integrity. **Evidence: code-confirmed; FLAC divergence reproduced.**

**Location:** [library_scanner.py](../app/library_scanner.py), `_index_file` 169, `_write_metadata` 264, FLAC/OGG branch 345.

“Rescan” infers missing tags from folder names and writes them directly to the library. This is an unexpected mutation for an indexing action. Its separate writer uses `isinstance(audio.tags, dict)` for FLAC/OGG tags, which does not match the tested FLAC tag container. A generated FLAC received an inferred title in SQLite while the file title stayed absent. Write failures are logged rather than propagated, and inferred values are still indexed.

**Recommended change:** make indexing observational by default. Expose tag repair as a previewable action; reuse the verified metadata writer; reread the actual saved result before indexing. Distinguish inferred display values from persisted tags.

**Acceptance:** ordinary rescan leaves audio bytes unchanged. Explicit repair reports per-file results, and the indexed state matches a subsequent file read for all supported formats.

### 11. [P1] Bulk operations can report false or misleading success

**Category:** feedback / recovery. **Evidence: reproduced and code-confirmed.**

**Location:** [app.js](../app/static/app.js), `confirmAllReady` 1216, `confirmItem` 1362, `handleBatchEdit` 2924, `handleSingleEdit` 2872.

`confirmItem` catches errors without returning a failure outcome or throwing. Its caller increments success after every resolved call. Both fixture transfers failed, yet the banner reported two successful moves. Library batch edit always uses success styling, closes the modal, and clears selection even when some tracks fail. A failed artwork upload can also be followed by successful metadata saving without a clear combined result.

**Recommended change:** return explicit outcomes; count only completed operations; retain failed selections/drafts; show failed items and reasons; offer retry-failed. Disable duplicate submissions and present progress for long batches. Distinguish partial success from complete success.

**Acceptance:** all-failure, partial-success, early-validation, and all-success cases produce accurate counts and preserve the information needed to retry.

### 12. [P1] Core library actions and the editor dialog are not fully keyboard accessible

**Category:** accessibility. **Evidence: code-confirmed and browser-inspected.**

**Location:** [index.html](../app/static/index.html), search/sort and modal near line 250; [app.js](../app/static/app.js), library renderers 2260–2383, `showEditModal` 2706, `closeEditModal` 2853.

Library artist/album/genre cards and desktop track rows are clickable `div`s without keyboard semantics. The modal lacks dialog semantics, initial focus, a contained tab sequence, and restored focus. Browser inspection found focus outside the opened modal and no associated label for `batchTitle`. Pending labels are likewise not connected to inputs. Genre buttons expose selection only through CSS; autocomplete lacks an active-descendant relationship; status messages are not live regions.

**Recommended change:** use links/buttons for actions, connect labels and help text, implement a native or correctly managed dialog, add accessible selected/current states, and announce relevant status changes. Preserve the existing Escape support. [W3C modal pattern](https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/)

**Acceptance:** browse, select, edit, save, and cancel using only the keyboard; focus never disappears behind the modal; a screen reader can identify field labels and current states. Relevant checks include WCAG keyboard, labels/relationships, focus order, name/role/value, and status messages.

### 13. [P1] Active buttons and muted text have insufficient contrast

**Category:** visual accessibility. **Evidence: calculated from actual CSS colors.**

**Location:** [style.css](../app/static/style.css), `.source-text` 400, selected genres 443, confirm controls 475/508, error badge 535, active navigation 781, primary buttons 1121, hints 1320.

| Foreground/background | Contrast |
|---|---:|
| White on blue gradient endpoints `#4a9eff` / `#6bb1ff` | 2.75:1 / 2.24:1 |
| White on green gradient endpoints `#00d4aa` / `#00b894` | 1.91:1 / 2.54:1 |
| Muted `#6b6b6b` on card `#1a1a2e` | 3.20:1 |
| Muted `#6b6b6b` on page `#0f0f23` | 3.54:1 |
| White on error red `#ff5757` | 3.11:1 |

These controls and supporting text are generally normal-sized text, for which 4.5:1 is the usual AA requirement. The green and blue controls fail even the 3:1 large-text threshold. [W3C contrast guidance](https://www.w3.org/WAI/WCAG21/Understanding/contrast-minimum)

**Recommended change:** use dark text on the bright fills or darken the fills; raise muted-text contrast; verify gradient interiors as well as endpoints. Preserve a clear selected state beyond color alone.

**Acceptance:** all enabled control labels, hints, source text, and error badges meet the applicable ratio in their actual states. Disabled controls should remain understandable even where contrast exceptions apply.

### 14. [P1] Library alerts are hidden, and several empty states never appear

**Category:** feedback / empty states. **Evidence: reproduced.**

**Location:** [index.html](../app/static/index.html), `globalAlert` within `pendingPage`; [app.js](../app/static/app.js), `showAlert` 83, renderers 2260–2319; [style.css](../app/static/style.css), `.empty-state` 596.

Library save/error handlers call `showAlert`, but its element belongs to the hidden pending page. Browser inspection confirmed it had `display: block` yet was not visible. Empty artists/albums/genres clear their containers without showing the adjacent empty-state element, whose default display is none.

**Recommended change:** provide page-level or shared visible feedback, modal-local errors, and explicit loading/empty/error states. Keep actionable errors until resolved or dismissed; distinguish an unindexed library from a search with no matches.

**Acceptance:** failures are visible where they occur; an empty library offers “scan library”; a zero-result query offers clear-search; successful saves are visible on the current page.

### 15. [P1] Write APIs have no application access control

**Category:** deployment/access integrity. **Evidence: code-confirmed; actual external reachability not assessed.**

**Location:** [main.py](../app/main.py), CORS configuration near 54; [docker-compose.yml](../docker-compose.yml), port publishing; pending, library, and settings routes.

The application exposes file mutation, deletion, artwork upload, and Telegram settings/test endpoints without authentication. CORS permits every origin, and Compose publishes port 8090 without a loopback-only binding. Any caller able to reach the service can use these operations. The severity in a specific installation depends on network isolation and proxy protection.

**Recommended change:** choose and document the intended boundary: loopback/protected private service, authenticated reverse proxy, or application authentication. Restrict browser origins appropriately. If cookie authentication is introduced, include its corresponding request-forgery protections. Keep this lightweight for the actual deployment model.

**Acceptance:** unauthorized callers cannot mutate files/settings, and the supported access path continues to work with SSE and uploads.

### 16. [P1] Incoming files are copied before their download completeness is established

**Category:** import integrity / recovery. **Evidence: code-confirmed risk; not reproduced against a live downloader.**

**Location:** [scanner.py](../app/scanner.py), discovery 133, copy 189, duplicate checks 169–178; [database.py](../app/database.py), `file_already_processed` 347.

Any matching audio extension can be discovered and copied immediately. There is no stable-size/mtime check or completion signal. If a downloader exposes the final extension while still writing, a partial copy can be queued. Path-based deduplication then suppresses a later complete version at the same path. The “stable across renames” comment also contradicts an identifier that hashes the path itself.

**Recommended change:** use the downloader's completion signal where available, otherwise require stable file observations and successful media parsing before staging. Track source revisions and add an explicit restage/retry action. Keep source identity distinct from content-duplicate detection.

**Acceptance:** a fixture that grows over time is processed only when ready; retry can recover a failed import without deleting its record or source manually.

### 17. [P2] Live queue updates do not actually reconcile existing cards

**Category:** perceived speed / state consistency. **Evidence: reproduced and code-confirmed.**

**Location:** [app.js](../app/static/app.js), polling 330, `smartUpdatePendingList` 395, SSE 1456; [api.py](../app/api.py), events 454; [scanner.py](../app/scanner.py), item creation.

Smart refresh only adds/removes cards. A fixture changed to `error` in memory, but no error badge appeared. `item_updated` events are ignored on the assumption that the change was local, so another browser's changes remain visually stale. The scanner never emits the `new_item` event the browser expects: arrivals depend on the 15-second poll after scanning/inference. Polls also continue on other pages and have no response-order protection. SSE has no heartbeat or bounded queue.

**Recommended change:** publish scanner results through an event-loop-safe bridge, update changed fields unless locally dirty, reconcile on reconnect, and guard against stale responses. Use visibility-aware fallback polling, a heartbeat, and bounded event queues. Refresh readiness counts after removals. Do not replace in-progress drafts.

**Acceptance:** two tabs stay consistent, reconnect catches missed changes, errors appear on existing cards, and background updates preserve typing and focus.

### 18. [P2] Artwork repeatedly triggers extraction and full-size transfer

**Category:** performance. **Evidence: code-confirmed.**

**Location:** [library_api.py](../app/library_api.py), `get_track_artwork` 416; [app.js](../app/static/app.js), artwork URLs 2291, 2507, 2745; pending image markup near 551.

Each library artwork request opens the audio file, extracts to a temporary file, reads it back, and returns full image bytes. URLs append `Date.now()`, defeating reuse across renders. Images do not use lazy loading. For large covers on network storage, this adds repeated disk, network, and image-decoding work.

**Recommended change:** cache extracted artwork by file identity/revision, generate display-sized thumbnails while retaining the original for embedding, serve cache validators, and replace timestamp cache busting with a version that changes only after an artwork update. Lazy-load offscreen covers and reserve dimensions. In confirmation, combine artwork/tag mutation into one verified copy where practical; currently the two safe-write helpers can copy the same large file twice.

**Acceptance:** revisiting an unchanged album does not re-extract its cover; one artwork update invalidates only that version; compare bytes transferred and disk reads on a representative album grid.

### 19. [P2] Large queues render every card and repeatedly scan the DOM

**Category:** frontend performance. **Evidence: measured and code-confirmed.**

**Location:** [api.py](../app/api.py), pending list 171; [app.js](../app/static/app.js), `renderItems` 477, `updateConfirmButton` 1188, `updateConfirmAllButton` 1207, confirmation 1362.

The pending endpoint and UI are unbounded. Rendering attaches handlers card by card, and each confirm-button update scans all ready buttons again. Successful confirmation calls `renderItems()` for the whole remaining queue, replaying animations and risking focus loss. The synthetic 500-card render took 221ms of script time and created 20,500 descendants; paint and image costs are additional.

**Recommended change:** introduce bounded pages or progressive rendering, update/remove only affected cards, delegate recurring events, and maintain ready counts in state. Preserve scroll/focus across changes. Prefer simple pagination initially; virtualization of editable forms requires careful draft handling.

**Acceptance:** a 500-item queue keeps interaction responsive and the mounted DOM bounded; confirming one item does not rebuild unaffected inputs. Validate on a throttled/mobile device before claiming a speed improvement.

### 20. [P2] Discovery waits behind sequential AI requests and notifications

**Category:** import throughput / perceived speed. **Evidence: code-confirmed.**

**Location:** [scanner.py](../app/scanner.py), `scan_loop` 392; [openrouter_client.py](../app/openrouter_client.py), `infer_metadata` 112; [telegram_notifier.py](../app/telegram_notifier.py), `send_message` 30.

One scanner thread processes each file end to end: copy, read, inference, write, database insert, and optional notification. The UI does not receive a record until late in that process. OpenRouter has a configured 60-second HTTP timeout; notification calls have a 10-second timeout. Later arrivals wait behind this serial work, and the scan interval begins after the batch completes.

**Recommended change:** promptly register discovered/staged items with an honest processing state; use a bounded inference queue and reusable HTTP client; move notifications to an independent bounded queue. Cache repeated inference by input/model/prompt version, handle missing credentials without a doomed request, and add bounded retry/backoff for transient failures.

**Acceptance:** newly discovered files become visible promptly even if an earlier inference stalls; worker concurrency respects service limits; restart/retry does not duplicate items. Do not infer AI accuracy from the fuzzy artist-match score.

### 21. [P2] Saved/imported tracks and library navigation become stale

**Category:** continuity / state correctness. **Evidence: code-confirmed.**

**Location:** [api.py](../app/api.py), successful confirmation 338 onward; [app.js](../app/static/app.js), router 1831, `loadViewData` 2086, detail functions 2481–2630, `handleSingleEdit` 2872.

Confirmation moves the file and completes the pending row without inserting it into `LibraryTrack`; users must rescan before it appears in this editor's library. The router can reuse cached library data. Saving from an album/genre detail calls the top-level `loadViewData`, whose query omits the active detail filter. Depending on `currentView`, it can update a hidden list or put unrelated tracks into the detail surface. Concurrent searches lack cancellation/request version checks.

**Recommended change:** upsert the final verified track after a move, invalidate relevant aggregates, and route every refresh through a single query/context model. Preserve detail identity, filters, page, selection, and scroll. Cancel or discard obsolete fetch results; reset pagination visibility when entering/leaving details.

**Acceptance:** a confirmed import appears without manual rescan; editing inside an album leaves the user in that album with current data; a slower old search cannot replace a newer result. Navidrome's own indexing schedule remains a separate integration concern.

### 22. [P2] Scans and artist/stat queries do avoidable database work

**Category:** backend performance. **Evidence: measured and code-confirmed.**

**Location:** [library_scanner.py](../app/library_scanner.py), `_index_file` 169; [database.py](../app/database.py), upsert 365, artist aggregation 512, suggestions 565; [library_api.py](../app/library_api.py), stats 494; [app.js](../app/static/app.js), `initLibrary` 1876.

Every unchanged-file check does a database query; changed tracks commit/refresh individually. Artist listing loads all relevant rows and splits artists in Python, stats repeats the aggregates, and artist suggestions regroup and normalize candidates per request. Initial library stats and its first data request are sequential. Artists/albums/genres use client pagination but refetch their full result sets on each page.

**Recommended change:** preload a compact path → mtime/size map, batch verified index updates, preserve per-file errors, cache aggregates/candidate keys with mutation-driven invalidation, and add server pagination for larger result sets. Fetch independent initial data concurrently. Evaluate WAL/busy-timeout behavior on the actual database storage before changing SQLite settings.

**Acceptance:** unchanged scans avoid one query per file; only changed files trigger tag reads; paging does not download the full collection repeatedly. Benchmark first—the 3,500-track local aggregation was only about 11ms, so this ranks below correctness and file I/O.

**Existing-plan caution:** the older scan plan proposes directory-mtime pruning. Do not adopt it as proof that descendant file contents are unchanged. Retain reliable per-file checks or filesystem events plus reconciliation; existing code appropriately still walks all directories.

### 23. [P2] Rescan progress, recovery, and missing-file handling are incomplete

**Category:** long-operation UX / library accuracy. **Evidence: code-confirmed.**

**Location:** [app.js](../app/static/app.js), `startRescan` 2974; [library_scanner.py](../app/library_scanner.py), start 33, scan 78, cleanup 470, status 493.

The API exposes processed/total/errors, but the UI shows only a spinner. Status polling lacks its own error/finalization handling, so a failed status request can leave the button disabled. Reload does not reconnect the screen to an active scan. Normal rescans do not remove missing records; the UI never requests `force=true`. Forced cleanup cannot distinguish deliberately removed files from unreadable subtrees, and an empty discovered set skips cleanup entirely. The scanning flag is set inside the new thread, leaving a start-request race.

**Recommended change:** atomically reserve scan state; show counts, completion time, and actionable failures; resume status observation after navigation/reload; recover from poll errors. Separate “refresh index” from a clearly explained missing-file reconciliation, and delete index rows only after a complete successful enumeration of the relevant root.

**Acceptance:** refresh/reload retains progress, network failure leaves a retry action, concurrent starts produce one scan, and an inaccessible directory never causes index deletion.

### 24. [P2] Metadata preservation, clearing, and validation are inconsistent

**Category:** form semantics / data integrity. **Evidence: code-confirmed.**

**Location:** [scanner.py](../app/scanner.py), initial metadata and pending creation near 280/337; [database.py](../app/database.py), `create_pending_item` 208; [library_api.py](../app/library_api.py), request models 23/35 and update 213; [app.js](../app/static/app.js), year payloads 2907/2949; [metadata_processor.py](../app/metadata_processor.py), filename sanitization 24.

The staged file can retain its embedded genre, but pending creation has no genre argument, so users must reselect it. Clearing year sends `null`, interpreted by the API as “leave unchanged.” Library fields lack the pending API's length checks; batch IDs are not bounded/deduplicated; negative year/track values are not consistently rejected. Filename sanitization does not limit UTF-8 component bytes, so a valid long Arabic title can still fail at move time. SQL search escaping is also inconsistent: LIKE patterns omit an explicit escape character, while Python artist substring search inserts SQL-style escapes.

**Recommended change:** define field operations explicitly—keep, set, clear—preserve useful imported tags in the review model, and centralize validation across single/batch/pending APIs. Validate generated filesystem components by byte length, retain full metadata titles, and use one literal-search convention. Keep raw and normalized search values separate.

**Acceptance:** embedded genre is visible, year can be cleared deliberately, invalid batch/number/text inputs produce useful field errors, and long Arabic titles plus `%`/`_` searches behave predictably.

### 25. [P2] Artist counts and album artwork references can be wrong

**Category:** browsing accuracy. **Evidence: count reproduced; artwork query code-confirmed.**

**Location:** [database.py](../app/database.py), `get_all_artists` 512, `get_all_albums` 630.

A track with the same artist and album artist is counted twice. The three-track fixture showed two tracks for each artist who had only one. Album counts also use album name alone within each artist. Artwork selection independently takes `max(has_artwork)` and `max(id)`, so the chosen sample ID need not have artwork even when another track does.

**Recommended change:** deduplicate each track's participating artists before incrementing counts, use the defined album identity, and choose a sample from tracks that actually have artwork.

**Acceptance:** one track counts once per artist; separate releases follow the chosen album identity; mixed-cover albums always reference an actual cover-bearing track.

### 26. [P2] Artwork support is inconsistent across formats

**Category:** media UX / storage efficiency. **Evidence: code-confirmed.**

**Location:** [metadata_processor.py](../app/metadata_processor.py), extraction 50, reads 159, embedding 600; [library_api.py](../app/library_api.py), upload 362; [scanner.py](../app/scanner.py), artwork cache near 199.

OGG metadata is supported, but artwork read/extract/embed paths do not implement its cover representation. FLAC uploads append pictures, while extraction selects the first; replacing a cover can keep showing the old image and grow the file. Artwork verification checks existence, not whether the new image was saved. Imported PNG bytes are cached with `.jpg`, and confirmation chooses MIME from that suffix. Uploads read the entire body and only inspect a short magic-byte prefix.

**Recommended change:** define supported artwork behavior per format, replace the intended front cover, verify new bytes/identity, preserve MIME accurately, and impose reasonable byte/dimension limits with real image decoding. Offer clear format-specific feedback until all formats have parity.

**Acceptance:** upload A then B and read back B; PNG remains PNG; OGG either roundtrips correctly or explains its limitation; excessive/invalid images are rejected without unnecessary memory use.

### 27. [P2] Batch edit makes unchanged values look like intended changes

**Category:** batch-edit UX. **Evidence: code-confirmed.**

**Location:** [app.js](../app/static/app.js), `showEditModal` 2706 and `handleBatchEdit` 2924; [library_api.py](../app/library_api.py), batch update 272.

Common values automatically uncheck “keep unchanged,” so opening a batch editor and saving can rewrite fields the user never touched. Mixed-value fields require the user to understand a separate checkbox, and cached track objects may be stale. There is no preview of changed fields or affected destinations, and the API accepts duplicate IDs/unbounded batch sizes. Per-track errors are returned but hidden from normal recovery.

**Recommended change:** default every field to keep, mark a field changed when edited or explicitly selected, expose set/clear semantics, and show a compact before/after summary plus affected count. Revalidate selected IDs/revisions, deduplicate requests, and retain failed items. Coordinate with findings 11 and 24.

**Acceptance:** opening and saving an untouched form causes no file writes; a one-field edit changes exactly that field; mixed-value and partial-failure cases remain understandable.

### 28. [P2] Deployment health and instructions have drifted from the application

**Category:** installation / operation UX. **Evidence: code-confirmed configuration issues; container not built.**

**Location:** [Dockerfile](../Dockerfile), [docker-compose.yml](../docker-compose.yml), [README.md](../README.md), [.env.example](../.env.example).

Compose's health check calls `curl`, but the Dockerfile installs only `gcc` explicitly; the chosen slim base is not a reliable contract for a curl-based check. The health URL serializes the entire pending list instead of doing a cheap readiness check. README still requests Gemini credentials and references removed `app/gemini_client.py`, while the implementation uses OpenRouter. Compose passes the API key but not the optional model/fallback/base-URL variables documented in `.env.example`. The README's unittest command omits the tests directory.

**Recommended change:** use an available runtime for a dedicated lightweight health endpoint, forward supported configuration, update the actual setup and provider instructions, and document local environment loading. Build and smoke-test the container as a release gate. Review pinned dependencies with a vulnerability tool before upgrades; this inspection does not claim specific advisories.

**Acceptance:** a fresh documented setup works, health status reflects app readiness, model overrides reach the container, and verification commands run from the project root.

### 29. [P2] Existing tests miss the highest-impact user workflows

**Category:** maintainability / regression prevention. **Evidence: suite passed while isolated defects reproduced.**

**Location:** [tests](../tests/), particularly metadata/multi-artist tests; [app.js](../app/static/app.js), approximately 3,200 lines; API and scanner modules.

The 30 passing tests give useful coverage of parsing, artist matching, metadata roundtrips, and scan helpers. They do not exercise save/confirm ordering, DOM rendering, pagination correctness, modal behavior, or deletion of completed records. Several older tests execute assertions at import time rather than providing independently collected cases. No repository CI workflow was present in the inspected tree.

**Recommended change:** add focused regressions with each correction: isolated API tests, a few browser journeys, and media fault-path tests. Introduce CI with existing tests and syntax checks. Gradually extract API access, queue state, library queries, dialog behavior, and rendering from the monolithic script as those areas change; avoid a framework rewrite without evidence that it solves a measured problem.

**Acceptance:** the reproduced defects fail before their fixes and pass afterward; tests use temporary files, mocked external services, and a documented environment. Do not create tests that merely assert a function exists or is declared async.

### 30. [P2] Review cards demand too much scrolling and give small controls too little space

**Category:** task speed / mobile ergonomics. **Evidence: visual inspection and measured control sizes; layout changes are proposals.**

**Location:** [style.css](../app/static/style.css), card/header styles near 201/236, mobile genres 722, artist toggle 306, artist buttons 1627/1646; [app.js](../app/static/app.js), card markup 516.

On phones, six genre options become six full-width rows, artwork keeps sharing a narrow row with editable fields, and large gaps separate confirmation/deletion. A single review takes substantial vertical space. Add/remove artist controls use a different font and small hit areas: remove is 32×32px; add measured 33px high; dropdown toggles are 25.6×25.6px.

**Recommended change:** use a compact two-column/wrapping genre group when labels fit, put full-width editing fields below a compact source/artwork summary, preserve a prominent confirm action, and make deletion secondary. Use approximately 44px hit areas for frequent touch actions without making every visual element large. A 44px design target is stricter than WCAG 2.2 AA's 24px minimum with exceptions; a 32px control is not automatically an AA failure. [W3C target-size guidance](https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html)

**Acceptance:** compare the time and scrolling needed to review ten files; preserve label readability, focus order, and access to the full source title at narrow widths.

### 31. [P2] Arabic terminology and editing states need clearer explanations

**Category:** UX writing / RTL clarity. **Evidence: inspected copy and behavior; replacements are proposals.**

**Location:** [index.html](../app/static/index.html), toolbar, library, settings, modal; [app.js](../app/static/app.js), error strings, artist suggestions, and confirmation; [style.css](../app/static/style.css), album-artist row highlight near 1672.

The UI mixes “الميتاداتا,” “البيانات الوصفية,” “ملف,” and “صوتية,” and some errors expose English field names or backend details. The first artist row is visually highlighted as album artist, although backend derivation may choose another artist based on the channel. The pending user cannot explicitly see/control that choice. A raw fuzzy-match number is displayed without explaining its meaning. Debug mode is a prominent ordinary toolbar action, while useful destination preview is hidden behind it.

**Recommended change:** use consistent domain terms, explicit saving/saved/failed labels, human-readable Arabic errors with technical details in a secondary disclosure, and a visible album-artist choice or accurate derived label. Move diagnostic controls into settings/advanced actions; make a simple destination preview available in the normal workflow. Isolate paths, tokens, and IDs with appropriate LTR direction while keeping Arabic prose RTL.

Suggested copy:

| Situation | Suggested Arabic |
|---|---|
| Edit metadata | تعديل بيانات الملف |
| Save pending edit | جارٍ حفظ التعديل… |
| Save failed | تعذّر حفظ التعديل. أعد المحاولة قبل نقل الملف. |
| Confirm transfer | حفظ ونقل إلى المكتبة |
| Album artist | فنان الألبوم |
| No matching search | لا توجد نتائج مطابقة. جرّب اسمًا آخر. |
| Partial transfer | نُقل 3 ملفات، وتعذّر نقل ملفين. |
| Destructive confirmation detail | سيُحذف الملف الأصلي والنسخة المعدّة للمراجعة. |

**Acceptance:** the displayed album artist matches the destination rule; errors tell users what happened and what to do next; Arabic counts use appropriate plural handling rather than `${n} ملف` everywhere.

### 32. [P2] Telegram settings cannot clearly be disabled or disconnected

**Category:** settings UX. **Evidence: code-confirmed.**

**Location:** [settings_api.py](../app/settings_api.py), update 58; [index.html](../app/static/index.html), Telegram form; [app.js](../app/static/app.js), settings handlers 3019 onward.

An empty token preserves the existing token, while clearing chat ID is rejected when a token exists. The UI has no notifications-enabled switch or explicit remove-token action. Users who have connected notifications cannot turn them off through a clear supported flow. HTTP exception text from Telegram is returned to the UI; it should be checked for credential-bearing URLs before display/logging.

**Recommended change:** add an enabled flag and an explicit disconnect operation, retain the useful masked-token behavior, and sanitize transport errors. Keep test, save, disable, and disconnect outcomes distinct.

**Acceptance:** disabling preserves configuration but sends no notifications; disconnect removes credentials; blank-token save still means preserve; error responses never expose the full token. Verify with mocked delivery.

### 33. [P3] Undefined CSS tokens and font inheritance cause visual drift

**Category:** theming / polish. **Evidence: code-confirmed and browser-inspected.**

**Location:** [style.css](../app/static/style.css), artist buttons 1627/1646.

`--text-error` and `--accent-color` are referenced but never defined; the defined tokens are `--error` and `--accent-primary`. Add/remove artist buttons also omit the shared font, and computed style used Arial. These controls look unrelated to the rest of the form.

**Recommended change:** use existing semantic tokens and shared typography; remove obsolete rules only when verified unused. Document the small set of colors, spacing, and component states already in use.

**Acceptance:** no unresolved CSS variables, consistent Arabic control typography, and intentional destructive/secondary colors.

### 34. [P3] The favicon is larger than the JavaScript and stylesheet combined

**Category:** initial-load performance. **Evidence: measured file sizes.**

**Location:** [favicon.png](../app/static/favicon.png), [index.html](../app/static/index.html), font stylesheet links near line 10.

The favicon is **347,404 bytes**, versus **117,842 bytes** for JavaScript and **34,495 bytes** for CSS. The Arabic font is externally hosted; `display=swap` and preconnect are already good choices, but font availability affects layout.

**Recommended change:** export appropriately sized favicon variants, inspect actual font usage/subsets, and consider a licensed self-hosted WOFF2 asset if offline/private-host reliability matters. Use versioned static caching and compression at the serving layer where useful. Measure transferred bytes before introducing a build system.

**Acceptance:** favicon transfer falls substantially without a visible loss at its rendered size; first visit and blocked-font rendering remain usable and do not overflow.

### 35. [P3] Motion preferences and transition scope need a small cleanup

**Category:** comfort / performance polish. **Evidence: code-confirmed.**

**Location:** [style.css](../app/static/style.css), repeated `transition: all`, card animations near 624, spinner near 1223, padding transition 1263.

Cards animate on render, several controls lift on hover, and there is no reduced-motion treatment. The library page animates padding when selection changes. Full queue rerenders amplify the motion.

**Recommended change:** provide a reduced-motion alternative that preserves clear progress/status, limit transitions to intended properties, and avoid layout animation for the selection-bar spacer. Keep necessary loading feedback understandable.

**Acceptance:** reduced-motion settings suppress nonessential movement; selecting tracks does not animate page layout; ordinary transitions remain brief and purposeful.

## 5. Recommended UI direction

This is an operational editor. Its visual hierarchy should help users review, correct, and move files with minimal uncertainty.

| Surface | Recommended arrangement | Why it helps |
|---|---|---|
| Shared header | Compact product name; clearly reachable Pending / Library / Settings navigation; mobile wrapping designed explicitly | Fixes the cross-page mobile failure |
| Pending toolbar | Queue count, search/filter, readiness summary, refresh, clear bulk action | Helps users find the next actionable file |
| Pending card | Compact source/artwork summary; full-width title; artist rows; explicit album artist; compact genre choice; saved/unsaved state; primary transfer action | Reduces scrolling and makes the final result predictable |
| Library | Context-specific search/sort; accurate counts; stable pagination; breadcrumbs for artist → album → tracks | Preserves orientation while browsing and editing |
| Edit dialog | Labelled fields; clear keep/set/clear behavior for batches; changed-field preview; local errors; persistent action footer | Reduces accidental edits and supports recovery |
| Long operations | Processed/total, current stage, failures, and retry-failed | Makes waiting understandable and recoverable |
| Empty/error state | Explain the cause and provide the appropriate next action | Avoids blank screens and ambiguous spinners |

Keep the dark Arabic identity. Improve contrast, density, alignment, and state behavior before decorative redesign. A light theme can follow later if users request it; its absence is not itself a defect.

## 6. Related feature ideas, ranked by value

These are additions rather than existing bugs. Dependencies matter: new automation should wait until saving, recovery, and batch outcomes are reliable.

| Order | Idea | User benefit | Smallest useful version | Dependency / effort |
|---:|---|---|---|---|
| 1 | Review filters and saved views | Reach unfinished/error files quickly in a large queue | Ready, missing artist, missing genre, needs review, errors; counts and clear filters | Correct state model; M |
| 2 | Audio preview | Verify the performer or title without leaving the editor | On-demand play/pause/seek for the active file; one player at a time; support range requests | Safe file-serving boundary; M |
| 3 | Change history and recoverable deletion | Recover from mistaken metadata edits or removals | Before/after tag log, move history, and a retention-limited trash/quarantine flow | Verified writes and storage policy; L |
| 4 | Metadata provenance | Understand which values need review | Mark values as embedded, inferred, or manually edited; reveal original value | Persist original/imported fields; M |
| 5 | Channel and artist presets | Reduce repeated genre/album-artist decisions | User-defined channel → suggested artist/genre rules, previewable and editable | Reliable draft/validation model; M |
| 6 | Artist aliases and merge preview | Keep Arabic spelling variants from splitting the library | Alias suggestions with affected track counts and an explicit merge diff | Correct counts/album identity; M–L |
| 7 | Keyboard review workflow | Process queues faster on desktop | Next/previous item, focus title/artist, choose genre, confirm; visible shortcut help | Accessibility and reliable save completion; M |
| 8 | Duplicate review | Avoid importing the same recording repeatedly | Exact content-hash candidates calculated off the request loop; compare metadata/source before action | Separate source identity and hashes; M–L |
| 9 | Operation center | Find failed imports, scans, and batches in one place | Durable job status, failed items, retry, last successful scan, storage/provider diagnostics | Background job model; M–L |
| 10 | Batch artwork management | Fix album covers efficiently | One image preview applied to explicitly selected tracks; per-file results | Format-correct artwork replacement; M |
| 11 | Previewable library reorganization | Bring existing maintenance scripts into a safer workflow | Show proposed old/new paths and collisions; export plan; apply with operation history | Stable album identity and recovery; L |
| 12 | Optional Navidrome integration | Show when transferred files become available to listeners | Link to the relevant library/search; add refresh controls only after verifying deployed Navidrome capabilities | Deployment-specific investigation; M |
| 13 | Review export/import | Support large cleanup projects or external review | Export IDs/revisions/current values; validate a CSV import and show a diff before applying | Versioned batch edits; M |

Do not label fuzzy name similarity as AI metadata confidence. If a future review score is useful, base it on explicit signals—missing fields, fallback usage, conflicting embedded values, uncertain artist matches—and explain those signals.

## 7. Delivery sequence and success criteria

### Phase A — reliable editing and file safety

Complete 01–04 and 07–11. Add the narrow regression cases in 29 alongside fixes. Gate: no completed-file deletion through pending APIs, no metadata-generated HTML, and no successful confirmation with an unsaved/failed draft. Failed writes leave recoverable files and truthful UI results.

### Phase B — usable mobile and accessible feedback

Complete 06 and 12–14; include the inexpensive token fix in 33. Then improve density/copy with 30–31. Gate: no page overflow at 320px, all main tasks work with keyboard, modal focus is contained/restored, feedback is visible, and active text contrast meets its applicable threshold.

### Phase C — responsive processing at realistic scale

Complete 05, 17–23, and the relevant parts of 26. Start with measurements on the deployment hardware and storage. Keep a bounded worker model, lazy/cached artwork, and limited mounted queue content. Gate: browsing stays responsive during representative file writes and scans; progress/reconnect/retry remain usable.

### Phase D — predictable deployment and fewer repeated actions

Complete 15–16, 24–29, and 32 as applicable; bring deployment/access work forward immediately if the service is reachable beyond its intended private boundary. Add the first feature ideas: filters, audio preview, history, and presets. Finish with 34–35.

### Proposed performance targets

These are starting acceptance targets to calibrate on representative hardware, not measured current performance or guaranteed improvements.

| Area | Proposed target / measurement |
|---|---|
| Typing and selecting | No application-caused long tasks above 50ms during steady interaction with a representative queue |
| Library browsing | p95 list/search response under 300ms on the chosen deployment, including while a file job runs |
| Queue rendering | Mount a bounded number of cards; measure scripting + layout + paint rather than HTML construction alone |
| Artist suggestions | Approximately 200–400ms perceived response including intentional debounce; discard obsolete requests |
| Live arrivals | UI learns about a newly registered queue item within roughly one second through events; AI work has its own processing state |
| Artwork | Unchanged repeat views reuse cache; grid requests fetch thumbnails rather than original-size artwork |
| Library scan | Count SQL queries, tag reads, file stats, writes, and bytes read; unchanged scans perform no tag reads/writes |
| Batch operation | Accurate processed/success/failed counters, recoverable interruption, and bounded resource use |

Use fixtures at 10, 100, and 500 pending items; libraries at 3,500 and 20,000 tracks; small and large artwork; large audio files; slow/failing I/O; and mixed success/failure batches. Stop expanding tests once each change's concrete risks and release gates are covered.

## 8. What to preserve

- The vanilla frontend avoids framework/runtime overhead and does not require a rewrite to fix these issues.
- Staging keeps the incoming original available until confirmation; strengthen its recovery guarantees.
- Arabic normalization, multi-artist handling, suggestion debouncing, caching, and request-token checks are useful existing building blocks.
- Metadata roundtrip tests cover real generated media, including Arabic values and multiple artists.
- The library scan already uses one directory walk and skips metadata reads for unchanged files.
- Pending smart updates already attempt to avoid replacing active cards; extend that approach to existing-card reconciliation.
- Settings responses mask stored tokens, and Telegram message content is escaped.
- Mobile library cards, selection bars, and sticky modal actions provide useful groundwork once shared navigation and accessibility are corrected.
- Maintenance scripts default to dry-run behavior; retain explicit previews if those operations move into the UI.

## 9. Detector review and final verification notes

The interface detector reported four warnings:

1. Gradient heading text at CSS line 71: the `.header` selector is not used by the current HTML, so this is not an active visible defect.
2. Gradient text at line 756: used by the brand. This is a design choice, not evidence of functional failure; prioritize contrast/readability over removing it automatically.
3. `padding-bottom` transition at line 1263: a real layout-property animation, addressed in 35; no dropped-frame claim was measured for this transition alone.
4. A supposed side accent at line 212: the actual rule is a top hover stripe, so the detector's classification is imprecise. No separate severity is assigned to this decoration.

The most important recurring problems are duplicated state, implicit save semantics, optimistic feedback without verified outcomes, and synchronous work inside async APIs. Correcting these shared patterns will resolve more friction than isolated cosmetic changes.

### Suggested interface work commands

For follow-up interface work, use these in dependency order:

1. `$impeccable harden` — draft/save states, truthful outcomes, visible errors, and dialog behavior.
2. `$impeccable adapt` — shared mobile navigation and narrow-screen form layout.
3. `$impeccable colorize` — correct the verified contrast problems while preserving the palette's identity.
4. `$impeccable optimize` — bounded queue rendering, targeted DOM updates, and image loading.
5. `$impeccable clarify` — consistent Arabic copy, destination explanation, and field semantics.
6. `$impeccable audit` — reassess the repaired surfaces against these findings.
7. `$impeccable polish` — final spacing, typography, and motion pass after functional gates pass.

These interface passes can be requested individually or in any preferred order. Backend/file-safety changes should follow the ranked findings and their acceptance checks. The report is the deliverable for this inspection; application code was not changed.
