# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

One operator: the owner of the library, and nobody else. They review on a phone (about 390px wide) most of the time, often at night, reaching the service over Tailscale. There are no roles, accounts or onboarding.

## Product Purpose

محرر الأصوات الولائية sits between Pinchflat and Navidrome. Pinchflat downloads Shia devotional audio from YouTube channels (لطميات, قصائد, مواليد وأفراح, أدعية, قرآن, شعر). An LLM proposes the Arabic title and performers, and every file waits in a review queue. The operator corrects the title, artists, folder (album artist) and genre, then confirms. The app writes verified tags and moves the file into the Navidrome library.

Success means the library stays clean, with correct Arabic names, one spelling per artist and the right folder, and that reviewing takes as little effort as possible.

## Positioning

A general tag editor (MusicBrainz Picard, Mp3tag) assumes Latin metadata and an online database to match against. This tool is built for Arabic devotional recordings that no database knows. It infers from the YouTube title and channel, matches artist spellings with Arabic-aware normalization, and treats the review queue as the main surface.

## Operating Context

- **Two review rhythms, about equally:** single confirms right after a Telegram ping, and longer sessions clearing 10–50 cards in a row.
- **Queue card:** title, one or more artists (`;`-separated), album artist / folder, genre preset, destination preview, confirm. "Confirm all ready" exists for long sessions.
- **Library pages:** browse artists, albums, genres and tracks; single and batch tag edits; artist-variant merge; rescan.
- **Settings:** Telegram notifications (connect, test, pause, disconnect).
- Live updates arrive over SSE. Originals are never modified; deleted items go to a trash folder.

## Capabilities and Constraints

- FastAPI + SQLite backend. Vanilla JS/CSS frontend with no framework and no build step (`app/static/`).
- Arabic RTL throughout. Paths, tokens and IDs are Latin/LTR fragments inside RTL prose.
- Formats: MP3, M4A, FLAC, OGG. Folder layout: `/music/{album artist}/{title}/{title}.ext`.
- Terms in use: صوتية / ملف (track / file), فنان (artist), فنان الألبوم / المجلد (album artist / folder), النوع (genre), قائمة الانتظار (queue), المكتبة (library).
- Undecided: one term for "metadata" (الميتاداتا vs البيانات الوصفية); see Sprint 4 B2.

## Brand Commitments

- The product name **محرر الأصوات الولائية** stays.
- The current icon (music note + pencil, blue→teal gradient; `app/static/favicon-32.png`, `apple-touch-icon.png`) is the brand mark.
- **Dark theme only.** It is used at night, and no light theme is needed.
- **No religious imagery as decoration**: no calligraphy, domes or geometric patterns as ornament on a utility tool.
- Voice: calm, plain, respectful of the content. No playful gimmicks, no confetti.

## Evidence on Hand

- Real artist names, genres and channel names live in the operator's library. Test fixtures use invented names. Never invent library statistics or usage claims.
- Audit evidence: `docs/PROJECT_INSPECTION_2026-09-30.md`; plan: `docs/SPRINT_4_PLAN.md`.

## Product Principles

1. **The queue is the product.** Every second saved per card matters across a 50-card session.
2. **What you see is what you get.** The card shows exactly what confirm will write and where the file will go.
3. **Never surprise the library.** No silent writes, no hidden side effects. Destructive actions are explicit and recoverable.
4. **Calm over clever.** The content is devotional, so the tool stays quiet and gets out of the way.
5. **Phone first, Arabic first.** Design at 390px RTL, then check desktop.
