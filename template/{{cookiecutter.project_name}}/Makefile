ROOT_DIR?=$(shell git rev-parse --show-toplevel 2>/dev/null || echo ".")
pytest = uv run --no-sync pytest --ds settings -c ${ROOT_DIR}/pyproject.toml

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

.PHONY: init
init: uv-install
	@echo "Project initialization complete."

.PHONY: init-pre-commit
init-pre-commit: .git/hooks/pre-commit .git/hooks/pre-push
	@echo "Project link initialization complete."

.PHONY: uv-install
uv-install:
	uv --version
	uv sync --inexact --no-dev

.PHONY: clean
clean:
	find . -name '*.pyc' -type f -delete
	find . -name "__pycache__" | xargs rm -rf
	find . -name ".mypy_cache"  | xargs rm -rf
	find . -name ".cache" | xargs rm -rf
	rm -rf ./dist
	rm -rf .venv
	uv clean

.git/hooks/pre-commit: ${ROOT_DIR}/.pre-commit-config.yaml
	uv run pre-commit install -t pre-commit
	@echo "Pre-commit hook installed."

.git/hooks/pre-push: ${ROOT_DIR}/.pre-commit-config.yaml
	uv run pre-commit install -t pre-push

.PHONY: lint
lint:
	uv run pre-commit run -a --hook-stage commit

# 一键启动：加载 .env、初始化数据库，并在 local.${BKPAAS_BK_DOMAIN}:8000 启动本地服务
.PHONY: dev
dev:
	@set -eu; \
	if [ ! -f ./.env ]; then \
		echo "Missing .env. Put it in $(CURDIR)/.env or run root make dev env_file=/path/to/.env" >&2; \
		exit 1; \
	fi; \
	set -a; \
	. ./.env; \
	set +a; \
	dev_host="local.$${BKPAAS_BK_DOMAIN:?Missing BKPAAS_BK_DOMAIN in .env}"; \
	echo "Starting template service at http://$$dev_host:8000"; \
	uv run --no-sync python bin/manage.py migrate; \
	uv run --no-sync python bin/manage.py createcachetable; \
	uv run --no-sync python bin/manage.py runserver "$$dev_host:8000"
