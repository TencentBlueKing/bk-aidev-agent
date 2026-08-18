# ChatBot 组件 API

> 适用版本：`@blueking/ai-blueking` `2.2.2`（含 HITL 中断/恢复、renderMode、模型选择、侧栏自定义渲染、standalone-mount、文件产物预览等能力）。

## Props

| 属性            | 类型                 | 默认值  | 说明                                           |
| --------------- | -------------------- | ------- | ---------------------------------------------- |
| url             | `string`             | `''`    | API 地址（独立模式必填）                       |
| chatHelper      | `IChatHelper`        | -       | 外部 chatHelper（集成模式传入，与 url 二选一） |
| autoLoad        | `boolean`            | `true`  | 是否自动加载最近会话                           |
| alwaysCreateNewSession | `boolean`     | `false` | 是否始终创建新会话（初始化时不判断最近会话是否有内容，直接新建） |
| sessionCode     | `string`             | -       | 指定初始会话编码                               |
| shortcuts       | `Shortcut[]`         | `[]`    | 快捷指令列表                                   |
| shortcutLimit   | `number`             | `10`    | 快捷指令显示上限                               |
| resources       | `IAiSlashMenuItem[]` | `[]`    | 资源列表（@ 触发）                             |
| skills          | `ISkillListItem[]`   | -       | 技能列表（/ 触发）                             |
| prompts         | `string[]`           | -       | 预设提示词                                     |
| helloText       | `string`             | -       | 欢迎语                                         |
| useAgentName    | `boolean`            | `false` | 使用 agentName 作为欢迎标题                     |
| placeholder     | `string`             | -       | 输入框占位符                                   |
| renderMode      | `RenderMode`         | `chat`  | 渲染模式：`chat`(默认) / `share`(分享只读) / `test`（详见「渲染模式 renderMode」） |
| enableSelection | `boolean`            | `false` | 是否启用多选模式（分享用；新代码推荐用 `renderMode="share"`） |
| shareLoading    | `boolean`            | `false` | 分享加载状态                                   |
| enableModelSelect | `boolean`          | `true`  | 是否启用模型选择（≥ v2.2.2）；拉取 `GET llms/`，列表非空才展示 |
| models          | `ILlmItem[] \| IModelOption[]` | - | 外部模型列表（≥ v2.2.2）；有值时跳过内部拉取 |
| modelSelectionManager | `ModelSelectionManager` | - | 集成模式注入共享实例（AIBlueking → ChatBot）；独立模式内部自建 |
| errorToast      | `boolean`            | `true`  | 接口/业务错误时是否自动弹 Message（展示 `error.message`）；设为 `false` 可自行通过 `@error` 处理。AIBlueking 内嵌时会传 `false` 以免与父层双弹 |
| height          | `string \| number`   | -       | 容器高度                                       |
| maxWidth        | `string \| number`   | -       | 最大宽度                                       |
| extCls          | `string`             | -       | 额外 CSS 类名                                  |
| requestOptions  | `MaybeRefOrGetter<IRequestOptions>` | - | 请求配置（仅独立模式；headers/data 支持对象、函数、ref、computed） |
| messageToolsTippyOptions | `MessageToolsTippyOptions` | - | MessageTools tippy 弹窗配置（如 `appendTo`，控制弹窗挂载位置和层级） |
| messageTools | `IToolBtn[]` | - | 自定义 AI 消息主工具组（copy/cite/rebuild/share）；按 id 与内置合并（覆盖/追加/`hidden: true` 隐藏） |
| updateTools | `IToolBtn[]` | - | 自定义 AI 消息反馈工具组（like/unlike/delete）；合并规则同上 |
| asideCollapsed | `boolean` | 内部默认折叠 | 侧栏折叠态。传入后**严格受控**（内部展开只发 `update:asideCollapsed`）；不传时由 ChatBot 内部自持。侧栏固定从右侧展开，已移除 `placement`。**嵌入模式须业务 Header 提供开关**，见下节 |
| resizeProps     | `ResizeProps`        | -       | ResizeLayout 配置（执行情况侧面板拖拽）        |
| size            | `AiSizeMode`（`'normal' \| 'small'`） | `'small'` | 字号主题档位，透传至 ChatContainer（`small` 12px / `normal` 14px） |
| executionTabVisible | `boolean` | `true` | 「执行情况」Tab 是否展示（与 ChatContainer 一致）；置 `false` 时从 Tab 栏隐藏 |
| getSideRenderComponent | `GetSideRenderComponent` | - | 自定义侧栏内容区渲染（详见 [side render / custom tabs](integration-patterns.md#侧栏自定义渲染与自定义-tab-side-render--custom-tabs)） |
| getSideTabRenderComponent | `GetSideTabRenderComponent` | - | 自定义侧栏 Tab 标签渲染 |
| onCustomTabChange | `OnCustomTabChange` | -       | 覆盖默认 Flow 节点详情拉取；未传则回退到 `chatHelper.message.getFlowAgentTaskNodeInfo` |

## Events

| 事件              | 参数                                       | 说明                           |
| ----------------- | ------------------------------------------ | ------------------------------ |
| send-message      | `(message: string)`                        | 用户发送消息                   |
| receive-start     | -                                          | 流式响应开始（仅独立模式）     |
| receive-text      | -                                          | 流式接收文本（仅独立模式）     |
| receive-end       | -                                          | 流式响应结束（仅独立模式）     |
| stop              | -                                          | 用户停止生成                   |
| error             | `(error: Error)`                           | 发生错误（仅独立模式）；参数保证是 `Error` 实例，同一个错误实例只触发一次；默认同时弹 Message（`errorToast`，文案为 `error.message`） |

> **注意**：AIBlueking 集成模式下，ChatBot 的 `@error` 不会被透传给业务方，所有错误统一通过 AIBlueking 的 `@sdk-error` 事件暴露。详见 [集成模式 - 错误处理](integration-patterns.md#错误处理模式)。
| session-switched  | `(session: ISession \| null)`              | 会话切换完成                   |
| shortcut-click    | `({ shortcut, source })`                   | 快捷指令点击                   |
| agent-info-loaded | `(chatHelper: IChatHelper)`                | 独立模式初始化完成（与 `whenReady` 成功时机一致） |
| feedback          | `(tool, message, reasonList, otherReason)` | 反馈提交成功                   |
| confirm-share     | `(messages: Message[], source?: IToolBtn)` | 确认分享/多选；`source` 为触发按钮。仅 `!source \|\| source.id === 'share'` 走内置 ShareBusinessManager |
| cancel-share      | -                                          | 取消分享                       |
| request-share     | -                                          | 请求进入分享模式               |
| agent-action      | `(tool: IToolBtn, messages: Message[])`    | 自定义消息工具点击（非内置 cite/rebuild/delete/like/unlike） |
| execution-panel-change | `(isCollapse: boolean, resizeAsideWidth?: number)` | 侧栏展开/折叠与宽度变化（浮窗几何不由此事件驱动） |
| update:asideCollapsed | `(collapsed: boolean)` | `v-model:asideCollapsed`；受控时内部展开只发此事件 |
| rename            | `(newName: string, sessionCode: string)`   | 首条消息后 AI 自动重命名成功；第二参为被改名会话编码（切会话后仍会抛，便于业务维护列表） |

## 嵌入模式业务 Header（会话名 + 侧栏开关）

`ChatBot` 只有聊天区，**不带** `AIHeader`。浮窗场景的展开/收起在 `AIBlueking` → `AIHeader`；嵌入到页面时必须业务方自建 Header。

| 职责 | 谁做 | 说明 |
| --- | --- | --- |
| 会话名称 | 业务 Header 左侧 | 从 `@agent-info-loaded` 拿到 `chatHelper` 后读 `session.current.sessionName` |
| 展开 / 收起侧栏 | 业务 Header 右侧 | `v-model:asideCollapsed`；图标用 `CollapsedAsideIcon`（chat-x 导出的 VNode，模板里 `cloneVNode`） |
| 侧栏内容 | ChatBot / ChatContainer | 固定从右侧展开；文件卡片、`addCustomTab` 只会 emit `update:asideCollapsed` |

```vue
<template>
  <div class="chat-main">
    <header class="chat-main-header">
      <h1>{{ currentSessionName }}</h1>
      <span :title="asideCollapsed ? '展开侧栏' : '收起侧栏'" @click="asideCollapsed = !asideCollapsed">
        <AsideToggleIcon />
      </span>
    </header>
    <ChatBot
      v-model:aside-collapsed="asideCollapsed"
      :url="apiUrl"
      height="100%"
      @agent-info-loaded="handleAgentInfoLoaded"
    />
  </div>
</template>
```

> 可运行样例：`packages/ai-blueking/playground/views/EmbeddedHeaderView.vue`。生产级（会话列表 + 搜索/批量删除）：`publish-template/src/views/ChatWindow.vue`。完整接线见 [集成模式](integration-patterns.md#嵌入式-chatbot业务-header--侧栏开关)。

## Slots

| 插槽名     | 参数                                     | 说明                                                  |
| ---------- | ---------------------------------------- | ----------------------------------------------------- |
| welcome    | `({ openingRemark?, welcomeTitle? })`    | 自定义空会话欢迎区（透传 ChatContainer `#welcome`）   |
| codeHeader | `({ language: string, token: Token[] })` | 自定义 markdown 代码块头部区域，常用于插入/应用等动作 |
| message    | `({ message, messageToolsStatus, onInterruptResume })` | 自定义单条消息渲染（覆盖默认 `MessageRender`）。作用域含**第三个** prop `onInterruptResume`（类型 `OnInterruptResume`，来自 chat-x） |

```vue
<ChatBot url="/api/ai">
  <template #welcome="{ welcomeTitle, openingRemark }">
    <h2>{{ welcomeTitle }}</h2>
    <p>{{ openingRemark }}</p>
  </template>
  <template #codeHeader="{ language, token }">
    <span @click="handleCodeInsert(language, token)">插入</span>
    <span @click="handleCodeApply(language, token)">应用</span>
  </template>
</ChatBot>
```

### 消息工具栏扩展（`messageTools` / `updateTools`）

透传 chat-x `ChatContainer` 合并扩展能力。合并规则：同 `id` 字段级覆盖、新 `id` 追加、`{ id, hidden: true }` 隐藏内置项。

- `triggerSelection: true`：点击进入多选，确认走 `confirm-share(messages, source)`（**不**进 `onAgentAction`）
- 其它自定义按钮：走 `agent-action`
- 仅 builtin share（`!source || source.id === 'share'`）执行内置分享；自定义 source 只向外 emit

```vue
<ChatBot
  :message-tools="[
    { id: 'save', name: '保存', icon: DownloadIcon, triggerSelection: true },
    { id: 'share', hidden: true },
  ]"
  :update-tools="[{ id: 'collect', name: '收藏' }]"
  @confirm-share="(msgs, source) => { /* source?.id === 'save' */ }"
  @agent-action="(tool, msgs) => { /* tool.id === 'collect' */ }"
/>
```

> **⚠️ `#message` 插槽与 HITL（关键）**：`#message` 作用域现在提供**三个** prop —— `message`、`messageToolsStatus`、以及新增的 `onInterruptResume`（`OnInterruptResume`）。任何自定义 `#message` 实现**必须**把 `:on-interrupt-resume="onInterruptResume"` 透传给内部的 `MessageRender`（或等价渲染），否则 HITL 的工具审批（tool-approval）、用户追问（user-question）、Flow 节点重试/跳过（flow-node retry-skip）等中断恢复动作将失效。完整中断/恢复机制见 [`hitl.md`](hitl.md)。
>
> ```vue
> <ChatBot :url="apiUrl">
>   <template #message="{ message, messageToolsStatus, onInterruptResume }">
>     <MessageRender
>       :message="message"
>       :message-tools-status="messageToolsStatus"
>       :on-interrupt-resume="onInterruptResume"
>     />
>   </template>
> </ChatBot>
> ```

## Expose 方法

| 方法/属性      | 类型                                     | 说明                     |
| -------------- | ---------------------------------------- | ------------------------ |
| sendMessage    | `(message: string) => void`              | 发送消息                 |
| stopGeneration | `() => void`                             | 停止生成                 |
| switchSession  | `(sessionCode: string) => Promise<void>` | 切换会话                 |
| setCiteText    | `(text: string) => void`                 | 设置引用文本             |
| focusInput     | `() => void`                             | 聚焦输入框               |
| selectShortcut | `(shortcut, text?) => void`              | 选择快捷指令并显示表单   |
| sendShortcut   | `(shortcut, text?) => Promise<void>`     | 直接发送快捷指令（跳过表单） |
| getChatHelper  | `() => IChatHelper \| null`              | 获取内部 chatHelper 实例 |
| updateAgentInfo | `() => Promise<IAgentInfo \| null>`     | 主动刷新 agentInfo 并更新内部状态（含 shortcuts）；失败返回 `null` |
| enterShareMode | `() => void`                             | 进入分享选择模式（委托给 ChatContainer） |
| exitShareMode  | `() => void`                             | 退出分享选择模式（委托给 ChatContainer） |
| messages       | `ComputedRef<Message[]>`                 | 当前消息列表             |
| currentSession | `ComputedRef<ISession \| null>`          | 当前会话                 |
| isGenerating   | `ComputedRef<boolean>`                   | 是否正在生成             |
| isReady        | `ComputedRef<boolean>`                   | 是否已完成初始化（独立模式含 sessionList） |
| whenReady      | `() => Promise<void>`                    | 等待初始化完成，语义对齐 AIBlueking `ensureSessionReady` |

## ResizeProps 类型

```typescript
interface ResizeProps {
  /** 是否禁用拖拽调整 */
  disabled?: boolean;
  /** 初始分割位置（px） */
  initialDivide?: number;
  /** 最大宽度（px） */
  max?: number;
  /** 最小宽度（px） */
  min?: number;
}
```

> `resizeProps` 透传至 `ChatContainer` 内的 `ResizeLayout`，控制执行情况侧面板的拖拽行为。

## 两种模式的区别

| 维度            | 独立模式                                                      | 集成模式                                              |
| --------------- | ------------------------------------------------------------- | ----------------------------------------------------- |
| 入口            | `<ChatBot url="..." />`                                       | `<AIBlueking>` 内部使用                               |
| chatHelper      | ChatBot 内部创建                                              | 父组件通过 `useChatBootstrap` 创建并传入              |
| 初始化          | `onMounted` 中自行 getAgentInfo → getSessions → chooseSession | 父组件完成，ChatBot 跳过                              |
| receive-\* 事件 | ChatBot 自身 emit                                             | 由父组件 `useChatBootstrap` 的 protocolCallbacks 处理 |
| 判断方式        | `props.chatHelper` 不存在                                     | `props.chatHelper` 存在                               |

### 独立模式初始化流程

```
ChatBot.onMounted()
├── runAgentBootstrap(chatHelper, { enableModelSelect })
│   ├── getAgentInfo() + getSessions()
│   └── getLlms()（enableModelSelect 且无外部 models 时；失败不阻断）
├── ModelSelectionManager.ensureLoaded（外部 models 优先；集成模式复用 AIBlueking 共享实例）
├── loadRecentSession / chooseSession（createSession 经 resolveModelForSession 写入合法 model）
└── emit('agent-info-loaded', chatHelper)
```

模型选中语义见主 SKILL「模型选择」小节：跟随 session；切换写回 `persistSessionModel`；所有新建会话路径统一解析 model；空列表阻断并上报；附件按钮跟随模型 `support_vision`。

### 嵌入页等待就绪（whenReady）

独立嵌入时无 `show()`，可在 `onMounted` 中 `await chatBotRef.whenReady()` 后再切换会话或发消息：

```vue
<ChatBot ref="chatBotRef" :url="apiUrl" />

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { ChatBot, type ChatBotExpose } from '@blueking/ai-blueking';

const chatBotRef = ref<ChatBotExpose>();

onMounted(async () => {
  await chatBotRef.value?.whenReady();
  // sessionList 已加载，可安全 switchSession / sendMessage
});
</script>
```

- `isReady`：响应式判断是否就绪
- `url` 变更导致重初始化时，进行中的 `whenReady()` 会以 `ChatBotInitStaleError` reject，需重新 `await whenReady()`
- AIBlueking 集成模式：`whenReady` 立即 resolve，请使用 `AIBlueking.show()` 等待会话就绪

## AIHeader 事件（AIBlueking 集成模式）

AIHeader 是 AIBlueking 的 Header 区域组件，其事件会透传至 AIBlueking 层暴露给业务方。ChatBot 独立模式不涉及 AIHeader。

| 事件 | 参数 | 说明 |
|------|------|------|
| `new-chat` | 无 | 用户点击新增会话按钮 |
| `new-chat-created` | `(session: { sessionCode: string; sessionName?: string; createdAt?: string })` | 新会话创建成功，携带 `sessionCode`、`sessionName`、`createdAt`（仅 V2 有 `sessionBusinessManager` 时触发） |
| `history-click` | `(event: Event)` | 用户点击历史会话按钮（V1 模式） |
| `history-session-switch` | `(sessionCode: string)` | 历史面板中切换会话（V2 模式） |
| `history-session-delete` | `(sessionCode: string)` | 历史面板中删除会话（V2 模式） |
| `history-session-rename` | `(sessionCode: string, newName: string)` | 历史面板中重命名会话（V2 模式） |
| `auto-generate-name` | 无 | 自动生成会话名称 |
| `rename` | `(newName: string, sessionCode: string)` | 会话重命名（手动改名，或首条消息后 AI 自动重命名成功）；`sessionCode` 标识被改名会话，切会话后仍会抛出；旧监听只取第一参兼容 |
| `help-click` | 无 | 点击转人工按钮 |
| `share` | 无 | 点击分享按钮 |
| `toggle-compression` | 无 | 切换面板压缩/展开 |
| `close` | 无 | 点击关闭按钮 |

> 完整的 AIBlueking 事件监听示例见 [集成模式与示例](integration-patterns.md#aiblueking-会话相关事件)。

---

## AIBlueking 组件 API

AIBlueking 是完整面板组件（Nimbus 悬浮球 + 浮窗 + 拖拽 + Header + ChatBot）。ChatBot 的 props（`renderMode`、`getSideRenderComponent` 等）大多会透传到内部 ChatBot。

### AIBlueking Props

| 属性 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| url | `string` | `''` | API 服务地址 |
| title | `string` | `''` | 组件标题 |
| helloText | `string` | `你好，我是小鲸` | 欢迎语 |
| useAgentName | `boolean` | `false` | 使用 agentName 作为欢迎标题 |
| placeholder | `string` | - | 输入框占位文本 |
| renderMode | `RenderMode` | `chat` | 渲染模式：`chat` / `share`（只读）/ `test` |
| requestOptions | `MaybeRefOrGetter<IRequestOptions>` | `{}` | 请求配置（支持 ref/computed，替换后后续请求自动生效） |
| shortcuts | `IShortcut[]` | `[]` | 快捷操作列表 |
| shortcutLimit | `number` | `3` | 快捷操作显示数量限制 |
| shortcutFilter | `(shortcut, selectedText) => boolean` | - | 快捷操作过滤函数 |
| prompts | `string[]` | `[]` | 预设提示词列表 |
| resources | `IAiSlashMenuItem[]` | - | 资源列表（@ 触发） |
| messageTools | `IToolBtn[]` | - | 自定义 AI 消息主工具组（透传 ChatBot） |
| updateTools | `IToolBtn[]` | - | 自定义 AI 消息反馈工具组（透传 ChatBot） |
| dropdownMenuConfig | `DropdownMenuConfig` | `{ showRename, showAutoGenerate, showShare }` 均 `true` | Header 更多菜单开关 `{ showAutoGenerate?, showRename?, showShare? }` |
| errorToast | `boolean` | `true` | 接口错误时是否自动弹 Message 提示；设为 `false` 可自行通过 `@sdk-error` 处理（统一错误出口） |
| ignoreErrors | `Array<RegExp \| string>` | - | 忽略的接口错误 URL 模式（包含匹配或正则），匹配的错误不弹 toast |
| executionTabVisible | `boolean` | `true` | 「执行情况」Tab 是否展示（透传 ChatBot，与 ChatContainer 一致）；置 `false` 时从 Tab 栏隐藏 |
| getSideRenderComponent | `GetSideRenderComponent` | - | 自定义侧栏内容区渲染（透传 ChatBot） |
| getSideTabRenderComponent | `GetSideTabRenderComponent` | - | 自定义侧栏 Tab 标签渲染（透传 ChatBot） |
| onCustomTabChange | `OnCustomTabChange` | - | 覆盖默认 Flow 节点详情拉取（透传 ChatBot） |
| resizeProps | `ResizeProps` | - | 执行情况侧面板拖拽配置 |
| size | `AiSizeMode`（`'normal' \| 'small'`） | `'small'` | 字号主题档位，透传至 ChatBot → ChatContainer（`small` 12px / `normal` 14px） |
| beforeNimbusClick | `() => boolean \| Promise<boolean \| void> \| void` | - | Nimbus 点击前钩子，返回 `false` 阻止默认 showPanel（见 [beforeNimbusClick](integration-patterns.md#nimbus-点击自定义beforenimbusclick)） |
| **会话** |||
| enableChatSession | `boolean` | `true` | 是否启用会话管理 |
| initialSessionCode | `string` | `''` | 初始会话编码 |
| autoSwitchToInitialSession | `boolean` | `false` | 是否自动切换到初始会话 |
| alwaysCreateNewSession | `boolean` | `false` | 是否始终创建新会话（初始化时不判断最近会话是否有内容） |
| loadRecentSessionOnMount | `boolean` | `true` | 挂载时是否加载最近会话 |
| **功能开关** |||
| enablePopup | `boolean` | `true` | 是否启用选中文本弹窗（划词） |
| enableModelSelect | `boolean` | `true` | 是否启用模型选择（≥ v2.2.2）；bootstrap 拉取 `GET llms/` |
| models | `ILlmItem[] \| IModelOption[]` | - | 外部模型列表（≥ v2.2.2）；有值时跳过内部拉取 |
| disabledInput | `boolean` | `false` | 是否禁用输入 |
| hideHeader | `boolean` | `false` | 是否隐藏头部 |
| hideNimbus | `boolean` | `false` | 是否隐藏悬浮球 |
| hideDefaultTrigger | `boolean` | `false` | 是否隐藏默认触发器 |
| showCompressionIcon | `boolean` | `true` | 是否显示压缩图标 |
| showHistoryIcon | `boolean` | `true` | 是否显示历史记录图标 |
| showMoreIcon | `boolean` | `true` | 是否显示更多图标 |
| showNewChatIcon | `boolean` | `true` | 是否显示新建会话图标 |
| **Nimbus / 容器** |||
| nimbusSize | `'large' \| 'normal' \| 'small'` | `normal` | 悬浮球大小 |
| draggable | `boolean` | `true` | 是否可拖拽 |
| defaultMinimize | `boolean` | `false` | 是否默认最小化 |
| miniPadding | `number` | `0` | 最小化时的内边距 |
| defaultWidth | `number` | `400` | 默认宽度 |
| defaultHeight | `number` | - | 默认高度 |
| defaultLeft | `number` | - | 默认左侧位置 |
| defaultTop | `number` | `0` | 默认顶部位置 |
| maxWidth | `number \| string` | `1000` | 最大宽度 |
| defaultChatInputPosition | `'bottom' \| undefined` | - | 默认聊天输入框位置 |
| teleportTo | `string` | `body` | 传送门目标 |
| extCls | `string` | `''` | 自定义 CSS 类名 |

### AIBlueking Slots

| 插槽名 | 参数 | 说明 |
|--------|------|------|
| welcome | `({ openingRemark?, welcomeTitle? })` | 自定义空会话欢迎区（透传 ChatBot → ChatContainer） |
| codeHeader | `({ language, token })` | 自定义代码块头部（透传 ChatBot） |
| headerLeft | 无 | Header 标题区与右侧工具栏之间插入自定义内容（透传 AIHeader，详见 [`#headerLeft`](integration-patterns.md#自定义-header-左侧-headerleft-插槽)） |
| message | `({ message, messageToolsStatus, onInterruptResume })` | 自定义单条消息渲染（透传 ChatBot；同样须透传 `onInterruptResume`，见上文 HITL 说明） |

### AIBlueking Expose

| 方法/属性 | 类型 | 说明 |
|-----------|------|------|
| show | `(sessionCode?: string, options?: { isTemporary?: boolean }) => Promise<void>` | 显示面板，可选指定会话；`isTemporary` 创建临时会话 |
| handleShow | `(sessionCode?: string) => Promise<void>` | 显示面板（等同用户操作路径） |
| hide | `() => void` | 隐藏面板 |
| handleClose | `() => void` | 关闭面板（等同用户点击关闭按钮） |
| sendMessage | `(message: string) => Promise<void>` | 发送消息 |
| stopGeneration | `() => void` | 停止生成 |
| selectShortcut | `(shortcut, text?) => void` | 选择快捷指令并显示表单 |
| sendShortcut | `(shortcut, text?) => Promise<void>` | 直接发送快捷指令（跳过表单） |
| getChatHelper | `() => IChatHelper \| null` | 获取 chatHelper 实例 |
| updateAgentInfo | `() => Promise<IAgentInfo \| null>` | 主动刷新 agentInfo 并更新内部状态（含 shortcuts） |
| addNewSession | `(options?: CreateSessionOptions) => Promise<void>` | 创建新会话 |
| switchToSession | `(sessionCode: string) => Promise<void>` | 切换会话 |
| updateSessionName | `(sessionCode, newName) => Promise<void>` | 更新会话名 |
| setCiteText | `(text: string) => void` | 设置引用文本 |
| focusInput | `() => void` | 聚焦输入框 |
| updatePosition | `(x, y) => void` | 更新位置 |
| updateSize | `(w, h) => void` | 更新尺寸 |
| updatePositionAndSize | `(x, y, w, h) => void` | 更新位置和尺寸 |

### AIBlueking Emits

| 事件 | 参数 | 说明 |
|------|------|------|
| show | 无 | 面板显示 |
| close | 无 | 面板关闭 |
| send-message | `(message: string)` | 用户发送消息 |
| receive-start / receive-text / receive-end | 无 | 流式响应开始 / 接收 / 结束 |
| stop | 无 | 停止生成 |
| dragging / resizing / drag-stop / resize-stop | `(position: PositionAndSize)` | 拖拽 / 缩放 |
| shortcut-click | `({ shortcut, source: 'main' \| 'popup' })` | 快捷指令点击 |
| session-initialized | `({ openingRemark: string, predefinedQuestions: string[] })` | 会话初始化完成 |
| sdk-error | `(payload: SdkErrorPayload)` | 统一错误出口（见下文） |
| transfer-messages | `({ messageIds: string[] })` | 消息转移选择 |
| share-messages | `({ messageIds: string[] })` | 消息分享选择 |
| confirm-share | `(messages: Message[], source?: IToolBtn)` | 确认分享/多选；自定义 `source` 不走内置分享 |
| agent-action | `(tool: IToolBtn, messages: Message[])` | 自定义消息工具点击 |
| new-chat | 无 | 点击新增会话按钮 |
| new-chat-created | `(session: { sessionCode, sessionName?, createdAt? })` | 新会话创建成功 |
| history-click | `(event: Event)` | 点击历史会话按钮 |
| auto-generate-name | 无 | 自动生成会话名 |
| rename | `(newName: string, sessionCode: string)` | 会话重命名（手动改名，或首条消息后 AI 自动重命名成功） |
| help-click | 无 | 点击转人工按钮 |
| share | 无 | 点击分享按钮 |

### SdkErrorPayload 类型

```typescript
type SdkErrorApiName = 'chat' | 'getAgentInfo' | 'init' | 'session' | 'share';
type SdkErrorSource = 'business' | 'http' | 'protocol';

interface SdkErrorPayload {
  apiName: SdkErrorApiName;   // 业务语义 apiName（非 HTTP 接口名）
  code: number;
  message: string;
  data: unknown;              // 原始错误对象
  action?: string;            // 可选，错误发生的动作
  source?: SdkErrorSource;    // 可选，错误来源
}
```

> `apiName` 已扩展为 `'chat' | 'getAgentInfo' | 'init' | 'session' | 'share'`（早期版本仅有 `init` / `chat`），并新增可选的 `action?` 与 `source?`（`'business' | 'http' | 'protocol'`）。错误处理示例见 [错误处理模式](integration-patterns.md#错误处理模式)。

### Vue2 兼容层注意事项

`@blueking/ai-blueking/vue2` 通过 `createVue2Wrapper` 包装 Vue3 组件，存在以下差异：

- **`updateAgentInfo` 在 Vue2 下不可用**：该方法已在 Vue3 组件（AIBlueking / ChatBot）上 expose，但**未**注册进 Vue2 wrapper 的 `exposeKeys`，因此 Vue2 消费方无法调用。需要刷新 agentInfo 时请改用 `getChatHelper()?.agent.getAgentInfo()`。
- **插槽注册**：Vue2 的 `AIBluekingV2` 注册 `['codeHeader', 'headerLeft', 'message', 'welcome']`；`ChatBotV2` 注册 `['codeHeader', 'message', 'welcome']`。HITL 场景下 `#message` 仍须透传 `onInterruptResume`。
- **`skills` prop 未在 `ChatBotV2` 注册**。
