# Playground 实例索引（可运行的权威参考）

> **⚠️ 前提：本页指向源码仓库内的文件，仅在你能访问 `bk-aidev-agent-public` 仓库时有效。**
> 若你**单独使用本 Skill（无仓库）**，无需这些文件——各 reference 文档已把关键示例（HITL 插槽接线、中断数据结构、侧栏自定义契约等）**内联**，可直接照抄：
> - HITL 全套（含 `#message`/`#group`/`#interruptQuestion` 参考实现、中断数据示例）→ [hitl.md](hitl.md)
> - 侧栏自定义 / 自定义 Tab（含 `tab.name` 管道格式、完整示例）→ [integration-patterns.md](integration-patterns.md)
> - 自定义消息渲染（含完整 `CustomMessageRenderer`）→ [custom-message-rendering.md](custom-message-rendering.md)
>
> 本页价值在于：**有仓库时**，几乎每个功能都有可运行真实代码，比文档片段更完整。启动：`pnpm dev:ai`（ai-blueking）/ `pnpm dev:ui`（chat-x）。

## 两套 playground 的定位

| Playground | 路径 | 层级 | 适合参考 |
|------------|------|------|----------|
| **ai-blueking** | `packages/ai-blueking/playground/` | 集成层（`AIBlueking` / `ChatBot`） | 面板集成、独立模式、**嵌入模式业务 Header**、requestOptions、错误处理、standalone-mount、侧栏自定义、`#message` 自定义渲染 |
| **chat-x** | `packages/chat-x/playground/` | 组件层（`ChatContainer` 等原子组件） | HITL 中断/恢复、`#group`/`#interruptQuestion` 插槽、RenderMode/size、自定义内容渲染、自定义 Tab（原子组件自行组装的完整范式） |

---

## 一、ai-blueking playground（集成层）

路由视图（`packages/ai-blueking/playground/views/`），路由表见 `router.ts`：

| 视图文件 | 演示主题 | 对应文档 |
|----------|----------|----------|
| `IntegratedView.vue` | 集成模式（`AIBlueking` 完整面板 + 悬浮球） | [集成模式](integration-patterns.md) |
| `StandaloneView.vue` | 独立模式 / `mountAIBlueking`·`mountChatBot` | [集成模式#非 Vue 宿主挂载](integration-patterns.md) |
| `EmbeddedHeaderView.vue` | **嵌入式 ChatBot 业务 Header**（会话名 + `v-model:asideCollapsed` + `CollapsedAsideIcon`）。标题栏「查看源码」弹窗可复制最小接入代码 | [集成模式#嵌入式业务 Header](integration-patterns.md#嵌入式-chatbot业务-header--侧栏开关)、[ChatBot API](chatbot-api.md#嵌入模式业务-header会话名--侧栏开关) |
| `ExampleBasicView.vue` / `ExampleAdvancedView.vue` | 基础 / 高级用法 | [ChatBot API](chatbot-api.md) |
| `CodeHeaderSlotView.vue` | `#codeHeader` 插槽（代码块「插入/应用」） | [ChatBot API#Slots](chatbot-api.md) |
| `HeaderLeftSlotView.vue` | `#headerLeft` 插槽（Header 左侧自定义） | [SKILL.md](../SKILL.md) |
| `UrlSwitchView.vue` | `url` 动态切换与重初始化（`whenReady` / `ChatBotInitStaleError`） | [ChatBot API#whenReady](chatbot-api.md) |
| `RequestOptionsView.vue` | `requestOptions` 响应式（对象/函数/ref/computed） | [SKILL.md · requestOptions 响应式](../SKILL.md) |
| `RenderModeView.vue` | `renderMode`（chat / share / test） | [SKILL.md · 渲染模式](../SKILL.md) |
| `ErrorHandlingView.vue` | `@error`（独立）vs `@sdk-error`（集成） | [集成模式#错误处理](integration-patterns.md) |
| `CustomMessageSlotView.vue` | `#message` + `custom-component` 自定义渲染 | [自定义消息渲染](custom-message-rendering.md) |
| `SideRenderView.vue` | 执行侧栏自定义渲染 + 自定义 Tab | [集成模式#侧栏自定义](integration-patterns.md) |

### 自定义消息渲染组件（`components/custom-widgets/`）

**文档 [custom-message-rendering.md](custom-message-rendering.md) 中的示例即取自这些真实文件**：

- `CustomMessageRenderer.vue` — 解析 `custom-component` 代码块并按 `data.type` 分发（`parseCustomBlocks`）
- `ChartWidget.vue` / `IframeWidget.vue` / `FormWidget.vue` — 三个示例业务组件

> ⚠️ playground 的 `CustomMessageRenderer.vue` 属基础 demo，**未透传 `onInterruptResume`**（因为它不涉及 HITL）。生产代码若可能收到中断消息（`MessageRole.Interrupt`），须按文档给非 Assistant 分支补上 `:on-interrupt-resume`，否则中断卡片无法交互——参见 [HITL](hitl.md)。

### 侧栏自定义渲染（`components/side-render/`）—— 非 obvious 契约都在这里

- `use-side-render-handlers.ts` — `getSideRenderComponent` / `getSideTabRenderComponent` 的完整实现。**关键细节**：
  - `getSideRenderComponent(h, props)` 的 `props` 携带 `{ task_id, node_id, node_name, task_name, loading, data }`。
  - 自定义 Tab 的 `tab.name` 是**管道分隔**格式 `` `{task_id}|{node_id}|{node_name}` ``（据此判断是否 Flow 节点 Tab / 解析节点名）。
  - `getSideTabRenderComponent(h, tab, { removeCustomTab })` 里用 `removeCustomTab(tab.name)` 关闭 Tab。
- `use-side-render-custom-tab-change.ts` — `onCustomTabChange` 的完整实现。**关键细节**：从 `tab.data?.props` 读 `task_id` / `node_id`；默认端点 `flow_agent/{taskId}/task_node_info/{nodeId}/`；返回值（节点详情对象）会渲染进侧栏内容区。演示了「内置拉取（builtin）」与「业务自拉取（custom）」两种 `detailSource`。
- `CustomTabContent.vue` / `FlowAgentSideRenderDemo.vue` — 侧栏内容 UI 与 Flow 节点 demo。
- `SideRenderLiveDemo.vue` / `SideRenderCodeSection.vue` / `side-render-scenarios.ts` / `side-render-code-examples.ts` — demo 脚手架与场景数据。

---

## 二、chat-x playground（组件层）——含 HITL 权威范例

原子组件自行组装的完整范式，也是**唯一有 HITL 可运行示例**的地方（`packages/chat-x/playground/`）：

| 文件 | 演示主题 |
|------|----------|
| **`chat-bot-new.vue`**（~1400 行） | **最全的组件层范例**：`ChatContainer` 全量 props/事件、`v-model:render-mode`、`:size`、`:on-interrupt-resume`、`:on-custom-tab-change`；并在**注释中给出 `#group` / `#message` / `#interruptQuestion` 三个插槽的参考实现**（含 `InterruptMessageRender`、`UserQuestionChoice` 用法）——写自定义插槽时直接照这里抄 |
| **`interrupt.ts`**（~330 行） | **HITL 数据模型的权威样例**：`createApprovalInterrupt`（`AIDevToolApprovalInterrupt` + `metadata.ticket`）、用户提问中断、`InterruptMessage.content`（`outcome` / `result`）的真实构造，对齐 `APPROVAL_STATUS` / `InterruptReason` 等枚举 |
| `mock.ts` | 流式 + 中断的 mock 数据源 |
| `custom-content.vue` | chat-x 层自定义**内容**渲染（`ContentRender` 的 `default` 插槽扩展点） |
| `custom-tab-content.vue` | 自定义 Tab 内容 |
| `custom-message/custom-message.vue` | 自定义消息渲染（组件层） |
| `custom-message/stock.ts` · `stock-echarts.ts` · `tree-map.ts` | **更真实的自定义组件示例**：股票卡片、ECharts、树图——比文档里的最小 ChartWidget 更接近生产 |
| `chat-new.vue` | `ChatContainer` 另一组装示例 |
| `image-play/` · `upload-file.ts` · `markdown*.ts` | 图片预览、上传、Markdown 渲染测试 |

### HITL 参考路径拆解

- **UI 如何接线**（插槽/props/中断消息渲染）→ `chat-bot-new.vue`（注释里的 `#message` / `#group` / `#interruptQuestion`）+ `interrupt.ts`（中断数据形状）。
- **恢复如何落到后端**（`OnInterruptResume` → SDK 原语）→ 生产实现在 ai-blueking 的 `packages/ai-blueking/src/components/composables/use-interrupt-resume.ts`（playground 的 `handleInterruptResume` 仅 `console.log`，是 demo）。
- 完整协议与集成三层写法见 [HITL 人机协同](hitl.md)。

---

## 使用建议

1. **先查本索引定位真实文件**，再回到对应 reference 文档看结构化说明——文档讲「为什么/契约」，playground 给「照着写」。
2. HITL / 侧栏自定义 / 自定义 Tab 这类**插槽作用域 + 回调契约**极易写错，务必对照 `chat-bot-new.vue` 与 `use-side-render-handlers.ts` 的真实签名。
3. 目前 **ai-blueking playground 无 HITL demo**；HITL 的可运行示例集中在 chat-x playground。
