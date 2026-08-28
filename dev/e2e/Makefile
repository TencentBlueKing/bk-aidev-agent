SHELL := /bin/bash

E2E_DIR := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
ROOT_DIR := $(abspath $(E2E_DIR)/../..)
TEMPLATE_DIR := $(ROOT_DIR)/template/builtin/{{cookiecutter.project_name}}
ENV_FILE ?= $(if $(wildcard $(E2E_DIR)/.env),$(E2E_DIR)/.env,$(E2E_DIR)/.env.example)
PODMAN ?= podman
COMPOSE := $(PODMAN) compose -f $(E2E_DIR)/docker-compose.yml
PYTHON ?= python3
MODULES ?= api,ai-blueking,metrics,wxbot
HEADLESS ?= true
DB ?= sqlite

.PHONY: help setup deps-up deps-down observability-up observability-down up down run browser test report-open \
	api ai-blueking metrics wxbot

help:
	@echo "bk-aidev-agent local E2E"
	@echo "  make setup              Install template runtime and link local SDK/plugin sources"
	@echo "  make up                 Start real Redis, RabbitMQ and local observability (SQLite by default)"
	@echo "  make up DB=mysql        Also start the optional real MySQL 5.7 profile"
	@echo "  make run                Run the complete API/AI/metrics/WeCom suite; write one HTML report"
	@echo "  make api                Run one module (also: ai-blueking/metrics/wxbot)"
	@echo "  make run HEADLESS=false Run headed/browser-friendly mode"
	@echo "  make browser            Open headed browser checks (default: AI whale)"
	@echo "  make test               Run fast framework regression tests"
	@echo "  make down               Stop local dependencies"

setup:
	E2E_ENV_FILE="$(ENV_FILE)" $(PYTHON) "$(ROOT_DIR)/scripts/template_debug.py" --env-file "$(ENV_FILE)"
	cd "$(TEMPLATE_DIR)" && uv sync --frozen --inexact --no-dev

deps-up:
	$(COMPOSE) $(if $(filter mysql,$(DB)),--profile mysql,) up -d
	E2E_DB="$(DB)" PYTHONPATH="$(E2E_DIR)" $(PYTHON) -m e2e.wait

deps-down:
	$(COMPOSE) --profile mysql down

observability-up:
	$(MAKE) -C "$(ROOT_DIR)/dev/otel" up

observability-down:
	$(MAKE) -C "$(ROOT_DIR)/dev/otel" down

up: deps-up observability-up

down: deps-down observability-down

run:
	@set -o pipefail; \
	E2E_DB="$(DB)" E2E_ENV_FILE="$(ENV_FILE)" PYTHONPATH="$(E2E_DIR)" \
		$(PYTHON) -m e2e.runner --modules "$(MODULES)" $(if $(filter true 1 yes,$(HEADLESS)),--headless,--no-headless)

browser:
	$(MAKE) run MODULES=$(MODULES) HEADLESS=false DB=$(DB) ENV_FILE="$(ENV_FILE)"

api ai-blueking metrics wxbot:
	$(MAKE) run MODULES=$@ HEADLESS=$(HEADLESS) DB=$(DB) ENV_FILE="$(ENV_FILE)"

test:
	PYTHONPATH="$(E2E_DIR)" $(PYTHON) -m unittest discover -s "$(E2E_DIR)/tests" -v

report-open:
	@echo "$(E2E_DIR)/reports/latest.html"
