---
name: /doc-update
description: 启动功能开发后文档与日志更新流程
position: 1
---

当在 Claude Code 中执行 `/doc-update` 命令时，将启动功能开发后的文档与日志更新流程，该流程包含以下四个阶段：

1. 需求分析与文档影响评估
2. 文档内容实现
3. 验证与链接修复
4. 更新日志 (Changelog) 管理

使用方法：
/doc-update [功能名称或简要描述]

例如：
/doc-update 编程式会话管理
/doc-update 新增用户偏好设置功能

执行该命令后，Claude Code 将自动调用 doc-expert 子代理来处理完整的文档更新流程。

**注意**: 所有文档更新都应遵循标准文档更新检查清单，确保覆盖所有必要的文档文件和验证步骤。

接下来，请根据：$ARGUMENTS 内容，更新相关文档
