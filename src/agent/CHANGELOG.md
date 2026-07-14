# CHANGELOG

## 2026-07-14 · Craw 适配层（packages/craw）

- **背景**：AIDEV 插件对接 CLI 形态内核（OpenClaw / Hermes）此前散落在业务插件的 extend 层，各写一套转发与 registry 覆盖。
- **变更**：新增 `aidev_agent/packages/craw/`——统一后端抽象（`OpenClawBackend` / `HermesBackend`）+ `CrawCompletionAgent`（CHAT 转发、SSE→AG-UI）+ `CrawSyncer`（周期 read/write）+ `enable_chat_takeover()`（`BKAI_CRAW_BACKEND` env 门控，未设零影响）；用户身份经 `X-Bkai-Access-Token` 透传（对齐 bkai-cli 池模式契约），日志只落 identity 哈希。`httpx` 转为显式依赖。
- **验证**：单测 `tests/packages/craw/` 29 例（`make test path=tests/packages/craw`）；colima 双容器端到端三变体各两轮 ALL PASS——openclaw 直连（`run.sh`）、hermes gateway api_server（`run-hermes.sh`）、业务插件集成（`run-plugin.sh`，整链 `/chat_completion/` 非流式 + AG-UI 流式；插件侧配套一个 extend 层薄壳触发 `enable_chat_takeover()`）。
- **隔离验证**（`run-isolation.sh`，真实网关环境）：REAL/FAKE 双用户 token 三层闭环——判定面（MCP 网关 initialize 建连即校验，REAL 通过 / FAKE 400）、隔离链（bkai-cli 池模式：identityId 分流独立内核、mcp-probe accessible/rejected、用户 token 不落盘仅 egress 内存注入）、对话行为面（同题问两身份：REAL 列出可用 MCP 工具并实调成功，FAKE 如实报无可用 MCP；与 egress 传输层流水吻合）。SDK `CrawIdentity.identity_id` 与池路由 identityId 同 sha256[:16] 契约实测一致。
- **注**：文档见 [docs/craw-adapter.md](docs/craw-adapter.md)。
