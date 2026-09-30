# Audit review and improvement plan

**Reviews:** [PROJECT_INSPECTION_2026-09-30.md](PROJECT_INSPECTION_2026-09-30.md) (the "audit")  
**Baseline:** `6fd9783` · **Date:** 2026-09-30

The audit is kept as the evidence appendix. This document is the working plan: it corrects the audit's
priorities, adds what it missed, and cuts its 35 findings into small, shippable tickets. Finding numbers
like `#03` refer to the audit.

---

## 1. Verdict on the audit

### What it gets right

- **The facts hold up.** Spot-checked against the code: #01 (delete of a `done` item unlinks the library
  file), #02 (library renderers use raw `innerHTML` and inline `onclick`), #03 (`confirmItem` reads the
  form values but never sends them), #04 (duplicated `if not success` block referencing undefined
  `artist`), #07 (Python sort runs *after* SQL `limit/offset`), #09 (`shutil.move` runs before
  `_verify_written_metadata`), #10 (`isinstance(audio.tags, dict)` in `library_scanner.py:345`), #28
  (README still says Gemini, healthcheck uses `curl` on a slim image). Line numbers were accurate.
- **Evidence labels** (reproduced / code-confirmed / risk / proposal) make it easy to tell what was
  actually observed from what was guessed.
- **"What to preserve" (§8)** is good advice: no framework rewrite, and keep the staging model.

### What's wrong with it

1. **It's sized for a team product, not a single-user home tool.** It has 35 findings, 13 feature ideas,
   4 phases, a "7/20 Poor" health score and p95 latency targets. That's hard to act on and makes the
   project look worse than it is. The actual job is getting files from Pinchflat into Navidrome with
   correct tags, safely. Most of what matters fits in about 12 small tickets.
2. **Priorities mix harm with polish.** Modal focus-trapping (#12) and gradient contrast (#13) sit at P1,
   next to bugs that corrupt or lose files (#09, #10). For one operator using a mouse or phone, those are
   P2/P3. Meanwhile #09 (tags changed even though the operation reported failure) should be P0.
3. **The fixes it prescribes are heavier than needed.** It proposes "operation journal", "versioned
   draft model", "bounded inference queue", "virtualization", and "background job with progress". Most
   of the P0/P1 bugs have fixes of 5–30 lines (see §3). A heavy plan delays the easy wins.
4. **No threat model.** #02 and #15 are rated without asking where the data comes from or who can reach
   port 8090. There is a real chain here: YouTube uploader's title → AI copies it → tag → library
   `innerHTML`, combined with unauthenticated delete APIs. That chain is what makes #02 serious. The
   audit never spells it out, so its severity looks arbitrary.
5. **Performance numbers measure imagined scale.** Rendering 500 pending cards and a 20k-track library
   were benchmarked without asking how big the queue actually gets. The one performance problem that
   matters (blocking `async def` routes, #05) is buried among speculative ones (#18, #19, #22).
6. **Lots of overlap.** #11/#24/#27 (batch semantics), #17/#19/#21 (UI state sync) and #18/#26
   (artwork) are each one theme split into several findings. The count of 35 is inflated.
7. **Tool-specific noise.** §9's `$impeccable …` commands and the detector-warning triage are notes
   about the audit tool, not about the project.
8. **It misses the NAS/filesystem side.** See §2. For a Docker service writing into a library that
   Navidrome watches, these are some of the most likely real-world failures.

---

## 2. Findings the audit missed

| ID | Severity | Finding | Where |
|---|---|---|---|
| **N1** | P1 | **Non-atomic move into the watched library.** `/data/staging` and `/music` are separate bind mounts, so `shutil.move` falls back to copy + delete. The destination file is written progressively under its final name, and Navidrome can index a half-written file. A crash mid-copy leaves a truncated track in `/music`. | `mover.py:97` |
| **N2** | P1 | **Files land owned by root.** The container has no `user:` / PUID/PGID, so every moved file and artist folder is `root:root`. The host user (and possibly Navidrome/Pinchflat) can't edit or delete them. | `Dockerfile`, `docker-compose.yml` |
| **N3** | P2 | **Silent duplicate tracks.** Re-importing the same song creates `title (1).mp3` next to the original. Navidrome then shows two copies. The dry-run knows the destination exists but doesn't warn. | `mover.py:37-40` |
| **N4** | P1 | **Delete is irreversible and destroys the only original.** Deleting a pending item removes the Pinchflat download from `/incoming` *and* the DB row. The row has to be deleted, otherwise dedup would block re-import. A `dismissed` status would allow keeping the row while leaving (or quarantining) the original. | `api.py:402-446` |
| **N5** | P1 (after #05) | **Confirm check-then-act race.** `confirm_item` checks `status in [...]`, then does slow work, then marks done. Today the blocked event loop accidentally serializes this. Once #05 moves the work to threads, a double click or two tabs can confirm twice → two library copies (with N3's `(1)` naming). Needs an atomic `UPDATE … SET status='processing' WHERE id=? AND status IN (...)`. | `api.py:254` |
| **N6** | P2 | `except Exception` in `delete_item` (and others) turns the 404 `HTTPException` into a 500. The audit notes this once for #01, but it's a pattern across routes. | `api.py:448` |

---

## 3. The plan

Tickets are small enough for one PR each. Every ticket ships with a regression test that fails first.

### Sprint 0 — stop data loss (do first, each ≤ ~1 hour)

| # | Ticket | Simplest fix | Covers |
|---|---|---|---|
| S0-1 | Block deleting completed items | In `delete_item`: 409 if `status == "done"`. Only unlink `current_path` if it `is_relative_to(STAGING_DIR)`. Let `HTTPException` propagate. | #01, N6 |
| S0-2 | Verify before replacing | In `update_metadata_safe` / `embed_artwork_safe`: call `_verify_written_metadata(temp_path, …)` **before** `shutil.move`. | #09 |
| S0-3 | Fix scanner failure branch | Delete the duplicated `if not success:` block. Add `notify` + `return` to the first. Don't `rmtree` a staging dir that a created row points at. | #04 |
| S0-4 | Rescan must not write | Remove the tag write from `_index_file` (index only). Fix the `isinstance(..., dict)` check for later reuse. | #10 |
| S0-5 | Atomic move into `/music` | Copy to a hidden temp name (`.{name}.partial`) in the destination dir, `fsync`, then `os.replace` to the final name. Delete the source after that. | N1 |

### Sprint 1 — make confirm trustworthy

| # | Ticket | Simplest fix | Covers |
|---|---|---|---|
| S1-1 | Confirm sends what the user sees | `POST /pending/{id}/confirm` accepts `{title, artist, genre}`. The server persists and confirms in one request. The frontend sends the DOM values it already reads. | #03 |
| S1-2 | Normalize item IDs | `Number()` once where artist row IDs are parsed (`getItemIdFromRowId`). Fix `captureFocusSnapshot` to read `data-item-id`. | #03 |
| S1-3 | Honest bulk results | `confirmItem` returns `true/false`. `confirmAllReady` counts only successes and reports "X moved, Y failed". | #11 |
| S1-4 | Safe library rendering | Use the existing `escapeHtml` in all library renderers. Replace inline `onclick="…('${…}')"` with `data-*` attributes plus one delegated listener. | #02 |
| S1-5 | Unblock the event loop | Change blocking routes from `async def` to `def` (FastAPI threadpools them). Keep `/events` async. Bridge SSE notifications from threads via `loop.call_soon_threadsafe`. **Ships together with S1-6.** | #05 |
| S1-6 | Atomic confirm claim | Compare-and-set to `processing` before work. Revert to `error` on failure. | N5 |
| S1-7 | Scanner pushes `new_item` | Reuse the S1-5 thread→loop bridge so arrivals appear immediately instead of on the 15s poll. | #17 (partial) |

### Sprint 2 — daily-use UX

| # | Ticket | Covers |
|---|---|---|
| S2-1 | Mobile nav: a media query that wraps/stacks brand + nav. No document overflow at 320px. | #06 |
| S2-2 | Move `globalAlert` outside `pendingPage` so library errors are visible. Show the empty-state elements. | #14 |
| S2-3 | Push sorting and filtered counts into SQL. Reset an invalid sort on tab change. Validate `limit ≥ 1`, `offset ≥ 0`. | #07 |
| S2-4 | Album drill-down passes `album_artist` (and year) as well as the name. | #08, #25 |
| S2-5 | Dedup the artist-count increment. Pick the artwork sample from tracks with `has_artwork=1`. | #25 |
| S2-6 | Warn when the destination already exists (dry-run + card), with a "replace / keep both / skip" choice. | N3 |
| S2-7 | Upsert the `LibraryTrack` row after a successful confirm, so no manual rescan is needed. | #21 (partial) |

### Sprint 3 — deployment hygiene

| # | Ticket | Covers |
|---|---|---|
| S3-1 | `user: "${PUID}:${PGID}"` in compose. Document it in `.env.example`. | N2 |
| S3-2 | `/api/health` endpoint. Healthcheck via `python -c "urllib.request…"` (no curl). Forward `OPENROUTER_MODEL` / `FALLBACK_MODELS` / `BASE_URL` in compose. | #28 |
| S3-3 | Rewrite README for OpenRouter. Drop Gemini references. | #28 |
| S3-4 | GitHub Actions: `pytest` + `node --check app/static/app.js`. | #29 |
| S3-5 | Replace hard delete with a `dismissed` status. Move the original to `/data/trash` with retention. | N4 |

### Later (only when a real need shows up)

- Contrast fixes on confirm/primary buttons (#13) are cheap, so batch them with S2-1.
- Keyboard/modal accessibility (#12) and reduced motion (#35).
- Artwork caching/thumbnails (#18), OGG artwork parity (#26).
- Queue pagination/DOM work (#19). Do this only if the queue regularly passes ~100 items.
- Batch-edit keep/set/clear semantics (#27, #24).
- Telegram disable/disconnect (#32). Favicon size (#34): a one-minute win, do it anytime.
- Auth (#15). **Moves to Sprint 0 if port 8090 is reachable from outside the LAN** (see §4).

### Not doing (for now)

Operation journal, inference worker queue, virtualization, SQL aggregate caching (#22: 11ms at 3.5k
tracks), the health-score framework, and the 13-item feature list. Revisit feature ideas after Sprint 2.
The two worth keeping in mind are **audio preview** and **review filters**.

---

## 4. Questions that change priorities

1. **Is port 8090 exposed beyond your LAN** (reverse proxy, Tailscale Funnel, port-forward)? If yes,
   #15 auth becomes Sprint 0.
2. **Typical pending queue size?** If it's under ~50, #19 is dropped entirely.
3. **Do you mainly review on the phone?** If yes, S2-1 and #30 (card density) move up.
4. **Is `/data` on the same filesystem as `/music` on the NAS?** Even so, separate bind mounts make
   `rename` fail with `EXDEV`, so N1 still applies inside Docker.
5. **Who owns files in the Navidrome library on the host (UID/GID)?** Needed for S3-1.

## 5. Working rules

- One ticket = one branch = one PR. Micro-commits inside.
- Each fix starts with a failing test in `tests/` using temp dirs and mocked OpenRouter/Telegram.
- Don't combine refactors with fixes. Extract parts of `app.js` only when a ticket already touches them.
