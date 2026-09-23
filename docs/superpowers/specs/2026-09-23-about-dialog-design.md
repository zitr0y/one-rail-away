# About dialog ("?") — design (2026-09-23)

Backlog BA. Replaces the header "Legal" text link (shipped earlier today) with a
"?" button that opens an in-app About dialog holding the mission, how to read
the map, data sources (in use + wanted), and the legal links. Approved by the
user 2026-09-23.

## UI

- **Header:** `?` button (`.about-toggle`) immediately before the theme toggle,
  `aria-label="About & legal"`, `title="About & legal"`, `aria-haspopup="dialog"`.
  Same look as the theme toggle; ≥44 px on mobile. The `a.header-legal` link and
  its CSS are removed.
- **Dialog:** rendered by App when open. Backdrop dims the map; panel is
  `role="dialog" aria-modal="true" aria-labelledby` its title. Closes on ×,
  Escape, or backdrop click. On open, focus moves to the × button; on close,
  focus returns to the `?` button. While open, App's global Escape handler does
  nothing else (it must not clear the journey selection). Desktop: centred
  card, max-width 36rem, scrolls inside if tall. Mobile: full-width sheet
  pinned below the header, scrolls inside.
- **Map credits keep** "Legal · Privacy" (second path to the legal pages).

## Content (final wording)

**About onestopeurope**

*Why this map exists* — Flying is often the default for trips in Europe,
mostly because it's hard to see what's possible by train. onestopeurope shows,
from any station, everywhere you can reach by train — and how many changes it
takes. It starts with **nonstop** trains, because a journey without changes is
the one people actually enjoy taking.

*How to read it* — Pick a station. Colours show travel time; lines show the
routes. Switch between **Nonstop**, **One stop** and **Two stops** to allow
changes. Tap a destination for example trains, how often they run, and a link
to book.

*Data* —
- **Timetables from:** DB (Germany), FlixTrain (Germany), SNCF (France),
  ÖBB (Austria), SBB (Switzerland), NS (Netherlands), Rejseplanen (Denmark),
  CP (Portugal), Trenitalia (Italy), Renfe (Spain), PKP (Poland).
- **Not covered yet:** no feed of their own — Czechia, Slovakia, Hungary,
  Slovenia, Croatia, Belgium, Luxembourg, Great Britain, Ukraine, Romania,
  Lithuania (trains *into* them show up; journeys *from* them don't).
  Missing operators — Italo (Italy), Ouigo España and iryo (Spain),
  WESTbahn (Austria), RegioJet and Leo Express (Czechia/Slovakia).
- Know an open timetable feed for one of these? Get in touch (→ legal notice
  contact).
- Full, current list: GitHub `docs/data-sources.md`
  (https://github.com/zitr0y/one-rail-away/blob/main/docs/data-sources.md).

*Footer* — Legal notice · Privacy · Built by Aaron Bussche as a free side
project.

The data lists live in `web/src/components/aboutContent.ts`, kept in sync with
`docs/data-sources.md` by hand.

## Tests

- Dialog: opens from `?`, has the three section headings, links to
  `/legal.html` and `/privacy.html`; Escape and × close it and return focus to
  `?`; backdrop click closes; Escape while open does not clear the selection.
- Header no longer contains `a.header-legal`.
- `cd web && npm run build` passes (prod type-check includes tests).
