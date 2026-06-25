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
- `ChatInput` 发送按钮图标尺寸由 `input-attachment.vue` 的全局类 `.send-message-icon` 控制，图标走 `.ai-common-icon`（全局 `width/height:1em`），故尺寸由 `font-size` 驱动；该全局类经 `InputAttachment` 作用于所有 `ChatInput` 实例（主输入区 chat-container、用户消息编辑态 user-message、中断/追问卡片 interrupt-message / user-question-card），改一处全量生效

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

## 编码约定（详见 chat-x-dev skill）

- `.ts` 文件顶部带项目 MIT license 头，`.vue` 文件不带；SFC 顺序固定 `template → script setup → style`，import 分组 vue → 三方 → 内部相对 → `import type`
- 样式统一 `&-element` 嵌套（不用 `&__element`），class 一律 `ai-` 前缀 BEM + `&.is-xxx` 状态；字号用 `var(--ai-font-size, 12px)` 必带兜底；语义色 `@use styles/variables.scss`；禁止 `:deep`
- composable 用箭头函数 + `Symbol` token 的 `useXxx`(provide)/`injectXxx`(inject 兜底 undefined)；只放数据逻辑，UI 交互态留组件本地；优先 `shallowRef`/`shallowReactive`
- 类型扩展走 `declare global` 声明合并（`AIBluekingMessageMap`/`AIBluekingContentMap`），不加组件泛型逐层透传；i18n 所有可见文案走 `t('中文')` 并同步 `src/lang/lang.ts`（漏加会类型报错）

## Skills 与文档体系

- 项目已沉淀 5 个 skill：`.agents/skills/chat-x-dev`（库内编码规范）、`skills/blueking-chat-x`（消费方使用导航，注意在 `skills/` 而非 `.agents/skills/`）、`.agents/skills/chat-x-update-docs`（提交前同步 test+wiki）、`.agents/skills/chat-x-tapd-dev`（TAPD 开发闭环）、`.agents/skills/chat-x-figma-dev`（Figma 设计稿出码，复用 chat-x-dev 编码规范不重复）
- 写/审 skill 的硬约束（用户反复纠正）：`description` 只写「何时触发」不写工作流/做什么；线性步骤用编号列表而非流程图（`digraph`）；skill 须自包含、不耦合或对比外部 skill（如 bkmonitor-figma-dev）；reference 里的变量/清单表标注为「快照，以源码为准」
- 组件 API 真相源是 `wikis/` + chat-x MCP（`chat-x-mcp`：`list_components`/`get_component_doc`/`search_docs`，由 `mcp/scripts/build-index.ts` 从 wikis 构建索引）；不要凭记忆臆测 props/events/slots
- `wikis/components/` 已按能力域目录组织（agent/feedback/helper/input/medias/message/rendering/setup），文档带 frontmatter；源码↔文档映射见 `wikis/components/inventory.md`，VitePress 侧边栏在 `wikis/.vitepress/config.mts` 手动维护

## Git 与提交校验

- `.git` 在 monorepo 根 `liang-ai-agent/.git`（workspace 为 `packages/chat-x`），沙箱内 `git commit`/`git push`/`gh pr create` 会报 `index.lock: Operation not permitted`，需 `required_permissions: ["all"]`；`git fetch` 用 `["network"]`
- git remote：origin = 个人 fork `liangling0628/bk-aidev-agent`，upstream = `TencentBlueKing/bk-aidev-agent`；本仓库未启用 GPG 签名，可直接代提交
- commit-msg 走 `@blueking/bkui-lint/verify-commit.mjs`：`type: subject` 的 subject（含 `--story=`/`--bug=` 后缀）须 1–50 字符；任何情况不得用 `--no-verify`
- pre-commit `scripts/pre-commit-test.mjs`：staged 的 `packages/chat-x/src` 改动，若对应 colocated `*.spec.ts` 或 `wikis/components/**` 已存在却未一并 stage 则拦截提交，并自动跑相关 vitest（测试不过无法提交）；slug override `components/image-preview/image.vue → ai-image`
- TAPD 单据 workspace_id 固定 `70093903`（蓝鲸开发工具）；19 位 ID = `10`+workspace_id(8 位)+短 ID(9 位)，分支名用完整 ID、commit/PR title 后缀用短 ID
- TAPD 回写评论：`comments_create` 传 Markdown（`**`/反引号/列表）会在 TAPD 页面渲染为空 `<div></div>`（API `comments_get` 仍能读到正文，UI 看不到）；故 `description` 用纯文本，创建后用 `get_workitem_change_history`（`object_type` 单数 `story`/`bug`/`task`）校验 `value_after`，为空则用 `comments_update` 以纯文本兜底；评论展示在单据「动态」Tab（标题常为系统生成的「在状态 [xxx] 添加」）
- upstream 特性基线分支名是 `feat/human_in_the_loop`（下划线），不是 `feat/human-in-the-loop`（连字符）

## Figma 设计稿开发

- Figma MCP（`user-figma`）默认可能未连接当前工作区，可检查 `~/.cursor/projects/<proj>/mcps/` 是否出现 `user-figma` 目录来判断；未连接时需让用户在 Cursor 启用后再继续
- 读取设计稿规格优先用 `get_design_context`（传 fileKey + nodeId），比 `get_metadata` 更有用（后者只给结构）；首次调用若要求 Code Connect 映射，确认不需要时传 `disableCodeConnect: true` 直接拿设计上下文，避免循环
- Figma 出码组件选型优先级（按控件类型分流）：bkui-vue 同名基础控件（按钮/输入/下拉/表单/开关/tab 等通用控件，优先用）→ chat-x 自有原子对话复合块（消息/工具条/渲染块等，查 `wikis/`/MCP，勿用基础控件硬拼重复造）→ 已装同名 npm 包 → 自研
- Figma 主题/token「先验证再映射」：skill reference 的变量表只是快照，套用前必须回源码（`src/styles/size-theme.scss` / `variables.scss`）确认目标变量/map 真实存在且在用；查无对应变量/主题未启用时，直接用设计稿的具体 hex/px 值并注释来源，不要臆造引用不存在的变量
- chat-x 图标用自有 SVG 体系（`src/icons/*.ts`，`h('svg', commonSVGProps)`，尺寸由 `font-size`(1em) 驱动、色由 `currentColor` 驱动），不使用 bkui-vue 图标；缺失图标按现有模式新增并补 barrel 导出；主题为 size-theme CSS 变量（`[data-ai-size]` small/normal，引用必带兜底）+ `variables.scss` 语义色/map，无暗色模式

## Workflow Preferences

- 实现前先输出架构分析与方案，用户确认后再动手
- 功能落地后同步更新 Skill 文档（项目内 `.cursor/skills/` 与全局 `~/.cursor/skills/`）和 references；主站 VitePress 文档更新遵循 `.agents/skills/ai-blueking-docs-update/`
- 优先维护项目内 `.cursor/skills/`，全局同名 skill 若已软链到项目内则不再双份维护
- playground 包通常不需要改动，除非用户明确要求
- 骨架屏使用全局 `.ai-skeleton-element` class + 各组件本地尺寸类，无独立 Skeleton 组件
