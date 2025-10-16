# 导入子目录中的 Makefile 文件
ROOT_DIR?=$(shell git rev-parse --show-toplevel)/src/plugins/aidev_ai_blueking
pytest = uv run --no-sync pytest -c ${ROOT_DIR}/pyproject.toml


.PHONY: ALL
ALL: init

uv.lock: pyproject.toml
	uv lock
	uv lock --check

.PHONY: requirements
requirements: requirements.txt

.PHONY: requirements.txt
requirements.txt: pyproject.toml
	uv export --no-hashes --no-annotate --no-dev --no-editable --no-header --format requirements-txt | awk 'NR>1' >  requirements.txt

.PHONY: init-project
init: uv-install
	@echo "Project initialization complete."

.PHONY: uv-install
uv-install:
	uv --version
	uv sync --inexact

.PHONY: clean
clean:
	find . -name '*.pyc' -type f -delete
	find . -name "__pycache__" | xargs rm -rf
	find . -name ".mypy_cache"  | xargs rm -rf
	find . -name ".cache" | xargs rm -rf
	rm -rf ./dist
	rm -rf .venv
	uv clean
