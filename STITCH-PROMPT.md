# Stitch prompts for the Triplet redesign

How to use: paste the **Project context** block first (Stitch keeps it as context for the
session), then generate one screen at a time with the per-screen prompts. Regenerate or
refine individual screens with follow-up instructions ("make the globe larger", "tighter
rows") rather than re-pasting everything.

---

## Project context (paste first, keep with every screen)

Design a dark, premium web app called **Triplet** — a flight-deal discovery tool for
Europe. The product: a traveller from the Vienna region (airports like VIE, BUD, ZAG,
LJU, TRS, VCE) types a loose wish — "somewhere warm in August under €150" — and Triplet
finds real round-trip deals across all of Europe, scores each one (a DealScore for how
good the price is, a FitScore for how well it matches the traveller's personal style),
and can generate an AI day-by-day itinerary once they pick a trip. Prices are cached
"indicative" fares, so honesty labels ("observed 2h ago", "verify before booking") are a
core part of the brand, not fine print.

**Design direction:** think editorial travel journal meets flight-deck instrument panel.
Dark ink-blue base (#0b1117), off-white type (#e8f0f4), muted blue-grey secondary text
(#93a6b4), one primary accent: mint (#7ddfc3), with sparing use of warm coral (#ff9a78)
for price highlights and gold (#ffd08a) for scores. Confident typographic hierarchy: a
characterful display face for headlines (something with personality — a sharp grotesque
or an editorial serif), a clean neutral sans for UI. Generous whitespace, asymmetric
layouts, full-bleed sections.

**Explicitly avoid the generic AI-generated look:** no emojis anywhere (use fine line
icons or none), no wall of identical rounded cards, no purple/blue gradient blobs, no
glassmorphism on everything, no centered-hero-with-two-buttons cliché, no feature grid
of three cards with icons. Prefer: ruled hairlines, tabular data laid out like a
timetable or boarding pass, big typographic numbers, small uppercase labels with letter
spacing, subtle grain/noise texture, and restrained motion.

**Signature element:** an interactive rotating 3D Earth (dark, wireframe-meets-satellite
style, city lights) with animated route arcs flying out of the Vienna region to
European destinations, each arc tipped with a small live price tag. It should feel like
a navigation instrument, not a stock globe.

---

## Screen 1 — Landing page

Landing page for Triplet. Layout:

- Slim top nav: wordmark "Triplet" left; links Discover, Pricing, Privacy; a quiet
  "Sign in" text link and one solid mint "Get started" button right.
- Hero, asymmetric: left column takes ~40% with an oversized editorial headline like
  "Europe, on a whim." and a subline explaining the product in one sentence ("Tell us
  roughly what you want. We watch the fares from your airports and tell you when it's
  worth flying."). Below it, a single natural-language search input styled like a
  command line / departures-board field with placeholder "somewhere warm in August,
  under €150" and an inline arrow submit. Right ~60%: the interactive 3D Earth with
  route arcs and floating price tags (€39 Milan, €118 Copenhagen…). The globe bleeds
  off the right edge of the viewport.
- Below the hero: a live "departures board" strip — a horizontally scrolling row of
  real deals rendered like split-flap airport rows: route, dates, nights, price,
  DealScore. Monospaced numerals, hairline separators, no card boxes.
- "How it works" as a numbered editorial sequence (01 Tell us your style — a 2-minute
  quiz; 02 We watch the fares — hourly, from your home airports; 03 You fly when it's
  worth it — scored deals plus an AI day plan), laid out as alternating text blocks
  with thin rules, not icon cards.
- An honesty section set apart typographically (small caps heading "Straight with
  you"): prices are indicative and timestamped, we never fake live fares, book with
  the airline. This is a brand moment, treat it with typographic dignity.
- Footer: minimal, three columns, legal links, GDPR note "Your data lives in the EU."

## Screen 2 — Discover (search + results)

The main search workspace, signed in. Layout:

- Persistent app shell: slim left rail or top bar with Discover, Dashboard, Account.
- Top: the natural-language search field (same command-line style as landing), and
  beneath it a compact row of structured controls that read like a fare rules line,
  not a filter sidebar: origin airport chips (VIE BUD ZAG LJU TRS VCE, toggleable),
  date window, trip length range (4–8 nights), max budget, and a destination selector
  that accepts a country, city, or region ("Anywhere", "Scandinavia", "Italy").
- Results as a timetable, not cards: each deal is a full-width row with a hairline
  below. Row anatomy, left to right: destination city in the display face with country
  in small caps under it; outbound and return dates with weekday; nights count; two
  compact score dials — DealScore (gold) and FitScore (mint) as thin-ring gauges with
  the number inside; the round-trip price as the largest element in coral with the
  per-person label and an "indicative · observed 2h ago" microlabel; a quiet chevron.
  An "Over budget" state renders the price ghosted with a small flag, still visible.
- One optional toggle: list ↔ globe view, where the same results render as arcs on the
  3D Earth and hovering an arc highlights the corresponding row.
- Empty state: not an illustration — a well-set typographic message with three example
  queries the user can click.

## Screen 3 — Trip detail + AI itinerary

The page after choosing a deal. Layout:

- Header: "Trip suggestion" small caps label, destination as a big editorial headline
  ("Milan, five nights."), timestamp and expiry as a microlabel.
- The flights as a boarding-pass-style strip: outbound and return legs on one line
  each — airport codes large, times, date, airline, stops — separated by a perforated
  rule. Price on the right in coral with the indicative disclaimer directly under it.
  Score dials for Deal and Fit with a one-line plain-English explanation each
  ("Cheaper than 92% of fares we've seen on this route").
- "Before you book" as a short ruled list (independent one-way fares, verify final
  price), set small, not a warning box.
- The AI itinerary section, the star of the page: before generation, a single
  confident block — "Plan your days" headline, one sentence ("A day-by-day plan built
  around your 12:00 arrival and 18:00 flight home, tuned to how you like to travel"),
  and one mint button "Plan my trip". After generation: a vertical day timeline with a
  thin mint spine; each day is a heading (Day 2 — Sun, Jul 26) with entries grouped by
  morning/afternoon/evening as small caps time labels; each entry: title in medium
  weight, one-line description in secondary text, and an estimated cost range set in
  monospace ("€10–25 · estimate"). End with "Getting around" and "Estimated extra
  spend" as two short ruled paragraphs, then the disclaimers in fine print. No emoji
  icons per activity — the time-of-day labels and typography carry the structure.

## Screen 4 — Onboarding quiz

A 3-step travel-personality quiz that should feel like assembling a boarding pass, not
a survey. Steps: (1) travel style — multi-select from options like Food, Nature &
hikes, Culture, Nightlife, Beach, City wandering, rendered as large type-set tokens
that fill in mint when selected; (2) comfort rules — max one stop, no red-eyes,
carry-on only, as toggle lines; (3) budget comfort zone — a horizontal slider on a
fare-scale. A live "boarding pass" preview on the right builds up as they answer:
their airports, styles, budget printed on it. Progress as thin segmented rule at top.
Finish button: "Start watching fares".

## Screen 5 — Dashboard

Signed-in home. Layout: a greeting line with the user's watch summary set as a
sentence ("Watching 3 routes from Vienna. Two deals worth a look this week."), not
stat cards. Then: "Your watches" as timetable rows (query as the user typed it, status
active/paused, last run, best price found with score); "Recent suggestions" as a
compact version of the Discover rows; alert history as a quiet log with timestamps.
One primary action top right: "New watch".

## Screen 6 — Account & privacy

Settings page in the same shell. Sections divided by hairline rules, not cards:
Profile (email, travel style summary with "Retake quiz" link), Plan & billing (current
plan, manage), and a "Your data" section given real presence: plain-language sentences
for GDPR rights with two actions — "Download everything we have" (secondary button)
and "Delete my account" (quiet red text button with confirm). Note that data lives in
the EU. The privacy section should feel like a brand promise, not a legal appendix.

## Screen 7 — Auth (sign in / sign up)

Minimal, centered but off-axis: form on the left third, and a slow-rotating dim globe
occupying the rest as ambience. Email + password, one mint submit, links exchanged
between sign in/up, forgot password. No social-proof clutter, no testimonial.

## Screen 8 — Pricing

Two plans set as a typographic comparison, side by side with a shared hairline grid —
not two floating cards. Free: manual searching, limited origin airports. Premium: all
origins, hourly fare watching with alerts, AI day plans. Prices as big editorial
numerals. One sentence of honesty under the table: "Both plans see the same fares. We
never mark prices up."
