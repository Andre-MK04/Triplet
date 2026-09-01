# Triplet Design System

The web app calls its own look **"Triplet Editorial Instrument"** — the visual
language of a flight departure board crossed with a printed boarding pass:
flat surfaces, hairline rules, monospace small-caps labels, sharp corners on
structure and round corners only on things that are literally round (dots,
pills, avatars). No glassmorphism, no drop shadows, no gradients except one
deliberate text treatment. This document is the source of truth for that
system so it can be reproduced in Stitch for the iOS app — read it top to
bottom before generating screens, then treat every token here as fixed and
every layout note as a pattern to reuse, not a one-off.

Source of truth in the repo: `apps/web/app/globals.css` (tokens),
`apps/web/tailwind.config.ts` (Tailwind mapping), `apps/web/components/ui/`
(Button, Badge, Misc).

---

## 1. Design principles

1. **Instrument, not brochure.** The UI reads like a departure board or a
   ticket stub — informational, slightly technical, confident about numbers.
   Not a glossy travel-brand landing page.
2. **Flat surfaces, no elevation.** Hierarchy comes from **surface steps**
   (a ladder of near-black/near-white tones) and **hairline borders**, never
   from box-shadow or blur. `boxShadow` tokens in Tailwind config are kept
   for compatibility but resolve to `none`.
3. **Sharp by default, round on purpose.** Cards, buttons, inputs, badges: 0
   radius (`rounded-none` / `rounded-card: 0`). Round shapes are reserved for
   things that are conceptually circular or pill-shaped: radio bullets,
   avatar dots, the boarding-pass notches on a card's edge, loading spinners,
   and small circular tag pills. If in doubt, keep it square.
4. **Type does the work color usually does.** Monospace, uppercase, tracked
   labels mark *metadata* (dates, counts, categories, statuses) everywhere in
   the app. Display serif-adjacent grotesque marks *headlines and prices*.
   Sans carries body copy. This three-way split is the single most
   recognizable trait of the system — keep it strict.
5. **Honesty about data freshness is a design material, not just copy.**
   Price confidence (fresh/recent/aging/stale/unknown) and price kind
   (observed vs. estimated) are always visually marked — via badge tone,
   secondary caption text, or both. Never present a number without a
   freshness signal somewhere near it.
6. **Texture, not decoration.** A ~2–2.5% monochrome film-grain sits over the
   entire app (`body::after`, inline SVG turbulence) so flat color fields
   don't read as sterile. This is the only ambient effect in the system.
7. **Motion is restrained and physical.** Framer Motion drives small
   lift/settle transitions (hover raises a card 4px, layout animates), never
   decorative loops. Respect `prefers-reduced-motion` everywhere — motion
   durations should collapse to ~0 when it's set.

---

## 2. Color system

Color is **theme-aware by design**, not an afterthought: dark is the default
theme, light is a full parallel palette, and every token must be legible in
both. Colors are stored as space-separated RGB channels (so alpha modifiers
work) except pre-baked translucent tokens, which are full `rgba()`.

### 2.1 Dark theme (default)

| Token | RGB | Hex | Role |
|---|---|---|---|
| `ink` | 11 17 23 | `#0B1117` | Page background (base) |
| `ink-soft` | 14 20 26 | `#0E141A` | Sunken surface (e.g. inset rows) |
| `ink-raised` | 22 28 34 | `#161C22` | Card / raised surface |
| `panel` | 26 32 39 | `#1A2027` | Panel surface, one step up |
| `lifted` | 37 43 49 | `#252B31` | Highest surface step |
| `deep` | 9 15 21 | `#090F15` | Deepest well (below page base) |
| `cloud` | 232 240 244 | `#E8F0F4` | Primary text |
| `mist` | 147 166 180 | `#93A6B4` | Secondary / muted text |
| `mint` | 125 223 195 | `#7DDFC3` | Primary action color, FitScore accents |
| `mint-ink` | 0 56 44 | `#00382C` | Text color placed on a solid mint fill |
| `sky` | 142 197 255 | `#8EC5FF` | Secondary accent (info, open-jaw) |
| `coral` | 255 154 120 | `#FF9A78` | Prices-in-danger / warning accent — **reserved for prices and warnings only** |
| `gold` | 255 208 138 | `#FFD08A` | DealScore accent, caution notices |
| `line` | rgba(232,240,244,0.15) | — | Hairline border color |
| `mint-soft` | rgba(125,223,195,0.12) | — | Tinted background for mint badges |
| `sky-soft` | rgba(142,197,255,0.12) | — | Tinted background for sky badges |
| `coral-soft` | rgba(255,154,120,0.14) | — | Tinted background for coral badges |

### 2.2 Light theme

| Token | RGB | Hex | Role |
|---|---|---|---|
| `ink` | 247 249 251 | `#F7F9FB` | Page background |
| `ink-soft` | 238 242 246 | `#EEF2F6` | Sunken surface |
| `ink-raised` | 255 255 255 | `#FFFFFF` | Card surface |
| `panel` | 255 255 255 | `#FFFFFF` | Panel surface |
| `lifted` | 240 243 247 | `#F0F3F7` | Highest surface step |
| `deep` | 230 235 240 | `#E6EBF0` | Deepest well |
| `cloud` | 15 23 32 | `#0F1720` | Primary text |
| `mist` | 90 107 120 | `#5A6B78` | Secondary text |
| `mint` | 15 138 111 | `#0F8A6F` | Primary action (darkened so it stays legible as text *and* a button fill) |
| `mint-ink` | 255 255 255 | `#FFFFFF` | Text on solid mint fill |
| `sky` | 37 99 176 | `#2563B0` | Secondary accent |
| `coral` | 199 74 42 | `#C74A2A` | Warning / price accent |
| `gold` | 146 100 0 | `#926400` | DealScore accent |
| `line` | rgba(11,17,23,0.14) | — | Hairline border |
| `mint-soft` / `sky-soft` / `coral-soft` | 0.10 / 0.10 / 0.10 alpha versions | — | Tinted badge backgrounds |

**Rule for porting to a new theme or platform:** never invert dark→light by
flipping lightness alone. Mint, sky, coral, and gold are independently
re-tuned per theme to keep contrast and "does this still look like an accent"
correct — light-theme mint is a materially different, darker hue than
dark-theme mint, not just a lightness flip.

### 2.3 Color usage rules

- **Mint** = primary action + the FitScore family. Solid mint fill only for
  the single highest-priority action per screen (e.g. "Check live price").
- **Gold** = DealScore only, plus mild caution notices/warnings inside
  expanded card details. Don't reuse gold as a generic "warning" everywhere —
  it's specifically tied to the deal-quality metaphor.
- **Coral** = prices in a negative/stale context, and hard warnings
  (destructive button variant, price-may-have-changed states). Never used
  decoratively.
- **Sky** = secondary informational accent — open-jaw trip badges, "info"
  notices, secondary data.
- **Mist** = all secondary text: captions, timestamps, hints, sub-labels.
- Badge tones map 1:1 to these five hues plus `neutral` (translucent white).
  Reuse the same tone vocabulary for any new status concept rather than
  inventing new hues.

---

## 3. Typography

Three families, three jobs — do not blur them:

| Role | Family | Tailwind token | Used for |
|---|---|---|---|
| Display | **Bricolage Grotesque** (400/500/700/800) | `font-display` | Headlines, section titles, prices, big numbers |
| Body | **Hanken Grotesk** (400/500/600/700) | `font-sans` (default) | Paragraphs, form labels, buttons' visible text where not mono |
| Mono | **JetBrains Mono** (400/500/600) | `font-mono` | Uppercase tracked labels, badges, timestamps, buttons, anything "instrument panel" |

Both are loaded via `next/font/google` — on Stitch/mobile, load the same two
Google Fonts (Bricolage Grotesque, Hanken Grotesk, JetBrains Mono) or embed
them; do not substitute system fonts.

### 3.1 The "ui-label-caps" pattern (signature move)

The single most repeated typographic treatment in the app — use it for *every*
metadata label, eyebrow, section kicker, and tab/segment label:

```
font-mono text-[10px–11px] font-semibold uppercase tracking-[0.12em] text-mist
```

- Size: 10px for tertiary captions, 11px for primary labels/eyebrows.
- Always uppercase, always mono, always tracked (`letter-spacing: 0.12em`,
  Tailwind token `tracking-label`).
- Color is `text-mist` by default; `text-mint` when it's an active/emphasis
  eyebrow (e.g. "Methodology", section kickers); `text-coral` for error
  labels.

### 3.2 Scale

- Hero / page display numbers: `font-display text-3xl–4xl font-bold
  tracking-tight` (SectionHeading uses `text-3xl sm:text-4xl`).
- Card title: `font-display text-lg font-bold`.
- Price headline on a card: `font-display text-2xl font-bold text-mint`.
- Body copy: `text-sm` / `text-base`, `leading-relaxed`, color `text-mist` for
  secondary, `text-cloud` for primary.
- Buttons: mono, uppercase, tracked, sizes `text-[11px]` (sm and md) /
  `text-xs` (lg) — see §5.
- **11px is the floor for anything meaningful or interactive.** Fare age,
  warnings, watch status, dates, price explanations, legal text and every
  button label sit at 11px or above. 10px is reserved for genuinely secondary
  chrome: field labels beside their values, footer legal lines, section
  eyebrows. Nothing in the interface is below 10px.
- Numbers that align in a column or represent a live metric get
  `font-variant-numeric: tabular-nums` (`.mono-num` utility class).

---

## 4. Surfaces, borders, radius

- **No rounded corners on structural elements.** Cards (`rounded-card` = 0),
  buttons (`rounded-none`), badges (`rounded-none`), inputs (`.cmd-input` has
  `border-radius: 0`).
- **Round corners only for genuinely circular things**: radio bullets (see
  §6.3), the two boarding-pass "notches" cut into the side of a `TripCard`
  (`rounded-full`, positioned `absolute -left-2/-right-2`, filled with the
  page background color to fake a punch-hole), small status dots, avatar
  circles, the loading spinner ring. Occasional small inner panels use
  `rounded-xl` (e.g. a nested "flight row" inside a card) — treat this as the
  one permitted soft-radius exception for a sub-panel embedded inside a
  sharp-cornered card, not a default.
- **Elevation is a border + surface-step, never a shadow.** A card
  (`ink-raised`) sits on the page (`ink`) with a 1px `border-line` hairline —
  that's the entire elevation vocabulary. `box-shadow` tokens exist in config
  but are set to resolve to nothing.
- **Dividers**: solid 1px `border-line` for structural separation; **dashed**
  1px `border-line` specifically for a ticket/boarding-pass-style tear line
  (e.g. the footer divider inside `TripCard`, separating "why this works"
  actions from the CTA). Use dashed borders sparingly and only where the
  ticket metaphor applies.
- **Grain**: apply a fixed, full-viewport, ~2–2.5% opacity monochrome noise
  overlay above all content (pointer-events none) so flat surfaces don't look
  sterile. On iOS this can be a single tiled noise image or a Core Image
  noise filter at ~2% opacity, blend mode normal, non-interactive.

---

## 5. Buttons

Four variants × three sizes. All buttons: mono, uppercase, tracked, sharp
corners, no shadow.

```
base: inline-flex items-center justify-center gap-2, rounded-none,
      font-mono font-semibold uppercase tracking-[0.12em],
      focus ring: 2px mint outline, 2px offset
```

| Variant | Style |
|---|---|
| `primary` | Solid mint fill, `mint-ink` text, `hover:opacity-90` |
| `secondary` | Transparent fill, 1px `border-line`, `text-cloud`; hover → mint-tinted border + mint text |
| `ghost` | No border/fill, `text-mist`; hover → `text-cloud` |
| `danger` | Transparent fill, 1px coral border at 40% alpha, coral text; hover → faint coral background |

| Size | Padding | Font size |
|---|---|---|
| `sm` | `px-3.5 py-2` | 11px |
| `md` | `px-5 py-2.5` | 11px |
| `lg` | `px-7 py-3.5` | 12px (`text-xs`) |

Disabled state: `opacity-50`, cursor not-allowed, no other treatment.

The single primary CTA per trip card is **"Check live price ↗"** — always
solid mint, always paired with an external-link arrow glyph, always the
visually heaviest thing on the card. This is deliberate: Triplet finds
candidates, the provider confirms the fare, and the button language must
never imply Triplet itself is booking or guaranteeing the price.

---

## 6. Core components (reproduce these exactly)

### 6.1 Badge

Pill-less, rectangular, bordered tag used for score badges, freshness/price
badges, trip-type tags, country/continent tags.

```
inline-flex items-center gap-1, rounded-none, border,
px-2 py-0.5, font-mono text-[10px] font-semibold uppercase tracking-[0.08em]
```

Tone table (background/text/border, using the `-soft` background tokens):

| Tone | Use |
|---|---|
| `mint` | Deal score, "fresh" price, live/positive states |
| `sky` | Cached price, open-jaw tag, informational |
| `coral` | Fit score low, stale price, warnings |
| `gold` | Mid-range fit score |
| `neutral` | Generic tags — country, continent, trip attribute (white/5% bg, `text-mist`, `border-line`) |
| `live` / `cached` / `demo` | Explicit price-provenance badges (alias mint/sky/neutral respectively) |

### 6.2 TripCard — the "boarding pass" card

This is the flagship component; reproduce its structure faithfully as the
mobile trip-result cell:

- Sharp-cornered card (`ink-raised` surface, 1px `line` border, ~20px
  padding), no shadow.
- **Two circular notches** cut into the left and right edges at vertical
  center (`rounded-full`, filled with the page background color) — the
  boarding-pass punch-hole illusion. On mobile, keep this if cards run
  full-bleed; drop it gracefully if cards have visible page margin on both
  sides (the illusion needs the card to look "torn from a strip").
- **Header row**: route title left (`font-display text-lg font-bold`,
  "City → City" using full city names + IATA codes in muted color), price
  block right-aligned (`font-display text-2xl font-bold text-mint` headline +
  small mist caption stating what the total covers).
- **Badge row**: deal score, fit score, freshness/confidence badge, trip-type
  tag (e.g. "Open-jaw"), up to 3 content tags — all using the Badge component,
  wrapped, small gap.
- **Flight rows**: one inset row per leg (`ink-soft/60` background,
  `rounded-xl` — the one soft-radius exception, `px-3.5 py-2.5`), each showing
  a mono-caps label ("Outbound"/"Return"), route with muted IATA codes, a
  small mint arrow glyph between airports, date/time/duration/stops line, and
  airline name in dimmer mist. Ground-transfer legs (train/bus between
  itinerary cities) render as a single centered gold-colored line with a
  transport emoji, cost, and duration — never priced into the flight total.
- **Expandable details** (`ink-soft/40` bordered panel): plain-language
  explanation, warnings (gold, prefixed with ⚠️), open-jaw self-transfer
  notice, a two-column score breakdown (label vs. signed point delta, mint
  for positive / coral for negative), and a closing freshness disclaimer line
  ("Last checked Xh ago. Prices are observed, not guaranteed…").
- **Footer**: a *dashed* top hairline separates it from the body (the
  tear-line motif). Left: text links "Why this works" (sky) and "Open →"
  (mist). Right: secondary "Save alert" button + the primary mint "Check live
  price ↗" pill-shaped-corner-free button (or a muted note if no booking link
  exists, e.g. demo data).
- Hover (non-touch only): whole card lifts 4px on Y with a spring transition;
  skip on touch devices / respect reduced motion.

### 6.3 Radio / trip-shape chooser

Custom circular radio bullets (never native OS radios):

- Native `<input type="radio">` visually hidden (`sr-only`), a sibling
  `span` renders a 16px circle, 1px border (`border-line` unselected →
  `border-mint` selected), with an inner 8px filled mint dot that scales in
  from 0 when selected (`scale-0` → `scale-100` transition).
  Focus-visible gets a 2px mint ring with 2px offset.
- Label text: `text-sm font-medium`, `text-mist` unselected → `text-cloud`
  selected; a `text-xs text-mist/70` hint line underneath each option.
- Options laid out as a horizontal wrapped group with generous gap, not a
  vertical stack — reads as a segmented choice, not a form list.
- **Default selection matters as content, not just code**: the "safest,
  simplest" option (direct return) is listed first and pre-selected; anything
  requiring more commitment (multi-city, open-jaw) requires an explicit
  choice.

### 6.4 SectionHeading / EmptyState / Notice (ui/Misc)

- **SectionHeading**: centered, max-width ~2xl. Optional mint mono-caps
  eyebrow above a `font-display text-3xl/4xl font-bold tracking-tight`
  title, optional mist body copy below.
- **EmptyState**: no illustration — a horizontally-ruled block (`border-y
  border-line`, generous vertical padding) containing a centered
  `font-display text-2xl font-bold` title, optional mist body, optional
  action button. Typographic, not decorative — keep this discipline on
  mobile too (a ruled block, not a cute mascot illustration).
- **Notice**: a quiet inline message, not a boxed alert — transparent
  background, 2px solid left rule in the tone color, `text-sm`, tone colors:
  info=sky, warning=gold, error=coral, success=mint.

---

## 7. Motion

- Library equivalent to reach for on iOS: `UIView.animate` / SwiftUI
  `.animation` with a spring, matching Framer Motion's defaults used here
  (subtle, springy, short).
- Card hover/press: translate up ~4px (or scale ~1.01 on touch-press-down)
  — hover doesn't exist on touch, so translate this into a **press** state
  instead (scale down slightly on touch-down, spring back on release).
  For scroll appearance, use a lightweight fade-up (`opacity 0→1`,
  `translateY(14px→0)`, ~0.6s ease) — the app's `fade-up` keyframe.
  Reduced-motion equivalent: instantly present, no fade/translate.
- Route lines in map/globe visuals animate as dashed strokes marching
  (`stroke-dasharray: 6 6`, offset animating continuously, 2.4s linear loop)
  — reproduce this for any route/flight-path visualization on mobile.
- Respect the OS "Reduce Motion" setting exactly the way the web app respects
  `prefers-reduced-motion`: collapse all animation durations to near-zero
  rather than removing the end states.

---

## 8. Price & freshness communication (content design, not just visuals)

This is a hard content constraint carried over from the backend price model —
get it right in Stitch mockups, because it is a legal/trust requirement, not
a style preference:

- **Never show a bare number as if it were a live, bookable price.** Every
  price headline is prefixed with a qualifier: `"from €X"` (observed fare),
  `"Estimated from €X"` (sum of separately-observed legs), or `"recently from
  €X"` (aging/stale fare, price may have moved).
- **Every price has a freshness state** — `fresh | recent | aging | stale |
  unknown` — and it should be visually recoverable from the card (badge tone
  and/or a caption line like "Found 14h ago" / "Found yesterday" / "Price may
  have changed").
- **Estimates are explicitly labeled** as sums of multiple observed legs
  ("3 flights priced separately") rather than presented as a single verified
  fare.
- **A "great deal" badge** ("Below typical price" style label) only appears
  when there's enough historical data to be statistically confident — it
  carries a tooltip/explanation naming the typical observed range. Don't
  invent a deal badge without backing data on mobile either.
- **The CTA is always "Check live price"**, never "Book now" / "Reserve" /
  anything implying Triplet itself transacts or guarantees availability.

---

## 9. Layout conventions

- Central content column: `max-w-2xl` for reading-width sections (headings,
  prose), wider grids for card lists.
- Generous section padding — vertical rhythm built from `py-10`–`py-16` on
  ruled sections rather than tight stacking.
- Cards in a results list: single column on narrow viewports, comfortable
  vertical gap (not touching) — the boarding-pass notch effect needs a little
  breathing room around each card to read as "torn from a strip," so avoid
  edge-to-edge full-bleed cards with zero gap on mobile.
- Sticky/persistent elements (search bar, filter bar) keep the flat-surface +
  hairline-bottom treatment — never add a shadow to fake a sticky header;
  a 1px `border-line` bottom edge is sufficient separation.

---

## 10. What to avoid

- Rounded cards, rounded buttons, rounded inputs (unless it's the specific
  documented exception in §4).
- Any drop shadow, glow, or blur-based elevation.
- Gradients, except the one signature `text-gradient` treatment (mint → sky
  → coral, 96deg) reserved for a single hero headline moment — don't spread
  it across UI chrome.
- Native OS toggle/radio/checkbox styling left unstyled — always the custom
  mono-label + circular-bullet treatment from §6.3.
- Presenting any fare as guaranteed, live, or bookable-through-Triplet
  language.
- Icon-heavy empty states, mascots, illustrations — the system is
  typographic and ruled, not illustrative.
