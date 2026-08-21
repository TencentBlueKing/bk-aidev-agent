# CHANGELOG

## 2026-08-21 · CrawSyncer 多产物 commit 事务化 + 隔离模板

- **变更**：`CrawSyncer` 提交阶段在第二次及后续 rename 失败时，从 backup 完整回滚全部正式文件，不再出现「新 SOUL + 旧 agent-config」。staging 文件名带周期 uuid；同一 craw home 提交持排它锁。官方插件模板 opt-in 挂载 `enable_chat_takeover()`，并增加 `agent_runtime=craw` 隔离 overlay（Dockerfile / supervisor）。凭据与环境域名不进模板。
- **验证**：`tests/packages/craw/` 91 → 93（含第二次 commit 失败回滚、重叠周期串行化）。

## 2026-07-14 · CrawSyncer 扩展全配置同步

- **变更**：`CrawSyncer` 从「只写 `SOUL.md`」泛化为「同步一组配置产物」——新增 `artifacts_provider()` 回调（`{相对路径: 内容}`，逐产物写入 + 读回校验）；新增 `agent_config_to_artifacts(config)` 把平台 `AgentConfig` 渲染成 `SOUL.md`（Prompt）+ `agent-config.json`（聚合 MCP / Skills / tools）。`soul_provider` 与 `soul_written_bytes` / `soul_verified` 保留为向后兼容别名。
- **范围**：同步 Prompt / MCP / Skills 三类（平台 `AgentConfig` 不含内核运行期 Memory）；内核侧消费产物（`agent apply`）为部署侧机制，不在本层。
- **验证**：单测 `tests/packages/craw/` 29 → 36 例；colima sim 跨容器实跑（agent 写全配置产物到共享卷 → openclaw 侧 `SOUL.md` + `agent-config.json` 落盘、读回一致）。

## 2026-07-14 · Craw 适配层（packages/craw）

- **背景**：AIDEV 插件对接 CLI 形态内核（OpenClaw / Hermes）此前散落在业务插件的 extend 层，各写一套转发与 registry 覆盖。
- **变更**：新增 `aidev_agent/packages/craw/`——统一后端抽象（`OpenClawBackend` / `HermesBackend`）+ `CrawCompletionAgent`（CHAT 转发、SSE→AG-UI）+ `CrawSyncer`（周期 read/write）+ `enable_chat_takeover()`（`BKAI_CRAW_BACKEND` env 门控，未设零影响）；用户身份经 `X-Bkai-Access-Token` 透传（对齐 bkai-cli 池模式契约），日志只落 identity 哈希。`httpx` 转为显式依赖。
- **验证**：单测 `tests/packages/craw/` 29 例（`make test path=tests/packages/craw`）；colima 双容器端到端三变体各两轮 ALL PASS——openclaw 直连（`run.sh`）、hermes gateway api_server（`run-hermes.sh`）、业务插件集成（`run-plugin.sh`，整链 `/chat_completion/` 非流式 + AG-UI 流式；插件侧配套一个 extend 层薄壳触发 `enable_chat_takeover()`）。
- **隔离验证**（`run-isolation.sh`，真实网关环境）：REAL/FAKE 双用户 token 三层闭环——判定面（MCP 网关 initialize 建连即校验，REAL 通过 / FAKE 400）、隔离链（bkai-cli 池模式：identityId 分流独立内核、mcp-probe accessible/rejected、用户 token 不落盘仅 egress 内存注入）、对话行为面（同题问两身份：REAL 列出可用 MCP 工具并实调成功，FAKE 如实报无可用 MCP；与 egress 传输层流水吻合）。SDK `CrawIdentity.identity_id` 与池路由 identityId 同 sha256[:16] 契约实测一致。
- **注**：文档见 [docs/craw-adapter.md](docs/craw-adapter.md)。
