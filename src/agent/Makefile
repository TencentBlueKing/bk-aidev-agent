# 导入子目录中的 Makefile 文件
ROOT_DIR?=$(shell git rev-parse --show-toplevel)/src/agent
pytest = poetry run pytest -c ${ROOT_DIR}/pyproject.toml

.PHONY: ALL
ALL: init requirements

poetry.lock: pyproject.toml
	poetry lock --no-update -vvv

.PHONY: requirements
requirements: requirements.txt

.PHONY: requirements.txt
requirements.txt: poetry.lock pyproject.toml
	poetry export -f requirements.txt --without-hashes | awk -F';' '{print$$1}' | grep -v "index-url" > ${ROOT_DIR}/requirements.txt

.PHONY: init-project
init: poetry-install .git/hooks/pre-commit .git/hooks/pre-push
	@echo "Project initialization complete."

.PHONY: poetry-install
poetry-install:
	poetry install --remove-untracked

.PHONY: backend-test
test:
	$(eval path ?= ${ROOT_DIR}/tests)
	$(eval reuse_db ?= --reuse-db)
	$(eval maxfail ?= --maxfail=1)
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
	$(eval maxfail ?= --maxfail=1)
	$(eval warnings ?= --disable-pytest-warnings)
	${pytest} ${path} \
		--durations=30 \
		--cov-config ${ROOT_DIR}/pyproject.toml \
		--cov ${ROOT_DIR}

.PHONY: build
build:
	poetry build

.PHONY: clean
clean:
	find . -name '*.pyc' -type f -delete
	find . -name "__pycache__" | xargs rm -rf
	find . -name ".mypy_cache"  | xargs rm -rf
	find . -name ".cache" | xargs rm -rf
	rm -rf ./dist


.PHONY: intergration-test
intergration-test:
	$(eval path ?= ${ROOT_DIR}/tests/intergration)
	$(eval maxfail ?= --maxfail=2)
	$(eval warnings ?= --disable-pytest-warnings)
	${pytest} ${path} -s