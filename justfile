# Run everything needed for development (web target added in Task 17)
test:
    uv run pytest -q

lint:
    uv run ruff check .

pipeline:
    uv run ose fetch && uv run ose build && uv run ose compute

# Run API and web dev servers together (Ctrl-C stops both)
dev:
    #!/usr/bin/env bash
    trap 'kill 0' EXIT
    uv run uvicorn server.app:app --reload --port 8000 &
    (cd web && npm run dev) &
    wait
