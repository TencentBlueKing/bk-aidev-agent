#!/bin/bash

set -euo pipefail

exec celery -A blueapps.core.celery worker -P threads \
    -Q plugin_schedule,bkai_agent_task,bkai_agent_metric -l INFO \
    -c "${BKAI_CELERY_CONCURRENCY:-16}" --max-tasks-per-child 256
