# Trainline results handoff — design (2026-09-23)

Backlog N. Supersedes the "homepage only" fallback in
[`research/2026-07-13-trainline-booking-handoff.md`](../research/2026-07-13-trainline-booking-handoff.md).

## Goal

Clicking **Search on Trainline** opens Trainline's **search results page** for
the selected origin, destination and the date chosen in the trip panel's date
picker — not the homepage, not a prefilled form. The link is built so an
affiliate wrapper can be added later without touching the web client.

Rail Europe as a second seller is the next phase (backlog S); the redirect
endpoint is the seam it plugs into.

## Evidence (verified 2026-09-23, headless Chromium)

- `https://www.thetrainline.com/book/results?journeySearchType=single&origin=urn%3Atrainline%3Ageneric%3Aloc%3A7630&destination=urn%3Atrainline%3Ageneric%3Aloc%3A7480&outwardDate=2026-09-29T08%3A00%3A00&outwardDateType=departAfter&selectedTab=train&passengers%5B%5D=1996-01-01`
  lands on results for Berlin Hbf → München Hbf with live trains and prices.
  Praha hl.n. (17509) → Kraków Główny (17584) also works; trains Trainline
  cannot sell are listed as "details only".
- Location ids come from Trainline's open dataset
  <https://github.com/trainline-eu/stations> (`stations.csv`, `;`-separated,
  ~16 MB, ODbL-1.0, last pushed 2026-09-21).
- Prototype match against the live `stations.json` (2626 stations): 1982 by
  name within 5 km, 129 by coordinates within 500 m, 15 border points
  skipped, ~500 unmatched (mostly small PL/CZ regional stops).
- The URL format is **not officially documented**. That risk is why the URL is
  built server-side (one place to fix) and why every failure falls back to
  the homepage.

## 1. Pipeline: station matching

**Fetch.** `fetch` downloads `stations.csv` from
`https://raw.githubusercontent.com/trainline-eu/stations/master/stations.csv`
into the raw dir as `trainline_stations.csv`. A failed download logs a warning
and keeps the previous copy; it never aborts the run.

**Match** (`pipeline/trainline.py`, called from `compute` after `stations.json`
is written). Candidates: rows with coordinates and `is_suggestable == "t"`.
For each of our stations:

1. Skip names containing `(Gr)` (border points).
2. Name match: normalise both names (NFKD, strip accents, lowercase, keep
   `[a-z0-9]`); accept a candidate whose normalised name equals, contains, or
   is contained in ours, within 5 km. Take the nearest.
3. Else coordinate match: nearest candidate within 500 m.
4. Else unmatched.

Output: `out/trainline_ids.json` — `{"<our station id>": "<trainline id>"}` —
written into the same slot as the reach files, so it always agrees with that
slot's station ids (ids still rotate per refresh, backlog AM). Log one line:
`trainline: matched N/M stations (name A, coord B, border C)`.

Missing or unparsable CSV: log a warning, write `{}`. Every click then falls
back to the homepage; the pipeline still succeeds.

## 2. Server: `GET /api/book`

Query: `from`, `to` (our station ids), `date` (`YYYY-MM-DD`). Always answers
**302**.

- Both ids in `trainline_ids.json` and `date` is valid and not before today
  (Europe/Berlin): redirect to
  `https://www.thetrainline.com/book/results` with
  `journeySearchType=single`, `origin=urn:trainline:generic:loc:<id>`,
  `destination=urn:trainline:generic:loc:<id>`,
  `outwardDate=<date>T06:00:00`, `outwardDateType=departAfter`,
  `selectedTab=train`, `passengers[]=<today minus 30 years, YYYY-MM-DD>`
  (one adult).
- Otherwise: redirect to `https://www.thetrainline.com/`.
- **Affiliate hook:** env `TRAINLINE_LINK_PREFIX`, empty by default. When set,
  the final target becomes `PREFIX + urlencode(target)` (Partnerize
  deep-link shape, e.g. `https://prf.hn/click/camref:XXX/destination:`).
  Applied to both results and homepage targets. No affiliate value is ever
  hardcoded.
- **Click log:** one stdout line per request:
  `BOOK from=<id> to=<id> date=<date> matched=<true|false>`. Count with
  `docker logs aaron-trains-api | grep -c BOOK`.
- `trainline_ids.json` is read through the same per-slot caching the server
  uses for `stations.json`, so a slot flip picks up the new mapping.

## 3. Web

- `bookingUrl(fromId, toId, date)` in `web/src/lib/booking.ts` returns
  `/api/book?from=…&to=…&date=…` (URL-encoded).
- `TripDetails` passes `origin.id`, `destination.id`, `bookingDate`. Label
  stays "Search on Trainline", still `target="_blank" rel="noopener noreferrer"`.
- Credit: add "Stations: Trainline EU (ODbL)" to the map attribution
  alongside the timetable credits.

## 4. Tests

- `tests/test_trainline.py`: name match, accent/punctuation normalisation,
  coordinate fallback, `(Gr)` skipped, same name 20 km away rejected,
  non-suggestable rows ignored, missing CSV → `{}`.
- `tests/test_server.py`: matched → results URL with all params; unmatched id
  → homepage; past / malformed date → homepage; prefix wraps and encodes;
  log line emitted.
- `web/src/lib/booking.test.ts`: `bookingUrl` builds the encoded API link.
- `TripDetails.test.tsx`: the link reflects a changed date.
- Manual, after deploy: click through Berlin Hbf → München Hbf and one
  unmatched station in a real browser.

## Out of scope

Rail Europe and other sellers (next phase, S); Eurail/Interrail pass info;
return trips; departure-time choice; mobile button prominence (AZ); broader use
of the Trainline dataset (new backlog item BB).
