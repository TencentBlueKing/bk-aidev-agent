# 导入子目录中的 Makefile 文件
ROOT_DIR?=$(shell git rev-parse --show-toplevel)/src/plugins/aidev_bkplugin
pytest = uv run --no-sync pytest --ds=tests.settings -c ${ROOT_DIR}/pyproject.toml


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
# 注意：tests/packages/opentelemetry 通过 conftest 的 pytest.importorskip 控制是否运行；
# 仅当安装 `pip install aidev-bkplugin[opentelemetry]` 后才会被纳入。
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
	$(eval markers ?= not slow)
	${pytest} ${path} \
		-m "${markers}" \
		--durations=30 \
		--cov-config ${ROOT_DIR}/pyproject.toml \
		--cov ${ROOT_DIR}/aidev_bkplugin

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
