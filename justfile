# Run everything needed for development (web target added in Task 17)
test:
    uv run pytest -q

lint:
    uv run ruff check .

pipeline:
    uv run ose fetch && uv run ose build && uv run ose compute
