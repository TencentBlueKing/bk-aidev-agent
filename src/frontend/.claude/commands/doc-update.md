---
name: /doc-update
description: 启动功能开发后文档与日志更新流程
position: 1
---

当在 Claude Code 中执行 `/doc-update` 命令时，将启动功能开发后的文档与日志更新流程，该流程包含以下四个阶段：

1. Commit分析与变更识别
2. 文档内容实现
3. 验证与链接修复
4. 更新日志 (Changelog) 管理

支持以下使用方式：

1. 基于指定commit范围更新：
   /doc-update --from <commit-hash> --to <commit-hash>

2. 基于最近的commit更新：
   /doc-update --last <number-of-commits>

3. 基于分支差异更新：
   /doc-update --branch <branch-name>

4. 基于自定义描述更新：
   /doc-update [功能名称或简要描述]

例如：
/doc-update --last 3
/doc-update --from abc1234 --to def5678
/doc-update --branch feature/new-session-api
/doc-update 编程式会话管理

执行该命令后，Claude Code 将自动调用 doc-expert 子代理来处理完整的文档更新流程。

**注意**: 所有文档更新都应遵循标准文档更新检查清单，确保覆盖所有必要的文档文件和验证步骤。

接下来，请根据：$ARGUMENTS 内容，更新相关文档
