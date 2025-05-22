# 导入子目录中的 Makefile 文件
ROOT_DIR?=$(shell git rev-parse --show-toplevel)

.PHONY: ALL
ALL: init-project requirements

poetry.lock: pyproject.toml
	poetry lock --no-update -vvv

.PHONY: requirements
requirements: requirements.txt

.PHONY: requirements.txt
requirements.txt: poetry.lock pyproject.toml
	poetry export -f requirements.txt --without-hashes | awk -F';' '{print$$1}' | grep -v "index-url" > ${ROOT_DIR}/requirements.txt

.PHONY: init-project
init-project: poetry-install .git/hooks/pre-commit .git/hooks/pre-push
	@echo "Project initialization complete."

.PHONY: poetry-install
poetry-install:
	poetry install --remove-untracked

.git/hooks/pre-commit: ${ROOT_DIR}/.pre-commit-config.yaml
	poetry run pre-commit install -t pre-commit

.git/hooks/pre-push: ${ROOT_DIR}/.pre-commit-config.yaml
	poetry run pre-commit install -t pre-push

build-template:
	cd ./src/frontend/publish-template/ && npm install && npm run build && cd -
	mkdir -p tmp/build
	cp -r ${ROOT_DIR}/template tmp/build
	cp -r ${ROOT_DIR}/src/frontend/publish-template/dist tmp/build/template/{{cookiecutter.project_name}}/bk_plugin/
	cd tmp/build && zip -q -r templates.zip ./*
	mv tmp/build/templates.zip .
	echo "Build template success"
	rm -rf tmp/build

build-template-clean:
	rm -rf tmp/build
	rm -rf ${ROOT_DIR}/src/frontend/publish-template/dist
	rm -f templates.zip
