# 导入子目录中的 Makefile 文件
REPO_ROOT?=$(shell git rev-parse --show-toplevel)
ROOT_DIR?=${REPO_ROOT}/src/plugins/aidev_wxbot
pytest = PYTHONPATH=${REPO_ROOT}/src/agent:${REPO_ROOT}/src/plugins/aidev_bkplugin:${ROOT_DIR}:$${PYTHONPATH} uv run --no-sync pytest --ds=aidev_wxbot.settings -c ${ROOT_DIR}/pyproject.toml


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

.PHONY: test
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
		${args}


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
