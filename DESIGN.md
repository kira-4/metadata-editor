---
name: محرر الأصوات الولائية
description: A dark, Arabic-first review tool for devotional audio on its way into Navidrome.
colors:
  night-ink: "#0f0f23"
  archive-navy: "#1a1a2e"
  shelf-navy: "#16213e"
  lamp-navy: "#1e2a47"
  seam: "#2a2a3e"
  parchment-text: "#e8e8e8"
  faded-text: "#a0a0a0"
  margin-text: "#6b6b6b"
  signal-blue: "#4a9eff"
  signal-blue-light: "#6bb1ff"
  signal-blue-deep: "#2d7dd2"
  settled-teal: "#00d4aa"
  settled-teal-deep: "#00b894"
  caution-amber: "#ffb627"
  fault-red: "#ff5757"
typography:
  headline:
    fontFamily: "Cairo, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif"
    fontSize: "1.5rem"
    fontWeight: 700
    lineHeight: 1.6
  title:
    fontFamily: "Cairo, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif"
    fontSize: "1rem"
    fontWeight: 600
    lineHeight: 1.6
  body:
    fontFamily: "Cairo, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif"
    fontSize: "1rem"
    fontWeight: 400
    lineHeight: 1.6
  label:
    fontFamily: "Cairo, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif"
    fontSize: "0.85rem"
    fontWeight: 400
    lineHeight: 1.6
  mono:
    fontFamily: "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace"
    fontSize: "0.85em"
rounded:
  sm: "0.5rem"
  md: "0.75rem"
  lg: "1rem"
spacing:
  xs: "0.5rem"
  sm: "0.75rem"
  md: "1rem"
  lg: "1.5rem"
  xl: "2rem"
components:
  button-primary:
    backgroundColor: "{colors.signal-blue}"
    textColor: "{colors.night-ink}"
    rounded: "{rounded.sm}"
    padding: "0.75rem 1.5rem"
  button-secondary:
    backgroundColor: "{colors.shelf-navy}"
    textColor: "{colors.parchment-text}"
    rounded: "{rounded.sm}"
    padding: "0.75rem 1.5rem"
  button-confirm:
    backgroundColor: "{colors.settled-teal}"
    textColor: "{colors.night-ink}"
    rounded: "{rounded.md}"
    padding: "1rem"
    width: "100%"
  card-review:
    backgroundColor: "{colors.archive-navy}"
    rounded: "{rounded.lg}"
    padding: "1.5rem"
  input-field:
    backgroundColor: "{colors.shelf-navy}"
    textColor: "{colors.parchment-text}"
    rounded: "{rounded.sm}"
    padding: "0.5rem 0.75rem"
  chip-genre:
    backgroundColor: "{colors.shelf-navy}"
    textColor: "{colors.parchment-text}"
    rounded: "{rounded.sm}"
    padding: "0.75rem 1rem"
  chip-genre-selected:
    backgroundColor: "{colors.signal-blue}"
    textColor: "{colors.night-ink}"
    rounded: "{rounded.sm}"
  nav-link-active:
    backgroundColor: "{colors.signal-blue}"
    textColor: "{colors.night-ink}"
    rounded: "{rounded.sm}"
    padding: "0.75rem 1.5rem"
---

# Design System: محرر الأصوات الولائية

## Overview

**Creative North Star: "The Night Archive"**

A quiet late-night workroom for cataloguing recordings. The room is deep navy, and the surfaces step up in small tonal increments the way shelves sit in low light. One cool blue marks the thing you can act on. Teal appears only when something is settled: a file confirmed, a save done. Amber and red stay rare and mean exactly one thing each.

The tool serves devotional content, so it stays calm. Density favours the review card: fields are full width, labels sit above inputs, and the primary action spans the card. Arabic RTL is the native direction. Latin fragments (paths, tokens, IDs, file extensions) are isolated islands inside it, never the other way round.

Today the system mixes this calm base with a few louder habits inherited from earlier iterations: gradient fills on actions, gradient title text, hover lift on cards. They are recorded below as they are and flagged; the design pass decides each case.

**Key Characteristics:**
- Dark only, navy not black; depth from tonal steps and 1px seams.
- One action colour (signal blue), one completion colour (settled teal).
- Cairo for everything Arabic; system mono for paths and code.
- Full-width, thumb-reachable controls on a 390px phone.

## Colors

A cool, low-light palette: four navy surface steps, three grey text tones, and a small set of signal colours that each carry one meaning.

### Primary
- **Signal Blue** (`signal-blue`): the action colour. Primary buttons, active navigation, selected genre chip, focus border, active tab underline, selection highlight. Its lighter step (`signal-blue-light`) is hover; the deeper step (`signal-blue-deep`) is pressed.

### Secondary
- **Settled Teal** (`settled-teal`, deep step `settled-teal-deep`): completion. The confirm-and-move button, "confirm all ready", success messages, Telegram "connected and on".

### Tertiary
- **Caution Amber** (`caution-amber`): needs attention but isn't broken. Manual-review badge, "will be cleared" state in batch edit, destination-exists warning, paused notifications.
- **Fault Red** (`fault-red`): failure and destruction. Error badges, failed files, delete actions, the pending-count badge on the nav.

### Neutral
- **Night Ink** (`night-ink`): page background, and the text colour on bright fills (blue, teal) so contrast holds.
- **Archive Navy** (`archive-navy`): cards, nav bar, modals.
- **Shelf Navy** (`shelf-navy`): inputs, chips, secondary buttons, summary panels inside cards.
- **Lamp Navy** (`lamp-navy`): hover surface.
- **Seam** (`seam`): every 1px border and divider.
- **Parchment Text** (`parchment-text`): primary text. **Faded Text** (`faded-text`): labels and meta. **Margin Text** (`margin-text`): placeholders, hints, idle states.

### Named Rules
**The One Meaning Rule.** Each signal colour means one thing. Blue is "you can act", teal is "done", amber is "look at this", red is "failed or destructive". Never use teal for a neutral action or blue for success.

**The Dark Text On Light Fill Rule.** Text on blue or teal fills is Night Ink, not white. White on Signal Blue measured about 2.5:1.

## Typography

**Body Font:** Cairo (400/600/700, Google Fonts) with the system UI stack as fallback.
**Label/Mono Font:** system monospace for paths and code fragments.

**Character:** Cairo is a geometric Arabic sans with a matching Latin, legible at small sizes on a phone and neutral enough for religious titles.

### Hierarchy
- **Headline** (700, 1.5rem): brand title in the nav, page titles.
- **Title** (600, 1rem): card field values in inputs, list item titles, buttons, tabs.
- **Body** (400, 1rem, line-height 1.6): running text and inputs.
- **Label** (400, 0.85rem): field labels, list meta, source line, hints (0.8rem).

### Named Rules
**The Isolated Latin Rule.** Paths, file extensions, tokens and chat IDs are wrapped in `<bdi>` or set `dir="ltr"`, so the bidi algorithm never reorders them inside Arabic prose.

## Layout

A single centred column (max 1400px, 2rem padding; 1rem on phones). The review queue is a grid of cards (min 400px columns) that collapses to one column on phones. The library has tabs (artists, albums, genres, all tracks), a search/sort bar, then a list or album grid. A fixed selection bar appears at the bottom in multi-select mode.

Breakpoints: 768px (tablet adjustments) and 600px (phone: stacked nav, full-width fields, genre chips in rows of three, small artwork beside the source line, 44px touch targets).

Spacing follows the 0.5 / 0.75 / 1 / 1.5 / 2rem scale; card internals mostly use `md` between groups and `xs`–`sm` inside a group.

## Elevation & Depth

**Direction: flat, tonal layers.** Depth comes from the navy steps (Night Ink → Archive Navy → Shelf Navy → Lamp Navy) and 1px Seam borders. Shadows belong only to things that float above the page: modals, dropdown suggestion lists, the selection bar.

Flagged for the design pass: cards and primary buttons still lift on hover (`translateY(-2px)` with `0 8px 24px` shadow, coloured glow on confirm), and cards grow a blue→teal top bar on hover. These contradict the flat direction.

### Shadow Vocabulary
- **Overlay** (`0 12px 24px rgba(0,0,0,0.35)`): modals and floating panels.
- **Dropdown** (`0 4px 16px rgba(0,0,0,0.35)`): suggestion lists.
- **Focus ring** (`0 0 0 3px rgba(74,158,255,0.1)`): input focus, paired with a Signal Blue border.

### Named Rules
**The Flat-At-Rest Rule.** Surfaces don't cast shadows at rest. Only overlays float.

## Shapes

Gently rounded throughout: 0.5rem for controls (inputs, buttons, chips), 0.75rem for the confirm button, artwork and list items, 1rem for cards, the nav bar and modals. Borders are 1px Seam; selected chips and nav use a 2px border in Signal Blue. Artwork is square with 0.75rem corners.

## Components

### Buttons
- **Shape:** gently rounded (0.5rem); confirm is 0.75rem and full width.
- **Primary:** Signal Blue fill, Night Ink text, 600 weight. Currently a 135° gradient to Signal Blue Light (flagged).
- **Confirm:** Settled Teal fill (currently gradient to Settled Teal Deep, flagged), Night Ink text, 700 weight, full width at the bottom of the card.
- **Secondary:** Shelf Navy fill, Seam border, Parchment text; hover Lamp Navy with a Signal Blue border.
- **Quiet danger:** secondary button with Fault Red text; two-tap arm state gets a red border and a faint red wash.
- **Disabled:** Shelf Navy fill, Margin text, reduced opacity.

### Chips (genre presets)
- **Style:** Shelf Navy fill, 2px Seam border, 600 weight, centred; rows of three on phones.
- **Selected:** Signal Blue fill (gradient today, flagged) with Night Ink text.

### Cards / Containers
- **Review card:** Archive Navy, 1rem corners, 1.5rem padding, 1px Seam border. Inner panels (destination preview, batch summary, rescan status) are Shelf Navy with 0.5rem corners.
- **List item:** Archive Navy, 0.75rem corners, 1rem padding; selected gets a translucent blue wash and blue border.

### Inputs / Fields
- **Style:** Shelf Navy fill, 1px Seam border, 0.5rem corners, 1rem text.
- **Focus:** Signal Blue border plus the soft focus ring.
- **Changed (batch edit):** Signal Blue border while a field is set to change.
- **Disabled:** half opacity.

### Navigation
- **Top bar:** Archive Navy panel holding the brand title (gradient text today, flagged) and three page links. The active link is a Signal Blue fill with Night Ink text. A red count badge sits on the queue link. On phones the brand stacks above an equal-width row of links.
- **Library tabs:** text tabs with a 3px Signal Blue underline when active.

### Review Card (signature)
Artwork and source line, title input, one row per artist (combobox with suggestions, remove ×), "+ add artist", the folder line ("المجلد:" with a select when there are several artists, and an RTL destination path), genre chips, then the full-width confirm button, a status line and a quiet delete.

## Do's and Don'ts

### Do:
- **Do** keep text on Signal Blue or Settled Teal fills in Night Ink.
- **Do** isolate every Latin fragment (path, extension, token, ID) with `<bdi>` or `dir="ltr"`.
- **Do** give phone touch targets at least 44px and keep primary actions full width.
- **Do** use Shelf Navy panels with 0.5rem corners for status and preview blocks inside a card.

### Don't:
- **Don't** add a light theme. The product is dark only.
- **Don't** use religious imagery (calligraphy, domes, geometric patterns) as decoration.
- **Don't** introduce playful motion or celebration effects (no confetti).
- **Don't** give a signal colour a second meaning (see The One Meaning Rule).
- **Don't** add shadows to surfaces at rest (see The Flat-At-Rest Rule).
