# onestopeurope — web

The MapLibre client for [onestopeurope](https://onestopeurope.eu): pick a station, see
how far you can get by train — nonstopeurope with onestopeurope.

It renders every reachable long-distance station as a colored dot on the map (colored
by trains-per-day / journey time), draws the connecting routes, and shows a booking
link for the selected journey. Reachability data is served by the FastAPI backend in
`../server` (precomputed by the `../pipeline`).

## Dev commands

From this directory:

```sh
npm run dev     # start the Vite dev server
npm test        # run the vitest suite once
npm run build   # typecheck (tsc -b) and produce a production build
npm run lint    # oxlint
```

Or, from the repo root, `just dev` starts both the API (port 8000) and this dev
server together and stops both on Ctrl-C.

## Environment variables

- `VITE_TRAINLINE_REF` — optional Trainline affiliate reference appended to booking
  links generated in `JourneyCard`. Leave unset for plain (non-affiliate) links.
