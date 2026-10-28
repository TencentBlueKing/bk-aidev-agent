# 文档同步任务

## 已完成

- [x] `git pull upstream develop --rebase` 到 `8dbee550`（`@blueking/*` `3.1.0-beta.5`）
- [x] 冲突按 3.1 源码合并：保留 `enableMessageCollapse`，`executionTabVisible` 仍视为无效
- [x] 文档站依赖改为已发布的 `3.1.0-beta.5`，changelog 首条版本为 `v3.1.0-beta.5`
- [x] 侧栏示例去掉失效的 `execution-tab-visible`，改为 `enable-message-collapse`；默认 Tab 按「文件产物」描述
- [x] 去掉「示例仍是 2.4.x」的说法。仍成立的限制（`show` 的 `isTemporary`、`updatePosition`、`context` 函数形态、`@sdk-error.code === -1`、已发布包的 `#message` 作用域）改标为当前行为

## 后续待处理

- [ ] `#message` 插槽补齐 `MessageSlotProps` / `renderDefault` 的改动在本分支源码里，尚未打进 `3.1.0-beta.5`。文档站示例跑的是已发布包，自定义消息页仍按窄作用域说明。发版后再改 `custom-message.md` 和指南里的 warning。
- [ ] `executionTabVisible` 仍留在 `ChatBot` / `AIBlueking` 类型和透传上，`ChatContainer` 不读取。是否从组件删掉，另行决定。
