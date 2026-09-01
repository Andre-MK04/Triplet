# Triplet — iOS App Flow for Stitch

Companion to [`design.md`](design.md). That file is the visual system
(tokens, components, rules). This file is the **screen-by-screen map** and
the **exact UI/UX and animation instructions** to feed Stitch, one screen at
a time, so the mobile app reproduces the web app's actual flow rather than a
freehand reinterpretation.

**How to use this with Stitch:** work through §2 in order. For each screen,
give Stitch (a) the screen's purpose and content from this doc, and (b) a
reminder to apply `design.md` in full (colors, type, radius rules, badge/
button components) — don't restate the whole design system every time, just
say "apply the Triplet Editorial Instrument system from design.md" and add
the screen-specific notes below. Generate screens roughly in flow order so
Stitch can carry visual continuity (its own generated components) forward
from one screen to the next instead of reinventing them.

---

## 1. Global UI/UX instructions (apply to every screen)

Give Stitch these as standing rules before generating anything, so they don't
need repeating per-screen:

- **Navigation shell**: a bottom tab bar, not the web's top nav. Four tabs
  for a signed-in user: **Discover** (search icon or the → glyph used on
  web), **My World** (globe), **Dashboard** (bell/watch icon), **Account**
  (person). Tab bar uses the flat-surface + hairline system: `ink-raised`
  background, a single 1px `border-line` top edge, no shadow. Active tab:
  mint icon + mint mono-caps label. Inactive: `mist` icon + label. No pill or
  background highlight behind the active tab — color change only, consistent
  with "no elevation, ever."
- **Top of screen**: no floating/blurred nav bar. Screen titles are plain
  in-content `font-display` headers that scroll with the content, the same
  way `discover`'s `<h1>` scrolls in the web app. A **thin hairline** at the
  very top separates the status bar area from content only when content is
  scrolled (i.e., appears on scroll, not a permanent chrome bar) — like the
  web navbar's `border-b border-line` but appearing only once there's
  something to separate from.
- **Safe areas / spacing**: generous vertical rhythm, ruled sections
  (`border-t border-line` between stacked sections) rather than cards nested
  in cards. Content padding ~20px horizontal, consistent throughout.
- **Every screen respects Reduce Motion**: instructed per-animation below,
  but as a blanket rule — any transition described as having a duration
  becomes instant when the OS setting is on.
- **Every price shown anywhere in the app carries a freshness cue** — see
  `design.md` §8. Never let Stitch generate a bare "€214" with nothing else.
- **Haptics** (note for Stitch's prototype interactions where supported):
  light impact on selecting a radio bullet or toggling a chip, medium impact
  on primary CTA press (Search, Save alert, Check live price), success
  notification haptic on save/confirmation screens.
- **Pull-to-refresh** on any scrollable list screen (Discover results,
  Dashboard, My World) uses a minimal custom refresh indicator: a thin mint
  arc that fills like the ScoreDial component, not the OS spinner — reinforce
  the instrument-panel identity even in system-provided moments.

---

## 2. Screen-by-screen flow

### Flow overview

```
Launch
 └─ [not signed in] → Landing → Sign up / Log in → Onboarding (10 steps) ──┐
 └─ [signed in]     → Discover (home tab)                                  │
                                                                            ▼
                                                              Discover (home tab)
                                                                    │
                                        ┌───────────────────────────┼───────────────────────────┐
                                        ▼                           ▼                           ▼
                                Results list                 Save-alert sheet            Refine sheet
                                        │
                                        ▼
                              Trip Detail (boarding pass)
                                        │
                                        ▼
                              Check live price → external browser

Tab bar (signed in): Discover · My World · Dashboard · Account
```

---

### 2.1 Launch / Splash

**Purpose:** brief brand moment while auth state resolves.

- Full-bleed `ink` background with the grain texture already active.
- Center: the Triplet wordmark (`font-display`, bold) with the small
  route-mark glyph from the web navbar (`TripletMark`), no spinner visible
  unless load exceeds ~800ms.
- **Animation**: wordmark fades/scales in very subtly (opacity 0→1, scale
  0.98→1, ~400ms ease-out) — no bounce, no logo animation loop. This is a
  threshold, not a moment to linger on.

---

### 2.2 Landing (signed-out home)

Mirrors `app/page.tsx`. Purpose: pitch the product and route to sign-up/login
before any search happens.

**Content, top to bottom:**
1. **Hero**: headline making the core promise (worldwide flight-deal
   discovery from your home airports), a short subhead, primary CTA
   "Get started" (mint, `lg`), secondary "Log in" (ghost).
2. **Live departures strip**: a horizontally-scrollable row of real cached
   deal cards, presented as **compact boarding-pass ticket stubs** (see
   `design.md` §6.2, condensed) — route, price with freshness caption, deal
   score badge. This is the same `useLiveDeals` data source as web; use
   placeholder/real-shaped data in Stitch.
3. **How it works**: 3-step ruled list (mono-caps numbered eyebrows are
   *not* used here since these aren't a real sequence in the data sense —
   use plain section headings instead per `design.md` §10's numbering
   caution... actually this *is* a real sequence, so numbered steps are
   appropriate here specifically).
4. **Methodology / trust section**: short copy on how prices are sourced,
   linking to the freshness/estimate honesty language from `design.md` §8.
   Mint eyebrow "Methodology".
5. Footer-equivalent: legal links (Privacy, Terms), sparse.

**Animation:**
- Hero content reveals with the `Reveal` pattern used on web: `opacity 0→1,
  translateY 22px→0`, `0.55s ease-out`, triggered once as each section
  scrolls into view (not on load) — a staggered ~80–120ms delay between
  hero sub-elements (headline → subhead → CTA).
- The departures strip auto-scrolls very slowly (a marquee, pausable on
  touch) — optional nice-to-have, skip if it complicates the prototype.

---

### 2.3 Sign up / Log in

Two screens, same shell. Simple, no-frills instrument-panel form.

**Content:**
- `font-display` title ("Create your account" / "Log in").
- Email field, password field — both using the flat underline `.cmd-input`
  treatment from `design.md` (no boxed input, just a hairline that turns
  mint on focus), **not** a rounded bordered box. This is a deliberate
  departure from typical iOS form fields — keep it.
- Primary button, full-width, mint, `lg`.
- OAuth option(s) as `secondary` buttons below a thin "or" divider (hairline
  + centered mono-caps "OR").
- Switch-mode link at the bottom ("Don't have an account? Sign up") in
  `text-sm text-mist`, mint on the actionable word.
- Forgot-password link under the password field on Log in, `text-xs text-mist`.

**Animation:**
- Field focus: bottom hairline animates color `line → mint` over ~200ms
  ease, exactly matching `.cmd-input:focus` on web. No label float animation,
  no box glow.
- Form submit error: a `Notice` (tone error, coral left rule) fades/slides in
  above the button, `opacity 0→1` + `translateY -4→0`, ~200ms.
- Successful submit: button label swaps to "Signing in…" (no spinner icon
  inside the button — text-only state change, matching web's `isLoading`
  pattern), then screen transitions to Onboarding or Discover with a
  standard push transition (system default is fine — don't over-animate
  auth transitions).

---

### 2.4 Onboarding (10-step wizard)

Mirrors `app/onboarding/client.tsx` closely — this is one of the most
distinctive flows in the app and should be reproduced faithfully.

**Structure (applies to all 10 steps):**
- **Top progress**: mono-caps label "Travel profile" left, step counter
  right as `mono-num` "03 / 10" — both `text-[10px] uppercase tracking-label
  text-mist`. Below that, a **segmented progress bar**: N thin horizontal
  bars in a row (`h-0.5`, small gap), each filled mint if `index <= step`,
  else `line` gray. Not a single continuous progress bar — segmented,
  because it reads as a literal step counter.
- **Body**: `font-display text-3xl font-bold` step title, `text-sm text-mist`
  subtitle beneath, then the step's specific input content.
- **Footer**: hairline top border, "← Back" ghost button left (disabled on
  step 1), primary button right — "Continue →" on steps 1–9, "Start watching
  fares" on step 10 (final commit language, not just "Finish").

**The 10 steps in order (content):**
1. **Where are you based?** — free-text city/town input (autocomplete),
   powers airport recommendations.
2. **How far would you travel to an airport?** — a distance slider (uses the
   flat range-input styling from `design.md`: 2px track, 10×22px sharp mint
   thumb, no rounded slider track).
3. **Recommended origin airports** — a list of nearby airports as **chips**
   (`Chip` component: bordered, sharp corners, toggled state fills mint),
   preselected chips already "on".
4. **Add any other airports** — search/autocomplete to add more airport
   chips manually.
5. **What kind of trips do you want?** — multi-select chips (city breaks,
   nature, food, nightlife, etc. — whatever tags the backend uses), "pick as
   many as you like."
6. **How long is your ideal trip?** — a min/max dual-range control for trip
   length in days.
7. **How do you feel about price?** — single-select radio-style choice
   between budget comfort zones (under €100/€200/€400/flexible) — reuse the
   TripPlanChoice circular-bullet pattern from `design.md` §6.3 for this,
   since it's the same "pick one path" interaction shape.
8. **How spontaneous are you?** — single-select (e.g. "I plan months ahead"
   → "I go whenever"), same circular-bullet treatment.
9. **Any comfort rules?** — a short list of toggleable preferences (e.g. "no
   red-eye flights"), each with a small three-state affordance if the web
   version distinguishes "Require" vs. "Prefer" — otherwise a simple toggle
   list is fine.
10. **How should we tell you about deals?** — notification frequency
    choice + the terminal CTA "Start watching fares".

**Animation (important, distinctive):**
- Step transitions are **horizontal slide + fade**, direction-aware: moving
  forward (Continue) slides the new step in from the right while the old
  one exits left; moving backward reverses it. Exact values to match web:
  incoming `opacity 0→1`, `translateX ±46px → 0`; outgoing mirrors it exiting
  to the opposite side. Duration ~300ms, ease-out. This directionality is
  the single most important animation detail on this screen — don't let
  Stitch default to a plain crossfade.
- Progress bar segments animate their fill color with a quick color
  transition (~200ms) when a step completes, not an instant snap.
- Validation: primary button is simply disabled (50% opacity, per
  `design.md` button rules) until the step's answer is valid — no shake
  animation on invalid submit attempts, since the button can't be pressed
  in the first place.

---

### 2.5 Discover (home tab, signed-in default screen)

Mirrors `app/discover/client.tsx`. This is the core screen — the single
unified search.

**Content, top to bottom:**
1. Header: `font-display text-3xl font-bold` "Discover trips" + one-line
   `text-mist` subhead.
2. **The search block**, ruled top and bottom (`border-y border-line`,
   generous vertical padding):
   - A **free-text describe-your-trip box**: multiline text area, `font-mono`
     text, prefixed with a mint `→` glyph aligned to the first line — this
     glyph is a signature visual detail, keep it. Placeholder text changes
     based on the selected trip shape (see below).
   - **"Your selected origin airports" control**: a compact button/row
     showing the currently selected airport chips (2–6 shown, "+N more" if
     more), tapping opens a sheet to add/remove airports (search + chip
     toggle, same chip pattern as onboarding).
   - **Trip-shape chooser**: the three circular-bullet radio options —
     Return (default, first) / Multi-city / Open-jaw — exactly as documented
     in `design.md` §6.3. Selecting Multi-city or Open-jaw reveals a short
     contextual hint line (mint left-border, small text) explaining what to
     type — e.g. "Name the cities in order" vs. "Say where you fly in and
     where you fly home from."
   - **"Find trips" primary button**, full-width or right-aligned on tablet
     width, disabled until at least one origin airport is selected. Label
     swaps to "Searching…" while loading (text-only state, no spinner
     inside button, matching the button convention already established).
   - A collapsible **"Dates, budget, destination +"** disclosure toggle
     (mono-caps, mist, mint on hover/press) — this expands an advanced
     panel: destination search/chips (city/country/region/continent, with
     "outside Europe" and "somewhere new" toggle checkboxes), date range,
     trip-length range, budget slider, direct-flights-only toggle. Keep this
     collapsed by default on mobile — don't ever pre-expand it.
3. **Results area** below the search block:
   - Loading state: a `Spinner` (thin mint spinning ring, matching
     `design.md`'s spinner spec) centered with a mono-caps "Searching…"
     label.
   - Empty state: the ruled typographic `EmptyState` block (§6.4 of
     `design.md`) — no illustration.
   - Results: a vertical list of `TripCard`s (the boarding-pass card, full
     spec in `design.md` §6.2) with comfortable gaps between them.
   - A **restored-search banner** may appear above results if returning from
     a Trip Detail screen: a `Notice` (info tone) stating results are from
     N minutes/hours ago with an option to re-search — this exists because
     re-running AI search costs money/quota, so returning to a prior result
     set is a deliberate, visible feature, not silent caching.

**Animation:**
- Advanced panel disclosure: height auto-animate with fade (`opacity 0→1`,
  `height 0→auto`), overflow hidden during the transition — matches web's
  `AnimatePresence` height animation exactly. No accordion "chevron rotate"
  needed if the button text itself changes ("... +" ↔ "... −").
- Results appearing after a search: cards fade/slide up in a light stagger
  (~40–60ms between cards, capped at first 5–6 to avoid a long stagger on
  big result sets) — `opacity 0→1`, `translateY 12px→0`, ease-out, ~350ms.
- Trip card hover-lift (§7 of `design.md`) becomes a **press** state on
  mobile: scale to ~0.98 on touch-down, spring back on release/tap-through
  to Trip Detail.
- Pull-to-refresh re-runs the last search (see global rule in §1).

---

### 2.6 Save Alert (sheet, from Discover)

Triggered from a "Save alert" button on a trip card or from a persistent
action after a search. Presented as a **bottom sheet**, not a full push —
this is a lightweight, secondary action.

**Content:**
- Sheet handle bar (thin, `line` color, sharp — not the default rounded iOS
  pill if it can be styled; otherwise accept the system default here since
  it's a system chrome element, not a Triplet-drawn one).
- Title: "Save this search" (`font-display`).
- Auto-filled name field for the alert (editable), showing the derived
  default name pattern from web (e.g. "VIE/ZAG/TRS under €600").
- Frequency choice (daily/weekly — likely another circular-bullet choice, or
  a simple segmented control if only 2 options).
- Primary "Save alert" button.
- Inline success/error `Notice` after submit, sheet auto-dismisses on
  success after a short delay (~900ms) or on explicit "Done" tap.

**Animation:** standard sheet present/dismiss (spring up from bottom,
system-native feel is appropriate here — sheets are one of the few places
where leaning on iOS system motion instead of a custom curve is correct,
since users have strong priors about how sheets behave).

---

### 2.7 Trip Detail

Mirrors `app/trip/[id]/client.tsx`. This is the "boarding pass, full size"
screen — the emotional payoff screen of the app, reproduce with real care.

**Content, top to bottom:**
1. Back navigation (standard, top-left).
2. **The Boarding Pass component**, full width, presented large:
   - Per-leg rows: a big `mono-num font-display text-4xl/5xl font-bold`
     departure time on the left, arrival time on the right, connected by a
     center column showing duration + stop count (mono-caps, tiny) above a
     thin horizontal line with a mint `→`. Below: date (bold, mono-caps) and
     airline name (muted). This grid-based, huge-digit time display is the
     boldest typographic moment in the whole app — Stitch should treat the
     departure/arrival times as the largest text on the entire screen,
     larger than the headline price.
   - A dashed divider between outbound and return legs, plus (for open-jaw)
     the ground-transfer note in gold with transport icon.
3. **Score dials row**: the two `ScoreDial` ring gauges — DealScore (gold
   ring) and FitScore (mint ring) — thin-stroke circular progress rings with
   the numeric value centered inside, small mono-caps label underneath each.
   These are literally the only two "big" circular shapes permitted by the
   design system (besides small dots/bullets) — make them a real visual
   moment: 60–80pt diameter, side by side.
4. **Price block**: total price headline with freshness qualifier
   ("Estimated from €X" / "from €X"), secondary caption with observed-time
   and/or estimate breakdown, per `design.md` §8.
5. **Why this works**: plain-language explanation text, plus warnings list
   (gold, ⚠️ prefix) if any, plus the score-factor breakdown (two columns:
   Deal score factors / Fit score factors, each a list of label + signed
   point delta in mint/coral) — this can be a disclosure ("Why this works ▾")
   rather than always-expanded on the smaller mobile viewport, unlike web
   where there's more room.
6. **Itinerary planner** (for multi-city/open-jaw trips): a vertical stepped
   list of stays (city, night count) — reuse the same visual language as the
   flight-leg rows (mono-caps labels, ruled separators) rather than inventing
   a new timeline widget.
7. **Sticky bottom action bar**: "Check live price ↗" as the solid mint
   primary button, pinned above the safe-area inset, hairline top border
   separating it from content (not floating/shadowed) — this should always
   be reachable without scrolling to the very bottom, since it's the whole
   point of the screen.

**Animation:**
- Screen entrance: standard push transition; once in, the score dials can
  animate their ring fill from 0 to their value on first appearance
  (`strokeDasharray` animating over ~700ms ease-out, slightly staggered
  between the two dials by ~100ms) — this is worth a deliberate moment since
  it's the payoff screen.
- Disclosure sections (Why this works, breakdown) expand with the same
  height+fade pattern as Discover's advanced panel.
- Tapping "Check live price" opens the booking URL in an in-app
  `SFSafariViewController` (not a full app-leave) — standard system
  presentation, no custom animation needed.

---

### 2.8 My World (tab)

Mirrors `app/world/*`. A globe-based visualization of the user's reachable
world / visited destinations.

**Content:**
- A 3D or stylized flat globe/map (the web version uses `RouteGlobe`, an
  interactive 3D globe with route arcs and price tags at destinations).
  For Stitch's mockup purposes this can be represented as a static
  illustrative globe artboard with labeled price-tag pins — the actual
  interactive 3D globe is a native-code concern, not something Stitch needs
  to fully simulate, but the **visual style of the pins/labels** should
  follow the system: small `Badge`-style price labels (sharp corners, mono,
  bordered) anchored to points on the globe, dashed **animated route lines**
  between origin and destinations per `design.md` §7.
- Below/around the globe: a filter or list toggle to switch to a flat list
  of visited/reachable countries or continents, styled as ruled rows (flag +
  country name + count of trips found there), not cards.

**Animation:**
- Route-line dash animation as specified in `design.md` §7 (marching dashes,
  continuous loop, 2.4s).
- Globe rotation/interaction: slow ambient auto-rotation when idle,
  responsive to drag — standard for a 3D globe, no special Triplet-specific
  easing needed here beyond "not too fast, feels like a real object."

---

### 2.9 Dashboard (tab)

Mirrors `app/dashboard/client.tsx`. Manage saved alerts/watches.

**Content:**
- List of saved searches/watches, each row showing: name, origin airports,
  budget, frequency, `lastCheckedAt`/`lastBestPrice` (with freshness
  language again), active/paused state toggle, and a chevron to a detail
  view.
- **Watch detail view** (tap into a row): insights — current best price vs.
  lowest/average observed (small stat row, tabular-nums), a simple price-
  history sparkline (thin mint line, no fill or a very faint fill, no grid
  clutter — matches the "elegant sparkline" guidance from the dataviz
  conventions implied by the rest of the system), and a delivery log
  (date, status, subject) as ruled rows.
- Empty state (`EmptyState`, no illustration) when no watches exist yet,
  with a CTA back to Discover.
- Pause/delete actions on a watch: swipe-to-reveal actions (native iOS
  pattern) using `danger` tone (coral) for delete, `secondary` for
  pause/resume — acceptable to lean on the native swipe-action affordance
  here since it's a list-management pattern users already know.

**Animation:**
- Sparkline draws in on first view (`stroke-dashoffset` animating from full
  to 0, ~600ms ease-out) — a small but nice touch echoing the ScoreDial fill
  animation on Trip Detail, reinforcing "numbers draw themselves in" as a
  house animation motif.
- Toggling active/paused is instant with a brief tone-color flash on the
  status Badge, no confirmation modal for pause (only for delete, which gets
  a plain system confirmation alert).

---

### 2.10 Account (tab)

Mirrors `app/account/page.tsx`. Plain settings screen — deliberately the
least "designed" screen in the app, which is itself correct: settings
screens should be calm, not showcase-y.

**Content, ruled sections (`border-t border-line` between each, matching
web exactly):**
1. Profile: display name field, email (read-only), save button.
2. Change password: current + new password fields, submit.
3. Billing: current plan name, "Manage billing" button (opens external
   portal — Safari view).
4. Theme: light/dark/system toggle — reuse the same 3-way pattern as the
   `ThemeToggle` on web (likely a segmented control).
5. Notification preferences link → back into a preferences editor (could
   reuse onboarding step 10's UI for consistency).
6. Danger zone: log out (secondary button), delete account (danger/coral
   button, confirmation alert before submitting).

**Animation:** none beyond standard form field focus (hairline → mint) and
success/error `Notice` fade-ins, consistent with Sign up/Log in. This screen
should feel calm and instant, not choreographed.

---

## 3. Cross-cutting UX notes for Stitch

- **Consistency check between screens**: after generating each screen, ask
  Stitch to reuse the exact components it already built for badges, buttons,
  chips, and the boarding-pass card rather than regenerating similar-looking
  but slightly different versions — visual drift between screens is the
  single biggest risk in a screen-by-screen generation process.
- **Dark mode is default**; generate every screen in dark first, then
  generate/verify the light variant using the light tokens table in
  `design.md` §2.2 — don't let Stitch invent a different light palette by
  naive inversion.
- **Empty, loading, and error states** should be produced for every
  data-driven screen (Discover results, Dashboard, My World, Trip Detail) —
  not just the "happy path with data" mockup. Use the typographic
  `EmptyState` pattern for empty, the thin-ring `Spinner` for loading, and
  the left-rule `Notice` (error tone) for errors, consistently.
- **No native default styling left unstyled**: every input, toggle, radio,
  slider, and button must be the Triplet-specific version from `design.md`,
  never the bare iOS system control — this is the single most important
  instruction for keeping the app from looking like a generic SwiftUI form
  once implemented.
