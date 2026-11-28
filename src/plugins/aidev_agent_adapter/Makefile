.PHONY: init test lint build
init:
	uv sync --group dev
test:
	uv run --no-sync pytest $(if $(path),$(path),tests) $(args)
lint:
	cd ../../.. && uv run --project src/plugins/aidev_agent_adapter --no-sync ruff check --config pyproject.toml src/plugins/aidev_agent_adapter
	cd ../../.. && uv run --project src/plugins/aidev_agent_adapter --no-sync ruff format --check --config pyproject.toml src/plugins/aidev_agent_adapter
build:
	uv build
