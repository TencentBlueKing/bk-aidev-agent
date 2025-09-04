# 导入子目录中的 Makefile 文件
ROOT_DIR?=$(shell git rev-parse --show-toplevel)/src/agent
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

.PHONY: backend-test
test:
	$(eval path ?= ${ROOT_DIR}/tests)
	$(eval maxfail ?= --maxfail=2)
	$(eval warnings ?= --disable-pytest-warnings)
	$(eval markers ?= not slow)
	${pytest} ${path} \
		-m "${markers}" \
		${maxfail} \
		${warnings} \
		--durations=20 \
		-vv \
		${reuse_db} ${args}

.PHONY: ci-test
ci-test:
	$(eval path ?= ${ROOT_DIR}/tests)
	$(eval maxfail ?= --maxfail=2)
	$(eval warnings ?= --disable-pytest-warnings)
	${pytest} ${path} \
		--durations=30 \
		--cov-config ${ROOT_DIR}/pyproject.toml \
		--cov ${ROOT_DIR}

.PHONY: build
build:
	uv pip install build
	uv run -m build

.PHONY: clean
clean:
	find . -name '*.pyc' -type f -delete
	find . -name "__pycache__" | xargs rm -rf
	find . -name ".mypy_cache"  | xargs rm -rf
	find . -name ".cache" | xargs rm -rf
	rm -rf ./dist
	rm -rf .venv
	uv clean

.PHONY: makemigrations
makemigrations:
	uv run python manage.py makemigrations

.PHONY: api_doc
api_doc:
	uv run python manage.py spectacular --file schema.yml
	uv run python manage.py generate_api_docs

.PHONY: intergration-test
intergration-test:
	$(eval path ?= ${ROOT_DIR}/tests/intergration)
	$(eval maxfail ?= --maxfail=2)
	$(eval warnings ?= --disable-pytest-warnings)
	${pytest} ${path} -s --durations=100
