from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from e2e.config import Config, Identity, configured_identity, load_env_file
from e2e.report import CaseResult, RunReport, redact, write_report
from e2e.trace import ApiTraceRecorder


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
        value = redact(
            {
                "access_token": "secret",
                "nested": ["a-secret-b"],
                "prompt_tokens": 8,
                "url": "http://localhost/callback?msg_signature=signed-value&nonce=1",
            },
            ("secret",),
        )
        self.assertEqual(value["access_token"], "***MASKED***")
        self.assertEqual(value["nested"], ["a-***MASKED***-b"])
        self.assertEqual(value["prompt_tokens"], 8)
        self.assertEqual(value["url"], "http://localhost/callback?msg_signature=***MASKED***&nonce=1")

    def test_html_is_written_for_failed_run(self):
        report = RunReport("2026-08-28T00:00:00+08:00", ["api"], cases=[CaseResult("api", "case", "failed", 1)])
        with tempfile.TemporaryDirectory() as directory:
            path = write_report(report, Path(directory))
            self.assertTrue(path.is_file())
            self.assertIn("1 failed", path.read_text(encoding="utf-8"))

    def test_html_contains_conversation_and_complete_api_exchange(self):
        report = RunReport(
            "2026-08-28T00:00:00+08:00",
            ["ai-blueking"],
            cases=[CaseResult("ai-blueking", "智能体对话", "passed", 8, coverage="同步问答与会话内容写入")],
            conversations=[{"case": "chat", "messages": [{"role": "user", "content": "发送的会话内容"}]}],
            api_calls=[
                {
                    "sequence": 1,
                    "source": "agent-to-remote-mock",
                    "module": "ai-blueking",
                    "case": "chat",
                    "method": "POST",
                    "url": "http://mock/v1/chat/completions",
                    "request_headers": {"Authorization": "Bearer trace-secret"},
                    "request_body": {"messages": [{"role": "user", "content": "发送的会话内容"}]},
                    "status": 200,
                    "response_headers": {"Content-Type": "application/json"},
                    "response_body": {"choices": [{"message": {"content": "回复内容"}}]},
                    "duration_ms": 8,
                    "error": "",
                }
            ],
        )
        with tempfile.TemporaryDirectory() as directory:
            path = write_report(report, Path(directory), ("trace-secret",))
            document = path.read_text(encoding="utf-8")
        self.assertIn("发送的会话内容", document)
        self.assertIn("功能健康概览", document)
        self.assertIn("未列出的功能不代表已验证", document)
        self.assertIn("同步问答与会话内容写入", document)
        self.assertIn("/v1/chat/completions", document)
        self.assertIn("请求 Headers", document)
        self.assertIn("***MASKED***", document)
        self.assertNotIn("trace-secret", document)


class TraceTests(unittest.TestCase):
    def test_calls_keep_sequence_and_case_context(self):
        recorder = ApiTraceRecorder()
        with recorder.case("api", "session"):
            call = recorder.start_call(source="test-runner", method="post", url="http://mock/session")
            recorder.finish_call(call, status=200, response_body={"ok": True}, duration_ms=3)
        recorded = recorder.snapshot()
        self.assertEqual(recorded[0]["sequence"], 1)
        self.assertEqual(recorded[0]["module"], "api")
        self.assertEqual(recorded[0]["case"], "session")
        self.assertEqual(recorded[0]["response_body"], {"ok": True})


if __name__ == "__main__":
    unittest.main()
