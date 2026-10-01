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
  margin-text: "#959bb0"
  signal-blue: "#4a9eff"
  signal-blue-light: "#6bb1ff"
  signal-blue-deep: "#2d7dd2"
  settled-teal: "#00d4aa"
  settled-teal-deep: "#00b894"
  caution-amber: "#ffb627"
  fault-red: "#ff5757"
typography:
  display:
    fontFamily: "Cairo, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif"
    fontSize: "1.5rem"
    fontWeight: 600
    lineHeight: 1.6
  title:
    fontFamily: "Cairo, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif"
    fontSize: "1.0625rem"
    fontWeight: 600
    lineHeight: 1.6
  body:
    fontFamily: "Cairo, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif"
    fontSize: "1rem"
    fontWeight: 400
    lineHeight: 1.6
  label:
    fontFamily: "Cairo, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif"
    fontSize: "0.875rem"
    fontWeight: 600
    lineHeight: 1.6
  caption:
    fontFamily: "Cairo, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif"
    fontSize: "0.8125rem"
    fontWeight: 400
    lineHeight: 1.6
  micro:
    fontFamily: "Cairo, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif"
    fontSize: "0.6875rem"
    fontWeight: 700
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
- **Parchment Text** (`parchment-text`): primary text. **Faded Text** (`faded-text`): labels and meta. **Margin Text** (`margin-text`, `#959bb0`): placeholders, hints, idle states. It measures ≥5.1:1 on all four navies; the old `#6b6b6b` failed AA on every surface.

### Named Rules
**The One Meaning Rule.** Each signal colour means one thing. Blue is "you can act", teal is "done", amber is "look at this", red is "failed or destructive". Never use teal for a neutral action or blue for success.

**The Dark Text On Light Fill Rule.** Text on blue or teal fills is Night Ink, not white. White on Signal Blue measured about 2.5:1.

## Typography

**Body Font:** Cairo (400/600/700, Google Fonts) with the system UI stack as fallback.
**Label/Mono Font:** system monospace for paths and code fragments.

**Character:** Cairo is a geometric Arabic sans with a matching Latin, legible at small sizes on a phone and neutral enough for religious titles.

### Hierarchy
Every `font-size` in `style.css` is a role token (`--text-*`); there are no literal sizes. Line height is 1.6 throughout, which Arabic needs for its ascenders and dots.

- **Display** (`--text-display`, 600, 1.5rem; **1.25rem at ≤600px**): page headings (قائمة الانتظار, مكتبة الصوتيات, الإعدادات), the empty-queue heading, the nav brand (700).
- **Title** (`--text-title`, 600, 1.0625rem): the card title textarea (the field under review, so it outranks every other field), section headings in Settings, the edit dialog and the detail view.
- **Body** (`--text-body`, 400, 1rem): inputs, buttons, tabs on desktop, list item titles (600). This is the floor for anything typed into.
- **Label** (`--text-label`, 600, 0.875rem, Faded Text): field labels (`.field-label`, `.genre-label` and Settings labels share it), genre chips, secondary list lines, notices and alerts (400 for running text).
- **Caption** (`--text-caption`, 400, 0.8125rem): destination paths, the source line on phones, hints, the Latin hint after a label, field status, technical details.
- **Micro** (`--text-micro`, 700, 0.6875rem): the nav count badge only.

Icon characters (♪ ✓ ×) use a separate glyph scale (`--glyph-sm/md/lg/xl`: 1.25/1.5/2/3rem), so icon sizes never borrow a reading role.

Roles differ on more than size: Title is 600 in Parchment Text, Label is 600 in Faded Text one step smaller, and the values in inputs are 400. A label and its value are told apart by weight and tone even where their sizes are close.

### Named Rules
**The No Fake Italic Rule.** Cairo has no italic, so `font-style: italic` renders a synthesized oblique. Mark secondary text with tone or size instead.

**The Steady Digits Rule.** Digits stay Western (they sit next to Latin paths and IDs). Counts, the nav badge, pagination, library stats, rescan progress and similarity scores use `font-variant-numeric: tabular-nums`, so they don't jitter while updating.

**The Isolated Latin Rule.** Paths, file extensions, tokens and chat IDs are wrapped in `<bdi>` or set `dir="ltr"`, so the bidi algorithm never reorders them inside Arabic prose.

## Layout

A single centred column (max 1400px, 2rem padding; 1rem on phones). The review queue is a grid of cards (min 400px columns) that collapses to one column on phones, ready cards first and needs-review cards last. The library has an unboxed page header (title, a stats line, select and rescan), then one browse panel (four tabs, then search and sort on one row), then a list or album grid. A fixed selection bar appears at the bottom in multi-select mode.

**The Sticky Minimum Rule.** Only what you need while scrolling sticks: the library's browse panel (about 130px) and, on phones, the queue's ready bar. Page headers, stats and notices scroll away.

**The One Way In, One Way Out Rule.** Multi-select has one entry (the «تحديد متعدد» toggle, `aria-pressed`, fixed label) and one labelled exit («إنهاء التحديد» in the selection bar). In selection mode the whole track card is the toggle and the checkbox shows its state; no per-card select buttons.

Breakpoints: 768px (tablet adjustments) and 600px (phone: stacked nav, full-width fields, genre chips in rows of three, small artwork beside the source line, 44px touch targets).

Spacing follows the 0.5 / 0.75 / 1 / 1.5 / 2rem scale; card internals mostly use `md` between groups and `xs`–`sm` inside a group.

## Elevation & Depth

**Direction: flat, tonal layers.** Depth comes from the navy steps (Night Ink → Archive Navy → Shelf Navy → Lamp Navy) and 1px Seam borders. Shadows belong only to things that float above the page: modals, dropdown suggestion lists, the selection bar.

Nothing lifts on hover. Cards, album cards and buttons answer hover with a tonal step (Lamp Navy background or Signal Blue border); filled buttons brighten (`filter: brightness(1.08)`) and dim slightly when pressed. The old hover lift, confirm glow and card top bar were removed in B6.

### Shadow Vocabulary
- **Overlay** (`0 12px 24px rgba(0,0,0,0.35)`): modals and floating panels.
- **Dropdown** (`0 4px 16px rgba(0,0,0,0.35)`): suggestion lists.
- **Focus ring** (`0 0 0 3px rgba(74,158,255,0.1)`): input focus, paired with a Signal Blue border.

### Named Rules
**The Flat-At-Rest Rule.** Surfaces don't cast shadows at rest. Only overlays float.

## Motion

**Direction: motion reports what happened to a file.** It never decorates. The operator goes through dozens of cards in a row, so routine motion is short and nothing waits on it.

| Token | Value | Use |
|---|---|---|
| `--dur-fast` | 150ms | hover, focus, chip selection |
| `--dur-base` | 200ms | routine state change, card exit |
| `--dur-enter` | 240ms | a new card arriving, cards closing a gap |
| `--ease-out` | `cubic-bezier(0.16, 1, 0.3, 1)` | arrivals and settling |
| `--ease-in` | `cubic-bezier(0.4, 0, 1, 1)` | exits |

- **A file leaves the queue** (confirmed, moved to the trash, or gone from the server): its card fades and rises 8px (`card-leave`, 200ms, ease-in). Then the cards after it slide into the gap from their old positions (FLIP via the Web Animations API, transform only, 240ms). This is the product's one authored motion.
- **A file arrives** (SSE or poll, never on page load): the card fades up 8px (`card-arrive`). Its border starts Signal Blue and fades to Seam over 1.2s (`card-arrive-mark`), so a new file can still be found after the slide ends.
- **A ready card opens** (phone): the fields fade in where they are (`card-reveal`). The height is not animated.
- **Saving:** the confirm button's slow sweep (`confirm-sweep`). The rescan icon spins.
- **The queue empties** after the last card leaves: the empty state fades in and a Settled Teal check draws once inside the tray (`check-draw`, 420ms). Revisiting the page shows it still.

### Delight, kept to outcomes
The only two "moments" report what really happened, in the product's words:
- **Queue cleared:** «اكتملت المراجعة», with how many files went to the library since the page was opened, and «افتح المكتبة». With nothing confirmed yet it stays neutral: «لا ملفات في الانتظار», an empty muted tray, and no check.
- **Confirm-all summary:** names where the files went: one folder «إلى مجلد «…»», two or three by name, more as a count («إلى 5 مجلدات في المكتبة»). A single confirm names its folder too. The folder is read from the server's `new_path`.
No celebration beyond this: no confetti, no sound, no streaks.

### Named Rules
**The Explained Change Rule.** Every animation names a change of state: arrived, left, opened, saving. A card that didn't change doesn't move. Rebuilding the list must never replay an entrance.

**The Named Property Rule.** Transitions list their properties. No `transition: all`, and no animation of layout properties (width, height, padding, margins, top/left).

**The Still Under Reduced Motion Rule.** With `prefers-reduced-motion: reduce`, the fades stay (they still say "this changed") and all movement goes: no translate, no FLIP slide, no sweep, no spin. `app.js` reads the same media query.

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

**Collapsed (phones, ≤600px):** a complete scanner suggestion (`pending`, with title, artist and genre) shows only a summary (title; artists · genre; destination path) with an «تعديل» tag, plus the real confirm button. Tapping the summary opens the full card for good. Cards that need review, or that the operator has opened, never collapse. A sticky ready bar («N من M جاهزة» + confirm-all) sits at the bottom of the queue on phones and replaces the toolbar's confirm-all.

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
- **Don't** animate a card that didn't change state, and don't lift anything on hover (see The Explained Change Rule).
- **Don't** give a signal colour a second meaning (see The One Meaning Rule).
- **Don't** add shadows to surfaces at rest (see The Flat-At-Rest Rule).
