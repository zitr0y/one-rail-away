# Legal notice, privacy policy, affiliate label — design (2026-09-23)

## Why

Trainline affiliate income (backlog N) makes onestopeurope.eu a commercial
information-society service. The operator lives in the Netherlands, so Dutch law
applies (country-of-origin principle, E-Commerce Directive art. 5 → Dutch Civil
Code art. 3:15d): name, geographic address, and contact details **including an
email address**, plus KvK / VAT numbers once they exist. The CJEU (C-298/07)
allows the second rapid contact channel to be a contact form. GDPR requires a
privacy policy because IP addresses are processed. Affiliate links must be
recognisable as advertising.

Everything is English only. Not legal advice; the operator reviews the text.

## Facts the text relies on (verified 2026-09-23)

- **Caddy** (reverse proxy, shared box) logs every onestopeurope request at
  debug level to Docker's json-file log: client IP, time, URL, user agent.
  Capped at one 50 MB file; oldest entry was ~32 h old → IPs are gone within
  a few days.
- **API** logs `BOOK` lines with station ids + date only (no IP; uvicorn sees
  the proxy's Docker address).
- **No cookies, no analytics, no localStorage personal data.** Fonts are
  self-hosted.
- **OpenFreeMap** (`tiles.openfreemap.org`) serves the map tiles; the browser
  contacts it directly, so it sees the visitor's IP.
- **Book** → `/api/book` → Trainline (and, once approved, via Partnerize,
  which sets its own tracking cookie).
- Mail for onestopeurope.eu is Namecheap forwarding; the operator creates
  `contact@onestopeurope.eu` → a private inbox. Only the alias is published.

## Pages

Static files in `web/public/`: `legal.html`, `privacy.html` (served as
`/legal.html`, `/privacy.html` — nginx `try_files $uri` serves them as-is; no
server config change). No JavaScript. Self-hosted Barlow font, light/dark via
`prefers-color-scheme`, readable column (max ~40rem), a "← Back to the map"
link to `/`. The email is written with HTML entity encoding (`&#99;&#111;…`)
to deter naive scrapers while staying a normal clickable `mailto:` for people.

### `/legal.html` — "Legal notice"

> **Legal notice**
>
> onestopeurope.eu is run by a private individual:
>
> Aaron Bussche
> Sophiaweg 76
> 6523 NJ Nijmegen
> Netherlands
>
> Email: contact@onestopeurope.eu
> Contact form: https://aaronbussche.eu
>
> Not registered with the Dutch Chamber of Commerce (KvK); no VAT number.
>
> **Affiliate links**
> The "Search on Trainline" button may be an affiliate link: if you buy a
> ticket after clicking it, Trainline may pay onestopeurope a commission. You
> pay the same price. It never changes which connections the map shows or how
> they are ranked.
>
> **Timetable data and accuracy**
> Journeys are computed from published timetable data (credited on the map)
> for a sample week. They can be incomplete or out of date — always check with
> the operator or seller before you travel.
>
> **Privacy** → link to `/privacy.html`

### `/privacy.html` — "Privacy policy"

> **Privacy policy**
> Last updated: <date of deploy>
>
> **Who is responsible** — Aaron Bussche, address and email as in the
> [legal notice](/legal.html).
>
> **No cookies, no tracking** — onestopeurope sets no cookies and uses no
> analytics or advertising trackers.
>
> **Server logs** — When you load the site, our web server records your IP
> address, the time, the page or data requested, and your browser's user
> agent. We use this only to run the site and keep it secure (legitimate
> interest, GDPR art. 6(1)(f)). The logs are deleted automatically, normally
> within a few days, and are not shared.
>
> **Map tiles** — The map background is loaded by your browser directly from
> OpenFreeMap (openfreemap.org), which therefore receives your IP address.
> See OpenFreeMap's own terms and privacy information.
>
> **"Search on Trainline"** — When you click it, we log which two stations
> and which date were requested (no IP address, nothing that identifies you)
> to count booking clicks. You are then sent to Trainline, possibly via the
> affiliate network Partnerize, which may set cookies to attribute a booking.
> From that point Trainline's and Partnerize's privacy policies apply.
>
> **Your rights** — You can ask for access, correction, deletion,
> restriction, or object to processing, via the email in the legal notice.
> In practice we hold nothing that links to you beyond short-lived server
> logs. You can complain to the Dutch Data Protection Authority (Autoriteit
> Persoonsgegevens, autoriteitpersoonsgegevens.nl).

## Links in the app

- **Header:** a small "Legal" text link in `.header-bar` (before the theme
  toggle), always visible on desktop and mobile → `/legal.html`.
- **Map attribution:** append `Legal · Privacy` links to the attribution
  control (MapLibre `customAttribution`), so privacy is reachable from the
  credits too.

## Affiliate label

- New endpoint `GET /api/config` → `{"affiliate_links": bool}`,
  true iff env `TRAINLINE_LINK_PREFIX` is non-empty. `Cache-Control: no-cache`.
- Web fetches it once at startup. When true, `TripDetails` shows a small
  "Affiliate link" note under the Book button linking to
  `/legal.html#affiliate-links`. When false or on fetch error: no note.
- The legal page's affiliate paragraph is static ("may be") so it's correct
  before and after approval.

## Tests

- Server: `/api/config` false without env, true with env.
- Web: TripDetails shows the note only when `affiliateLinks` is true; header
  renders the Legal link.
- Static pages: a small vitest reads both HTML files and asserts they contain
  the operator name, the entity-encoded email, the Autoriteit Persoonsgegevens,
  and no `<script` tag.
- Manual after deploy: `/legal.html` and `/privacy.html` load (not the SPA),
  mailto works, header link visible on a 375 px viewport.

## Operator to-do (not code)

- Create the `contact@onestopeurope.eu` forward in Namecheap (target:
  aaronbussche@gmail.com). Deploy only after it exists.
- Once registered with the KvK / for VAT: add the numbers to `legal.html`.

## Out of scope

Cookie banner (nothing to consent to), German text, a mission/about page (BA).
