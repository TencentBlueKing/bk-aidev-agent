# Learned Patterns

## Architecture & Layering

- HTTP 层方法须在业务层 `use-message.ts` 中透传/封装后，组件才能通过 `chatHelper.message` 调用；不要直接使用 `chatHelper.http`（类型为 `unknown`）
- 过滤/转换职责集中在 `chat-helper` SDK 层；业务层（如 `ShareBusinessManager`）和组件层不要重复相同的 `role === user` 过滤逻辑
- 布局细节（侧板展开收起、视口 clamp、nextTick）下沉到 `use-draggable`，`ComponentManager` 做薄代理，避免布局状态散落在 manager
- `ChatContainer` 的 `onCustomTabChange` 在应用层（`chat-bot.vue`）拉取接口数据并 return 回 tab；flow-agent 节点详情走此链路
- `isCollapse` 变化需统一 emit `collapseChange`，不能只在手动折叠按钮处 emit；否则 `addCustomTab` 展开时外层 draggable 无法配合
- `AIBlueking`/`ChatBot` 已支持 `codeHeader` 插槽透传，插槽参数为 `{ language, token }`；链路为 `AIBlueking -> ChatBot -> ChatContainer#message -> MessageRender#codeHeader`，用于代码块头部自定义动作（如插入/应用）
- `requestOptions.data` 对 POST/PUT/PATCH/DELETE 合并进 body；对 GET/HEAD/OPTIONS 合并进 query（params）
- `supportUpload` 需从 `ChatContainer -> MessageContainer -> MessageRender -> UserMessage` 全链路透传；否则用户消息编辑态 `ChatInput` 会回退到默认 `true` 与主输入区配置不一致
- 自定义 `ChatContainer` 的 `#message` 插槽渲染 `MessageRender` 时，必须透传 `on-action`、`on-input-confirm`、`on-shortcut-confirm`、`tippy-options`；否则用户消息的工具操作（删除/编辑/复制/引用）全部失效，而 AI 消息的工具操作不受影响（AI 的 `MessageTools` 在 `MessageContainer` 内部渲染，不经过 `#message` 插槽）

## Selection & Share Flow

- 分享选择模式的 UI 交互（SelectionFooter、全选/取消全选、Checkbox 渲染）已内聚在 `ChatContainer`（chat-x）中，由 `useMessageGroup` 管理 `isShareMode` / `selectedUserMessages`
- 外部触发进入分享模式使用 `ChatContainer` 的 expose 方法：`chatContainerRef.enterShareMode()` / `exitShareMode()`；ChatBot 也暴露了同名方法委托给 ChatContainer
- `ChatContainer` 内部拦截 `tool.id === 'share'`（来自 MessageTools），不透传给父组件的 `onAgentAction`；确认分享时 emit `confirmShare` 携带选中消息
- `useShareSelection` composable 仅保留「确认分享」的业务逻辑（独立模式下调 `ShareBusinessManager` + 复制链接），不再管理选择 UI 状态
- `useToolActions` 不再包含 share 分支和 `internalEnableSelection`
- 新会话和历史会话切换时都须退出 selection mode，不只是 `handleNewChat`
- pause 消息（`property.extra.pause`）在 UI 上可被选中，但 `hasSessionContents` 不能仅凭 `list.length > 0`，需区分「仅 pause」与「有真实会话」

## TypeScript Patterns

- 避免 `IShortcut & Shortcut` 整块交叉类型，当两个接口同名字段类型冲突（如 `fillRegx: RegExp` vs `string`、`components` 结构差异）时会产生 `never`；改用 `Shortcut & Pick<IShortcut, 'supportUpload'>` 只扩展所需字段

## Workflow Preferences

- 实现前先输出架构分析与方案，用户确认后再动手
- 功能落地后同步更新 Skill 文档（项目内 `.cursor/skills/` 与全局 `~/.cursor/skills/`）和 references；主站 VitePress 文档更新遵循 `.agents/skills/ai-blueking-docs-update/`
- 优先维护项目内 `.cursor/skills/`，全局同名 skill 若已软链到项目内则不再双份维护
- playground 包通常不需要改动，除非用户明确要求
- 骨架屏使用全局 `.ai-skeleton-element` class + 各组件本地尺寸类，无独立 Skeleton 组件
