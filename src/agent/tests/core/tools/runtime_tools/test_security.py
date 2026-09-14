# -*- coding: utf-8 -*-
"""命令允许列表 / AST 校验（``packages.security.command``）测试。

本文件覆盖：

- 允许列表数据表与参数限制类（纯数据/纯谓词，行为不变）；
- 路径规范化 ``validate_path`` 与脚本目录判定；
- ``validate_command`` 的允许 / 拒绝 / 边界与真实结构语义
  （注释、替换、进程替换、重定向、动态执行内容）；
- 新增配置覆盖。
"""

from __future__ import annotations

import pytest
from aidev_agent.packages.security.command.command_allowlist import ALLOWED_COMMANDS
from aidev_agent.packages.security.command.command_blocklist import AllowedFlagsOnly
from aidev_agent.packages.security.command.command_parser import _check_script_path_allowed, _normalize_command_name
from aidev_agent.packages.security.command.command_security import (
    validate_command,
    validate_path,
)
from aidev_agent.pydantic_models import SecurityCommandSettings


def _settings(**overrides) -> SecurityCommandSettings:
    """把逐字段覆盖值收成单一 settings 对象（``validate_command`` 的唯一配置入口）。

    基线**显式**开启结构约束族（``enable_command_syntax_rules=True``）与动态执行内容规则
    （``enable_command_blocklist_dynamic_exec=True``），不依赖模型默认（二者默认均为
    ``False``）；本文件多处断言这些规则命中 / 拒绝。调用方显式传入的
    同名覆盖优先。始终构造实例，绝不返回 ``None``：``validate_command`` 的该参数
    必填，省略即 ``TypeError``（缺失配置属 fail-open）。
    """
    overrides.setdefault("enable_command_syntax_rules", True)
    overrides.setdefault("enable_command_blocklist_dynamic_exec", True)
    return SecurityCommandSettings(**overrides)


def _verdict(command: str, **kwargs) -> str:
    return validate_command(command, security_command_settings=_settings(**kwargs)).verdict


def _rule_ids(command: str, **kwargs) -> set[str]:
    report = validate_command(command, security_command_settings=_settings(**kwargs))
    return {rule.rule_id for finding in report.findings for rule in finding.rules} | {
        item.rule_id for item in report.structure_findings
    }


#: 「放行未知命令」的通道：经 ``rules`` 下发一条 allow 规则（``rule_id`` 未登记即新增，无需前缀）。
#: 12-02 起请求级旁路参数不再影响判定；12-04 删除其字段定义（C-03）。
_ALLOW_MYCMD_RULE = {
    "rule_id": "allow_mycmd",
    "verdict": "allow",
    "justification": "放行 mycmd",
    "tokens": ["mycmd"],
}


class TestAllowedCommands:
    """Test ALLOWED_COMMANDS allowlist definitions."""

    def test_allowed_commands_is_frozenset(self):
        assert isinstance(ALLOWED_COMMANDS, frozenset)

    @pytest.mark.parametrize(
        "command",
        [
            "pwd",
            "uname",
            "df",
            "free",
            "ls",
            "cat",
            "stat",
            "cp",
            "mv",
            "mkdir",
            "grep",
            "head",
            "tail",
            "sed",
            "awk",
            "diff",
            "echo",
            "sleep",
            "true",
            "tar",
            "gzip",
            "bash",
            "sh",
            "python",
            "python3",
        ],
    )
    def test_allowed_commands_contains_categories(self, command):
        assert command in ALLOWED_COMMANDS

    @pytest.mark.parametrize(
        "command",
        [
            "rm",
            "kill",
            "pkill",
            "killall",
            "curl",
            "wget",
            "nc",
            "netcat",
            "sudo",
            "su",
            "chmod",
            "chown",
            "passwd",
            "dd",
            "mkfs",
            "ssh",
            "scp",
            "rsync",
            "iptables",
            "mount",
            "umount",
            "ps",
            "top",
            "netstat",
            "ss",
            "nohup",
            "setsid",
            "disown",
            "screen",
            "tmux",
        ],
    )
    def test_dangerous_commands_not_in_allowlist(self, command):
        """这些命令不在允许列表内——注意 ``cp`` / ``mv`` / ``mkdir`` **刻意在**列表内（文件操作放行）。"""
        assert command not in ALLOWED_COMMANDS


class TestParameterRestrictions:
    """Test parameter restriction classes."""

    def test_allowed_flags_only_allows_valid(self):
        restriction = AllowedFlagsOnly(flags={"", "-s", "-v"})
        for args in ([], ["-s"], ["-v"], ["-s", "/tmp"]):
            ok, _ = restriction.is_allowed(args)
            assert ok

    def test_allowed_flags_only_rejects_invalid(self):
        restriction = AllowedFlagsOnly(flags={"", "-s", "-v"})
        ok, reason = restriction.is_allowed(["-a"])
        assert not ok
        assert "不允许" in reason

    def test_allowed_flags_only_allows_non_flags(self):
        restriction = AllowedFlagsOnly(flags={"", "-h"})
        ok, _ = restriction.is_allowed(["/tmp", "file.txt"])
        assert ok


class TestNormalizeCommandName:
    """Test command name normalization."""

    def test_plain_command_name(self):
        assert _normalize_command_name("ls") == "ls"
        assert _normalize_command_name("cat") == "cat"
        assert _normalize_command_name("python3") == "python3"

    def test_absolute_path(self):
        assert _normalize_command_name("/bin/ls") == "ls"
        assert _normalize_command_name("/usr/bin/python3") == "python3"

    def test_relative_path(self):
        assert _normalize_command_name("./ls") == "ls"

    @pytest.mark.parametrize("name", ["../bin/cat", "../../bin/rm"])
    def test_path_traversal_rejected(self, name):
        with pytest.raises(ValueError, match="路径遍历"):
            _normalize_command_name(name)

    def test_empty_command_name(self):
        with pytest.raises(ValueError, match="空命令名"):
            _normalize_command_name("")

    def test_strips_whitespace(self):
        assert _normalize_command_name("  ls  ") == "ls"


class TestScriptPathHelpers:
    """脚本目录判定（保持既有精确/子目录政策）。"""

    @pytest.mark.parametrize("path", ["/workspace/script.py", "/workspace/proj/script.py"])
    def test_allowed(self, path):
        ok, _ = _check_script_path_allowed(path, ["/workspace"])
        assert ok

    @pytest.mark.parametrize("path", ["/etc/script.py", "/other/script.py"])
    def test_not_allowed(self, path):
        ok, reason = _check_script_path_allowed(path, ["/workspace"])
        assert not ok
        assert "不在允许" in reason

    def test_traversal_rejected(self):
        ok, _ = _check_script_path_allowed("../evil.py", ["/workspace"])
        assert not ok

    def test_empty_path(self):
        ok, reason = _check_script_path_allowed("", ["/workspace"])
        assert not ok
        assert "未指定" in reason or "遍历" in reason


class TestValidateCommandAllowed:
    """``validate_command`` 放行用例。"""

    @pytest.mark.parametrize(
        "command",
        [
            "pwd",
            "ls",
            "cat file.txt",
            "echo hello",
            "date",
            "whoami",
            "ls -la /tmp",
            "uname -s",
            "df -h",
            "grep pattern file.txt",
            "head -n 20 file.txt",
            "tail -f file.txt",
            "wc -l file.txt",
            "sort file.txt",
            "awk '{print $1}' file.txt",
            "sed s/foo/bar/g file.txt",
        ],
    )
    def test_simple_allowed_commands(self, command):
        assert _verdict(command) == "allow"

    @pytest.mark.parametrize(
        "command",
        [
            "ls /tmp && pwd",
            "cd /tmp; ls; pwd",
            "ls || echo failed",
            "cat file.txt | grep pattern",
            "cat file.txt | grep pattern | wc -l",
        ],
    )
    def test_composite_allowed_commands(self, command):
        """复合结构与管道只要每个内部命令都通过即放行。"""
        assert _verdict(command) == "allow"

    @pytest.mark.parametrize("command", ["bash -c 'ls /tmp'", "bash -c 'ls / && pwd'", "sh -c 'ls /tmp'"])
    def test_static_shell_c_allowed(self, command):
        assert _verdict(command) == "allow"

    def test_comment_after_command(self):
        assert _verdict("echo hello # this is a comment") == "allow"

    def test_quoted_pipe(self):
        assert _verdict('echo "hello | world"') == "allow"

    def test_long_command(self):
        """5005 字符长命令仍放行（默认长度预算的回归基座）。"""
        assert _verdict("echo " + "A" * 5000) == "allow"

    @pytest.mark.parametrize("command", ["uname", "df"])
    def test_no_args_allowed(self, command):
        assert _verdict(command) == "allow"

    @pytest.mark.parametrize(
        "command",
        [
            "python /workspace/script.py",
            "python3 /app/script.py",
            "python script.py",
            "python3 -m pytest",
            "python3 -u script.py",
            "cd /app && python3 script.py",
            "python /etc/script.py",
        ],
    )
    def test_python_static_execution_policy(self, command):
        """Python **静态脚本 / -m** 政策保持（不做脚本目录限制）。

        CR-01：``-c`` 内联代码已移出本「允许」集（见
        :meth:`test_python_inline_code_is_blocked`）—— 内联代码无法静态确定执行内容，
        按 D-09 归类为动态执行内容（默认 block），旧期望 ``allow`` 已被用户批准推翻。
        """
        assert _verdict(command) == "allow"

    @pytest.mark.parametrize("command", ["python -c 'print(1)'", "python3 -c 'print(hello)'"])
    def test_python_inline_code_is_blocked(self, command):
        """CR-01：``python -c`` 内联代码 → 动态执行内容 block（不再落到允许列表 allow）。"""
        report = validate_command(command, security_command_settings=_settings())
        assert report.verdict == "block"
        assert "dynamic:execution_content" in {item.rule_id for item in report.structure_findings}

    def test_shell_with_allowed_script_path(self):
        assert _verdict("bash /workspace/script.sh") == "allow"

    @pytest.mark.parametrize(
        "command",
        [
            "ls -la /root/.cursor/ 2>/dev/null",
            "cat /etc/passwd >/dev/null",
            "ls -la /root/ 2> /dev/null",
            "ls > /dev/null",
        ],
    )
    def test_redirect_to_dev_null_allowed(self, command):
        """输出重定向到精确 ``/dev/null`` 目标豁免。"""
        assert _verdict(command) == "allow"


class TestValidateCommandRejected:
    """``validate_command`` 拒绝用例（按 AST 新契约）。"""

    @pytest.mark.parametrize("command", ["mycmd file.txt", "curl example.com", "sudo kill 123", "kill 123"])
    def test_grey_list_commands_are_review(self, command):
        """不在允许列表且未命中危险规则 -> review（可走审批），不是 block。

        ``sudo`` 用例取**内层不在允许列表**的命令（``kill``）：允许列表已按内层命令判定，
        ``sudo ls`` / ``sudo cat ...`` 现在是 allow，不再是灰名单样本。
        """
        report = validate_command(command, security_command_settings=_settings())
        assert report.verdict == "review"
        # **零规则命中**（2026-09-24）：不在允许列表也不在黑名单 → ``rules == []``。
        # 原断言 ``whitelist:review`` 命中，但该"规则"已删除（review 不是规则）。
        assert all(not finding.rules for finding in report.findings if finding.command_name in command)

    @pytest.mark.parametrize("command", ["uname -a", "df -a"])
    def test_forbidden_flag_is_block(self, command):
        report = validate_command(command, security_command_settings=_settings())
        assert report.verdict == "block"
        assert "args:restricted" in {rule.rule_id for finding in report.findings for rule in finding.rules}

    def test_background_execution_rejected(self):
        report = validate_command("sleep 100 &", security_command_settings=_settings())
        assert report.verdict == "block"
        assert "syntax:background" in {item.rule_id for item in report.structure_findings}

    @pytest.mark.parametrize("command", ["nohup python server.py", "nohup python server.py &"])
    def test_nohup_rejected(self, command):
        assert _verdict(command) == "block"

    def test_substitution_with_dangerous_inner_rejected(self):
        """D-07：真替换按其**内部命令**判定（``mycmd`` 不在允许列表 -> review）。"""
        report = validate_command("echo $(mycmd file)", security_command_settings=_settings())
        assert report.verdict == "review"
        assert len(report.findings) == 2

    @pytest.mark.parametrize("command", ["echo $(pwd)", "echo `id`", "diff <(ls dir1) <(ls dir2)"])
    def test_safe_substitutions_allowed(self, command):
        """``$(...)`` / 反引号 / 进程替换不再仅因语法存在被拒。"""
        assert _verdict(command) == "allow"

    @pytest.mark.parametrize("command", ["ls > output.txt", "cat < file.txt"])
    def test_redirection_rejected(self, command):
        report = validate_command(command, security_command_settings=_settings())
        assert report.verdict == "block"
        assert "syntax:redirect" in {item.rule_id for item in report.structure_findings}

    def test_here_string_rejected(self):
        assert _verdict("cat <<< hello") == "block"

    def test_brace_expansion_rejected(self):
        assert _verdict("echo {a,b,c}") == "block"

    def test_path_traversal_rejected(self):
        assert _verdict("../../bin/ls") == "block"

    @pytest.mark.parametrize(
        "command",
        ["/bin/rm -rf /", 'bash -c "rm -rf /"', "bash -c 'bash -c \"rm -rf /\"'"],
    )
    def test_dangerous_commands_and_wrappers_rejected(self, command):
        """``/bin/rm`` 只是灰名单（review），命中黑名单 label 才 block。"""
        assert _verdict(command) == "block"

    def test_bash_c_no_arg_rejected(self):
        assert _verdict("bash -c") == "block"

    @pytest.mark.parametrize("command", ["", "   "])
    def test_empty_command_rejected(self, command):
        report = validate_command(command, security_command_settings=_settings())
        assert report.verdict == "block"
        assert "empty:no_executable_command" in {item.rule_id for item in report.structure_findings}

    def test_comment_only_rejected(self):
        report = validate_command("# this is a comment", security_command_settings=_settings())
        assert report.verdict == "block"
        assert "empty:no_executable_command" in {item.rule_id for item in report.structure_findings}

    def test_null_byte_rejected(self):
        report = validate_command("echo hello\0world", security_command_settings=_settings())
        assert report.verdict == "block"
        assert "input:null_byte" in {item.rule_id for item in report.structure_findings}

    def test_unmatched_quotes_rejected(self):
        report = validate_command('echo "unclosed', security_command_settings=_settings())
        assert report.verdict == "block"
        assert "parse:syntax_error" in {item.rule_id for item in report.structure_findings}

    @pytest.mark.parametrize("command", ["setsid cmd", "disown", "screen -dmS s", "tmux new -d"])
    def test_forbidden_commands_rejected(self, command):
        report = validate_command(
            command,
            security_command_settings=SecurityCommandSettings(
                enable_command_blocklist=False, enable_command_syntax_rules=True
            ),
        )
        assert report.verdict == "block"
        assert "syntax:forbidden_command" in {item.rule_id for item in report.structure_findings}

    def test_pipe_ampersand_rejected(self):
        report = validate_command("ls |& grep pattern", security_command_settings=_settings())
        assert report.verdict == "block"
        assert "syntax:pipe_amp" in {item.rule_id for item in report.structure_findings}


class TestValidateCommandEdgeCases:
    """边界与真实结构语义。"""

    @pytest.mark.parametrize(
        "command",
        [
            "cd /app && echo \"sys.path.append('/app/scripts'); print('hello')\"",
            "bash -c \"echo 'test' && echo 'done'\"",
            'echo "hello" && echo "world"',
            "echo 'say \"hello\"' && ls",
        ],
    )
    def test_complex_nested_quotes_allowed(self, command):
        """嵌套引号命令不得因引号组合被误拒。"""
        assert _verdict(command) == "allow"

    def test_multiple_pipes_all_checked(self):
        assert _verdict("cat file.txt | grep pattern | mycmd file") == "review"

    def test_and_operator_with_dangerous_second(self):
        assert _verdict("cd /tmp && rm -rf /") == "block"

    def test_max_depth_budget_end_to_end(self):
        """深度超限由 ``max_depth`` 配置驱动并经真实入口断言（不再直调内部函数）。"""
        report = validate_command('bash -c "ls"', security_command_settings=SecurityCommandSettings(max_depth=1))
        assert report.verdict == "block"
        assert "budget:max_depth" in {item.rule_id for item in report.structure_findings}

    def test_unquoted_glob_command_name_is_dynamic(self):
        """执行位置的未引用 glob 无法静态确定 -> 动态策略默认 block。"""
        report = validate_command("*.sh", security_command_settings=_settings())
        assert report.verdict == "block"
        assert "dynamic:execution_content" in _rule_ids("*.sh")

    def test_quoted_glob_command_name_is_static_review(self):
        """被引号保护的 glob 是静态字面，未命中允许列表则为 review（不是动态 block）。"""
        report = validate_command("'*.sh'", security_command_settings=_settings())
        assert report.verdict == "review"

    def test_wildcard_args_allowed(self):
        assert _verdict("ls *.py") == "allow"
        assert _verdict("ls file?.txt") == "allow"


class TestAllowRulesReachAllowlist:
    """放行未知命令**唯一**的通道是经 ``rules`` 下发一条 allow 规则（未登记 id 即新增）。

    迁移自 12-02 的「请求级旁路参数不再影响 allow 判定」用例；该字段的**定义**已在
    12-04 删除（C-03 / 用户硬目标）。理由：请求级旁路参数只能加**命令名**、不能带参数，
    而 ``rules`` 通道两者都能表达，两套机制并存必然漂移。

    与 ``test_provider.py`` 的 ``TestAllowRulesReachAllowlistEndToEnd`` 互补：
    本组直调 ``validate_command``，只证明**原语**可用；那组经生产装配路径钉住
    ``build_rule_set`` 的合并连线。
    """

    def test_allow_rule_permits_only_when_declared(self):
        """能力断言：未下发 → ``review``；下发 allow 规则 → ``allow``。"""
        assert _verdict("mycmd --version") == "review"
        assert _verdict("mycmd --version", rules=[_ALLOW_MYCMD_RULE]) == "allow"

    @pytest.mark.parametrize(
        "command, rule_id",
        [
            ("echo x > /etc/passwd", "syntax:redirect"),
            ("echo {a,b}", "syntax:brace_expansion"),
            ("sleep 1 &", "syntax:background"),
        ],
    )
    def test_allow_rules_do_not_weaken_hard_limits(self, command, rule_id):
        """承重墙（**不得删除**）：放行规则只影响命令名成员判定，不削弱无条件节点限制。

        原用例经「命令名列表」请求级旁路参数（``["echo", "sleep"]``）注入；
        现改经两条 allow 规则 —— **语义等价**（都是「echo / sleep 名字命中即
        放行」）。故这三条命令的结论必须**逐条不变**：仍因**结构层**规则被判 ``block``。
        「命令名被允许」与「调用形态被无条件拒绝」是两回事，本用例钉住前者不会吃掉后者。
        """
        report = validate_command(
            command,
            security_command_settings=SecurityCommandSettings(
                enable_command_syntax_rules=True,
                rules=[
                    {
                        "rule_id": "allow_echo",
                        "verdict": "allow",
                        "justification": "放行 echo",
                        "tokens": ["echo"],
                    },
                    {
                        "rule_id": "allow_sleep",
                        "verdict": "allow",
                        "justification": "放行 sleep",
                        "tokens": ["sleep"],
                    },
                ],
            ),
        )
        assert report.verdict == "block"
        assert rule_id in {item.rule_id for item in report.structure_findings}


class TestReportShape:
    """唯一报告契约（无旧 ``ValidationResult`` / ``rejection_category`` 适配）。"""

    def test_allow_findings_carry_allowlist_success(self):
        report = validate_command("ls", security_command_settings=_settings())
        assert report.verdict == "allow"
        assert report.findings[0].rule_ids == ("allowlist:allowed",)
        assert report.is_allowed()

    def test_report_has_only_four_fields(self):
        report = validate_command("ls", security_command_settings=_settings())
        assert set(report.__dataclass_fields__) == {"verdict", "sources", "findings", "structure_findings"}

    def test_old_result_attributes_are_gone(self):
        report = validate_command("ls", security_command_settings=_settings())
        for attribute in ("is_allowed", "reason", "rejected_command", "rejection_category"):
            assert not isinstance(getattr(report, attribute, None), (bool, str))


class TestScriptDirFallback:
    """默认脚本目录的真源是模型字段（``_DEFAULT_*`` 模块常量已删除）。"""

    def test_default_script_dirs_not_empty(self):
        assert len(SecurityCommandSettings().allowed_script_dirs) > 0

    def test_script_dir_override_reaches_script_path_rule(self):
        """``allowed_script_dirs`` 覆盖影响 ``syntax:script_path``（shell 脚本走目录政策）。"""
        report = validate_command(
            "bash /nonexistent-dir/phase10.sh",
            security_command_settings=SecurityCommandSettings(
                allowed_script_dirs=["/workspace"], enable_command_syntax_rules=True
            ),
        )
        assert report.verdict == "block"
        assert "syntax:script_path" in {rule.rule_id for finding in report.findings for rule in finding.rules}


class TestValidatePath:
    """Test validate_path function from security module."""

    @pytest.mark.parametrize(
        "path, expected",
        [("foo/bar", "foo/bar"), ("/foo/bar", "/foo/bar"), ("/./foo//bar", "/foo/bar"), ("a/../b", "b")],
    )
    def test_validate_path_normalizes(self, path, expected):
        assert validate_path(path) == expected

    def test_validate_path_prevents_traversal(self):
        with pytest.raises(ValueError, match="Path traversal not allowed"):
            validate_path("../etc/passwd")

    def test_validate_path_tilde_passes_through(self):
        assert validate_path("~") == "~"
        assert validate_path("~/.bashrc") == "~/.bashrc"

    def test_validate_path_windows_absolute_rejected(self):
        with pytest.raises(ValueError, match="Windows absolute paths are not supported"):
            validate_path("C:/Users/file.txt")

    def test_validate_path_allowed_prefixes(self):
        assert validate_path("/data/file.txt", allowed_prefixes=["/data/", "/workspace/"]) == "/data/file.txt"

    def test_validate_path_not_in_allowed_prefixes(self):
        with pytest.raises(ValueError, match="must start with one of"):
            validate_path("/etc/file.txt", allowed_prefixes=["/data/", "/workspace/"])
