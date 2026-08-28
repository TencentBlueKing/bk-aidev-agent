from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from e2e.config import Config, Identity, configured_identity, load_env_file
from e2e.report import CaseResult, RunReport, redact, write_report


class ConfigTests(unittest.TestCase):
    def test_access_token_has_priority(self):
        with patch.dict(os.environ, {"E2E_ACCESS_TOKEN": "top-secret", "E2E_USERNAME": "alice"}, clear=True):
            identity = configured_identity()
        self.assertEqual(identity.mode, "access_token")
        self.assertEqual(identity.username, "alice")
        self.assertEqual(identity.access_token, "top-secret")

    def test_username_fallback(self):
        with patch.dict(os.environ, {"E2E_USERNAME": "alice"}, clear=True):
            self.assertEqual(configured_identity(), Identity("alice", "username"))

    def test_dotenv_does_not_override_explicit_environment(self):
        with tempfile.TemporaryDirectory() as directory:
            env_file = Path(directory) / ".env"
            env_file.write_text("E2E_USERNAME=from-file\n", encoding="utf-8")
            with patch.dict(os.environ, {"E2E_USERNAME": "explicit"}, clear=True):
                load_env_file(env_file)
                self.assertEqual(os.environ["E2E_USERNAME"], "explicit")

    def test_database_defaults_to_sqlite_and_rejects_unknown_backend(self):
        with tempfile.TemporaryDirectory() as directory:
            env_file = Path(directory) / ".env"
            env_file.write_text("E2E_USERNAME=alice\n", encoding="utf-8")
            with patch.dict(os.environ, {"E2E_ENV_FILE": str(env_file)}, clear=True):
                self.assertEqual(Config.from_env("api").database, "sqlite")
            with (
                patch.dict(os.environ, {"E2E_ENV_FILE": str(env_file), "E2E_DB": "postgres"}, clear=True),
                self.assertRaisesRegex(ValueError, "E2E_DB must be sqlite or mysql"),
            ):
                Config.from_env("api")


class ReportTests(unittest.TestCase):
    def test_recursive_redaction(self):
        value = redact({"access_token": "secret", "nested": ["a-secret-b"]}, ("secret",))
        self.assertEqual(value["access_token"], "***MASKED***")
        self.assertEqual(value["nested"], ["a-***MASKED***-b"])

    def test_html_is_written_for_failed_run(self):
        report = RunReport("2026-08-28T00:00:00+08:00", ["api"], cases=[CaseResult("api", "case", "failed", 1)])
        with tempfile.TemporaryDirectory() as directory:
            path = write_report(report, Path(directory))
            self.assertTrue(path.is_file())
            self.assertIn("1 failed", path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
