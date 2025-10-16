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

.PHONY: build-aidev-ai-blueking
build-aidev-ai-blueking:
	cd ./src/frontend/publish-template/ && npm install && npm run build && cd -
	mv ${ROOT_DIR}/src/frontend/publish-template/dist/static ${ROOT_DIR}/src/plugins/aidev_ai_blueking/aidev_ai_blueking
	mkdir ${ROOT_DIR}/src/plugins/aidev_ai_blueking/aidev_ai_blueking/templates
	mv ${ROOT_DIR}/src/frontend/publish-template/dist/index.html ${ROOT_DIR}/src/plugins/aidev_ai_blueking/aidev_ai_blueking/templates/home.html
	cd ${ROOT_DIR}/src/plugins/aidev_ai_blueking && uv build
	@echo "aidev-ai-blueking built."
