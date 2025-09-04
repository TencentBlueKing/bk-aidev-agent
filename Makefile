# 导入子目录中的 Makefile 文件
ROOT_DIR?=$(shell git rev-parse --show-toplevel)

.PHONY: ALL
ALL: init-project

uv.lock: pyproject.toml
	uv lock

.PHONY: requirements
requirements: requirements.txt

.PHONY: requirements.txt
requirements.txt: uv.lock pyproject.toml
	uv pip freeze | grep -v "file" > requirements.txt


.PHONY: init-project
init-project: uv-install .git/hooks/pre-commit .git/hooks/pre-push
	@echo "Project initialization complete."

.PHONY: uv-install
uv-install:
	uv --version
	uv sync

.git/hooks/pre-commit: ${ROOT_DIR}/.pre-commit-config.yaml
	uv run pre-commit install -t pre-commit
	@echo "Pre-commit hook installed."

.git/hooks/pre-push: ${ROOT_DIR}/.pre-commit-config.yaml
	uv run pre-commit install -t pre-push

.PHONY: clean
clean:
	rm -f .git/hooks/pre-commit
	rm -f .git/hooks/pre-push
	uv clean

.PHONY: lint
lint:
	uv run pre-commit run -a --hook-stage commit

build-template:
	cd ./src/frontend/publish-template/ && npm install && npm run build && cd -
	mkdir -p tmp/build
	cp -r ${ROOT_DIR}/template tmp/build
	cp -r ${ROOT_DIR}/src/frontend/publish-template/dist tmp/build/template/{{cookiecutter.project_name}}/bk_plugin/tpls
	cd tmp/build && zip -q -r templates.zip ./*
	mv tmp/build/templates.zip .
	echo "Build template success"
	rm -rf tmp/build

build-template-clean:
	rm -rf tmp/build
	rm -rf ${ROOT_DIR}/src/frontend/publish-template/dist
	rm -f templates.zip
