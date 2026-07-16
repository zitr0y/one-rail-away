---
name: verify
description: Build/launch/drive recipe for verifying web map changes end-to-end (headless, no screenshots)
---

# Verifying onestopeurope web changes

## Launch (committed sample artifacts in data/out are enough)

```bash
uv run uvicorn server.app:app --port 8000 &   # API; must be 8000 (vite proxy is hardcoded)
cd web && npm ci && npx vite --port 5199 &    # dev server; DEV builds expose window.__map
```

Smoke: `curl -s http://localhost:5199/api/stations | head -c 100` (vite proxies /api → 8000).

## Drive (Python playwright, sync API — installed user-wide)

- Wait for `window.__map`, then `window.__map.loaded()`, then ~1s settle.
- Inspect layers via `__map.queryRenderedFeatures({layers: ['all-stations']}).length`
  (GeoJSONSource private `_data` is NOT readable in maplibre 5 — always assert on
  rendered features, not source internals).
- Sample data expectations at the default viewport (center 8,50 zoom 4.5):
  4 `all-stations` dots, 15 `capital-stars` rendered (18 capitals total, 3 off-view).
- To force "stations before map load" ordering, `page.route()` a 2.5s delay onto
  `**/mapstyle-light.json`; delay `**/api/stations` for the opposite ordering.

## Gotchas

- `pkill -f "uvicorn server.app"` inside a compound command kills the shell itself
  (the pattern matches the shell's own cmdline). Bracket-escape: `uvicorn serv[e]r.app`,
  and never launch the server in the same Bash call as the pkill.
- No screenshots/visual eval — the user eyeballs UI themselves; verify via
  `window.__map` state queries and API responses only.
