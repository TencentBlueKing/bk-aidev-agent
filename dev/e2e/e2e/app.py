from __future__ import annotations

import os
import subprocess
import time

from .config import Config, Identity, env_bool
from .http import request


class ManagedApp:
    def __init__(self, config: Config, identity: Identity):
        self.config = config
        self.identity = identity
        self.project = config.root / "template/builtin/{{cookiecutter.project_name}}"
        self.python = self.project / ".venv/bin/python"
        self.process: subprocess.Popen | None = None
        self.log_handle = None

    def environment(self) -> dict[str, str]:
        env = os.environ.copy()
        env.update(
            {
                "PYTHONPATH": f"{self.project}:{self.config.root / 'dev/e2e'}",
                "BK_APP_CONFIG_PATH": "bk_plugin_runtime.config",
                "DJANGO_SETTINGS_MODULE": "bk_plugin.patch.plugin",
                "BKPAAS_APP_ID": "aidev_agent_e2e" if self.config.database == "mysql" else "e2e-agent",
                "BKPAAS_APP_SECRET": "local-e2e-app-secret",
                "BKPAAS_ENGINE_REGION": "ieod",
                "BKPAAS_BK_DOMAIN": "localhost",
                "AIDEV_SPACE_ID": "e2e-space",
                "AIDEV_GATEWAY_NAME": "bk-aidev",
                "BK_APIGW_STAGE": "local",
                "BK_AIDEV_APIGW_ENDPOINT": self.config.mock_url,
                "BK_SSM_ENDPOINT": self.config.mock_url,
                "BKPAAS_APIGW_OAUTH_API_URL": self.config.mock_url,
                "BK_APIGW_MANAGER_URL_TMPL": self.config.mock_url + "/api/{api_name}",
                "LLM_GW_ENDPOINT": self.config.mock_url + "/v1",
                "MESSAGE_HANDLER_TYPE": os.getenv("MESSAGE_HANDLER_TYPE", "redis"),
                "MESSAGE_REDIS_URL": os.getenv("MESSAGE_REDIS_URL", "redis://127.0.0.1:16379/0"),
                "RABBITMQ_HOST": os.getenv("RABBITMQ_HOST", "127.0.0.1"),
                "RABBITMQ_PORT": os.getenv("RABBITMQ_PORT", "25672"),
                "RABBITMQ_USER": os.getenv("RABBITMQ_USER", "aidev"),
                "RABBITMQ_PASSWORD": os.getenv("RABBITMQ_PASSWORD", "aidev-e2e"),
                "RABBITMQ_VHOST": os.getenv("RABBITMQ_VHOST", "/"),
                "BKAI_AGENT_OTEL_ENABLED": os.getenv("BKAI_AGENT_OTEL_ENABLED", "true"),
                "BKAI_AGENT_ENABLE_METRICS": os.getenv("BKAI_AGENT_ENABLE_METRICS", "true"),
                "BKAI_AGENT_OTEL_ENDPOINTS": os.getenv(
                    "BKAI_AGENT_OTEL_ENDPOINTS",
                    '[{"url":"http://127.0.0.1:4318","exporter_type":"http"}]',
                ),
                "AIDEV_STDOUT_LOG_ENABLED": "true",
                "E2E_AUTH_MOCK_ENABLED": "true",
                "E2E_USERNAME": self.identity.username,
                "BKAPP_WXAIBOT_TOKEN": os.getenv("BKAPP_WXAIBOT_TOKEN", "e2e-wxbot-token"),
                "BKAPP_WXAIBOT_ENCODING_AES_KEY": os.getenv(
                    "BKAPP_WXAIBOT_ENCODING_AES_KEY", "abcdefghijklmnopqrstuvwxyz0123456789ABCDEFG"
                ),
                "BKAPP_WXAIBOT_WS_ENABLED": "false",
            }
        )
        if self.config.database == "mysql":
            env.update(
                {
                    "MYSQL_HOST": os.getenv("MYSQL_HOST", "127.0.0.1"),
                    "MYSQL_PORT": os.getenv("MYSQL_PORT", "13306"),
                    "MYSQL_NAME": os.getenv("MYSQL_NAME", "aidev_agent_e2e"),
                    "MYSQL_USER": os.getenv("MYSQL_USER", "aidev"),
                    "MYSQL_PASSWORD": os.getenv("MYSQL_PASSWORD", "aidev-e2e"),
                    "BK_PLUGIN_DEV_USE_MYSQL": "1",
                    "BK_PLUGIN_RUNTIME_DB_HOST": os.getenv("MYSQL_HOST", "127.0.0.1"),
                    "BK_PLUGIN_RUNTIME_DB_PORT": os.getenv("MYSQL_PORT", "13306"),
                    "BK_PLUGIN_RUNTIME_DB_USER": os.getenv("MYSQL_USER", "aidev"),
                    "BK_PLUGIN_RUNTIME_DB_PWD": os.getenv("MYSQL_PASSWORD", "aidev-e2e"),
                }
            )
        else:
            env.update(
                {
                    "BK_PLUGIN_DEV_USE_MYSQL": "0",
                    "E2E_SQLITE_PATH": str(self.config.root / "dev/e2e/.runtime/agent.sqlite3"),
                }
            )
        # blueapps treats an absent BKPAAS_ENVIRONMENT as local development;
        # setting it to "dev" switches logging to the read-only PaaS /app path.
        env.pop("BKPAAS_ENVIRONMENT", None)
        return env

    def start(self) -> None:
        if not env_bool("E2E_MANAGED_APP", True):
            return
        if not self.python.is_file():
            raise RuntimeError(f"template environment is missing; run make -C dev/e2e setup ({self.python})")
        runtime = self.config.root / "dev/e2e/.runtime"
        runtime.mkdir(parents=True, exist_ok=True)
        self.log_handle = (runtime / "app.log").open("w", encoding="utf-8")
        env = self.environment()
        migrate = subprocess.run(
            [str(self.python), "bin/manage.py", "migrate", "--noinput"],
            cwd=self.project,
            env=env,
            stdout=self.log_handle,
            stderr=subprocess.STDOUT,
            timeout=180,
            check=False,
        )
        if migrate.returncode:
            raise RuntimeError(f"Django migration failed; see {runtime / 'app.log'}")
        address = self.config.app_url.removeprefix("http://").removeprefix("https://")
        self.process = subprocess.Popen(
            [str(self.python), "bin/manage.py", "runserver", address, "--noreload"],
            cwd=self.project,
            env=env,
            stdout=self.log_handle,
            stderr=subprocess.STDOUT,
        )
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                raise RuntimeError(f"Django exited with {self.process.returncode}; see {runtime / 'app.log'}")
            try:
                if request("GET", self.config.app_url + "/bk_plugin/meta/", timeout=2).status < 500:
                    return
            except OSError:
                pass
            time.sleep(0.5)
        raise RuntimeError(f"Django did not become ready; see {runtime / 'app.log'}")

    def close(self) -> None:
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)
        if self.log_handle:
            self.log_handle.close()
