SHELL := /bin/bash

OTEL_DIR := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
ROOT_DIR := $(abspath $(OTEL_DIR)/../..)
PLUGIN_DIR := $(ROOT_DIR)/src/plugins/aidev_bkplugin
PYTHON ?= $(PLUGIN_DIR)/.venv/bin/python
PODMAN ?= podman
JQ ?= jq
COMPOSE := $(PODMAN) compose -f $(OTEL_DIR)/docker-compose.yml
PROMETHEUS_DASHBOARD := $(OTEL_DIR)/grafana/dashboards/aidev-agent-metrics.json
BKMONITOR_DASHBOARD := $(OTEL_DIR)/grafana/components/aidev-agent-metrics-bkmonitor.json
BKMONITOR_DASHBOARD_FILTER := $(OTEL_DIR)/grafana/generate-bkmonitor-dashboard.jq

N ?= 3
MODELS ?= mock-log-analysis-a,mock-log-analysis-b,mock-log-analysis-c
HANDLER ?= all
ITERATIONS ?= 400
INTERVAL ?= 1.5
SEED ?= 20260809

MOCK_COMMAND = env PYTHONPATH="$(ROOT_DIR)/src/agent:$(PLUGIN_DIR):$(ROOT_DIR)" \
	"$(PYTHON)" "$(OTEL_DIR)/mock_agent_metrics.py" \
	-n "$(N)" --models "$(MODELS)" --handler "$(HANDLER)" \
	--iterations "$(ITERATIONS)" --interval "$(INTERVAL)" --seed "$(SEED)"

.PHONY: help start stop up down status logs mock test metrics dashboard-bkmonitor

help:
	@echo "Local OpenTelemetry observability"
	@echo "  make start       Start Podman services and run mock in foreground"
	@echo "  make stop        Stop Podman services"
	@echo "  make status      Show Podman container status"
	@echo "  make logs        Follow Podman service logs"
	@echo "  make mock        Run mock in the foreground"
	@echo "  make test        Run exporter and local observability tests"
	@echo "  make metrics     Print the Collector Prometheus endpoint"
	@echo "  make dashboard-bkmonitor  Regenerate the standalone BK Monitor dashboard"
	@echo ""
	@echo "Parameters: N=3 MODELS=a,b,c HANDLER=all ITERATIONS=400 INTERVAL=1.5 SEED=20260809"

start: up mock

stop: down

up:
	$(COMPOSE) up -d

down:
	$(COMPOSE) down

status:
	$(COMPOSE) ps

logs:
	$(COMPOSE) logs -f

mock:
	$(MOCK_COMMAND)

test:
	cd "$(PLUGIN_DIR)" && env PYTHONPATH="$(ROOT_DIR)/src/agent:$(PLUGIN_DIR):$(ROOT_DIR)" \
		"$(PYTHON)" -m pytest --ds=tests.settings -c "$(PLUGIN_DIR)/pyproject.toml" \
		"$(PLUGIN_DIR)/tests/services/test_otel_metrics.py" "$(OTEL_DIR)/tests"

metrics:
	curl -fsS http://localhost:8889/metrics

dashboard-bkmonitor:
	mkdir -p "$(dir $(BKMONITOR_DASHBOARD))"
	$(JQ) -f "$(BKMONITOR_DASHBOARD_FILTER)" "$(PROMETHEUS_DASHBOARD)" > "$(BKMONITOR_DASHBOARD).tmp"
	mv "$(BKMONITOR_DASHBOARD).tmp" "$(BKMONITOR_DASHBOARD)"
