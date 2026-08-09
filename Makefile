# 导入子目录中的 Makefile 文件
ROOT_DIR?=$(shell git rev-parse --show-toplevel)
TEMPLATE_PROJECT_DIR := template/{{cookiecutter.project_name}}

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
	rm -rf ${ROOT_DIR}/src/plugins/aidev_ai_blueking/aidev_ai_blueking/templates
	rm -rf ${ROOT_DIR}/src/plugins/aidev_ai_blueking/aidev_ai_blueking/static
	cd ${ROOT_DIR}/src/frontend/ai-blueking && pnpm install --no-frozen-lockfile && pnpm run build:helper && pnpm run build:ui && pnpm run build:ai
	cd ${ROOT_DIR}/src/frontend && pnpm install --no-frozen-lockfile
	cd ${ROOT_DIR}/src/frontend/publish-template/ && rm -rf node_modules/.cache && pnpm run build
	mv ${ROOT_DIR}/src/frontend/publish-template/dist/static ${ROOT_DIR}/src/plugins/aidev_ai_blueking/aidev_ai_blueking
	mkdir ${ROOT_DIR}/src/plugins/aidev_ai_blueking/aidev_ai_blueking/templates
	mv ${ROOT_DIR}/src/frontend/publish-template/dist/index.html ${ROOT_DIR}/src/plugins/aidev_ai_blueking/aidev_ai_blueking/templates/home.html
	cd ${ROOT_DIR}/src/plugins/aidev_ai_blueking && uv build
	@echo "aidev-ai-blueking built."

.PHONY: release_ai_blueking
release_ai_blueking:
	@VERSION=$$(echo $(filter-out $@,$(MAKECMDGOALS)) | awk '{print $$1}'); \
	if [ -z "$$VERSION" ]; then \
		echo "Error: VERSION is required. Usage: make release_ai_blueking 1.3.0rc4"; \
		exit 1; \
	fi; \
	echo "Updating ai-blueking version to $$VERSION..."; \
	sed -i 's/"version": "[^"]*"/"version": "'"$$VERSION"'"/' ${ROOT_DIR}/src/frontend/ai-blueking/package.json; \
	sed -i 's/^version = "[^"]*"/version = "'"$$VERSION"'"/' ${ROOT_DIR}/src/plugins/aidev_ai_blueking/pyproject.toml; \
	sed -i 's/^aidev-ai-blueking==[^ ]*/aidev-ai-blueking=='"$$VERSION"'/' ${ROOT_DIR}/template/{{cookiecutter.project_name}}/requirements.txt; \
	sed -i 's/"aidev-ai-blueking==[^"]*"/"aidev-ai-blueking=='"$$VERSION"'"/' ${ROOT_DIR}/template/{{cookiecutter.project_name}}/pyproject.toml; \
	echo "Version updated successfully to $$VERSION"; \
	echo "Updated files:"; \
	echo "  - src/frontend/ai-blueking/package.json"; \
	echo "  - src/plugins/aidev_ai_blueking/pyproject.toml"; \
	echo "  - template/{{cookiecutter.project_name}}/requirements.txt"; \
	echo "  - template/{{cookiecutter.project_name}}/pyproject.toml"

.PHONY: release_versions
release_versions:
	@if [ -n "$(VERSION)" ]; then \
		echo "Updating all package versions to $(VERSION)..."; \
		uv run python scripts/update_versions.py "$(VERSION)"; \
	elif [ -n "$(aidev_agent_version)$(aidev_bkplugin_version)$(aidev_wxbot_version)$(aidev_template_version)$(aidev_ai_blueking_version)" ]; then \
		echo "Updating package versions (specified components only)..."; \
		uv run python scripts/update_versions.py \
			$(if $(aidev_agent_version),--aidev-agent-version "$(aidev_agent_version)") \
			$(if $(aidev_bkplugin_version),--aidev-bkplugin-version "$(aidev_bkplugin_version)") \
			$(if $(aidev_wxbot_version),--aidev-wxbot-version "$(aidev_wxbot_version)") \
			$(if $(aidev_template_version),--aidev-template-version "$(aidev_template_version)") \
			$(if $(aidev_ai_blueking_version),--aidev-ai-blueking-version "$(aidev_ai_blueking_version)"); \
	else \
		echo "Error: set VERSION=2.0.0b1 or pass at least one per-component version"; \
		echo "Example: make release_versions aidev_ai_blueking_version=2.0.0rc1"; \
		exit 1; \
	fi
	UV_PYTHON="$(ROOT_DIR)/.venv/bin/python" $(MAKE) -C "$(ROOT_DIR)/src/agent"
	UV_PYTHON="$(ROOT_DIR)/.venv/bin/python" $(MAKE) -C "$(ROOT_DIR)/src/plugins/aidev_bkplugin"
	UV_PYTHON="$(ROOT_DIR)/.venv/bin/python" $(MAKE) -C "$(ROOT_DIR)/src/plugins/aidev_wxbot"
	UV_PYTHON="$(ROOT_DIR)/.venv/bin/python" $(MAKE) -C "$(ROOT_DIR)/$(TEMPLATE_PROJECT_DIR)"

.PHONY: sync_template_sdk_versions
sync_template_sdk_versions:
	@echo "Syncing template SDK versions from repository packages..."
	@uv run python scripts/update_versions.py --sync-template-sdk-versions

.PHONY: dev
dev:
	uv run --no-sync python scripts/template_debug.py --env-file "$(env_file)"
	$(MAKE) -C '$(TEMPLATE_PROJECT_DIR)' dev

# Catch-all rule to prevent Make from complaining about unknown targets
%:
	@:
