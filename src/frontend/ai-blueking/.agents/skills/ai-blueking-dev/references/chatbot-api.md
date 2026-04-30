# ChatBot 组件 API

## Props

| 属性            | 类型                 | 默认值  | 说明                                           |
| --------------- | -------------------- | ------- | ---------------------------------------------- |
| url             | `string`             | `''`    | API 地址（独立模式必填）                       |
| chatHelper      | `IChatHelper`        | -       | 外部 chatHelper（集成模式传入，与 url 二选一） |
| autoLoad        | `boolean`            | `true`  | 是否自动加载最近会话                           |
| sessionCode     | `string`             | -       | 指定初始会话编码                               |
| shortcuts       | `Shortcut[]`         | `[]`    | 快捷指令列表                                   |
| shortcutLimit   | `number`             | `10`    | 快捷指令显示上限                               |
| resources       | `IAiSlashMenuItem[]` | `[]`    | 资源列表（@ 触发）                             |
| prompts         | `string[]`           | -       | 预设提示词（/ 触发）                           |
| helloText       | `string`             | -       | 欢迎语                                         |
| placeholder     | `string`             | -       | 输入框占位符                                   |
| enableSelection | `boolean`            | `false` | 是否启用多选模式（分享用）                     |
| shareLoading    | `boolean`            | `false` | 分享加载状态                                   |
| height          | `string \| number`   | -       | 容器高度                                       |
| maxWidth        | `string \| number`   | -       | 最大宽度                                       |
| extCls          | `string`             | -       | 额外 CSS 类名                                  |
| requestOptions  | `IRequestOptions`    | -       | 请求配置（仅独立模式，含 headers/data）        |
| resizeProps     | `ResizeProps`        | -       | ResizeLayout 配置（执行情况侧面板拖拽）        |

## Events

| 事件              | 参数                                       | 说明                           |
| ----------------- | ------------------------------------------ | ------------------------------ |
| send-message      | `(message: string)`                        | 用户发送消息                   |
| receive-start     | -                                          | 流式响应开始（仅独立模式）     |
| receive-text      | -                                          | 流式接收文本（仅独立模式）     |
| receive-end       | -                                          | 流式响应结束（仅独立模式）     |
| stop              | -                                          | 用户停止生成                   |
| error             | `(error: Error)`                           | 发生错误（仅独立模式）         |

> **注意**：AIBlueking 集成模式下，ChatBot 的 `@error` 不会被透传给业务方，所有错误统一通过 AIBlueking 的 `@sdk-error` 事件暴露。详见 [集成模式 - 错误处理](integration-patterns.md#错误处理模式)。
| session-switched  | `(session: ISession \| null)`              | 会话切换完成                   |
| shortcut-click    | `({ shortcut, source })`                   | 快捷指令点击                   |
| agent-info-loaded | `(chatHelper: IChatHelper)`                | Agent 信息加载完成（独立模式） |
| feedback          | `(tool, message, reasonList, otherReason)` | 反馈提交成功                   |
| confirm-share     | `(messages: Message[])`                    | 确认分享                       |
| cancel-share      | -                                          | 取消分享                       |
| request-share     | -                                          | 请求进入分享模式               |

## Slots

| 插槽名     | 参数                                     | 说明                                                  |
| ---------- | ---------------------------------------- | ----------------------------------------------------- |
| codeHeader | `({ language: string, token: Token[] })` | 自定义 markdown 代码块头部区域，常用于插入/应用等动作 |

```vue
<AIBlueking :url="apiUrl">
  <template #codeHeader="{ language, token }">
    <span @click="handleCodeInsert(language, token)">插入</span>
    <span @click="handleCodeApply(language, token)">应用</span>
  </template>
</AIBlueking>
```

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
| messages       | `ComputedRef<Message[]>`                 | 当前消息列表             |
| currentSession | `ComputedRef<ISession \| null>`          | 当前会话                 |
| isGenerating   | `ComputedRef<boolean>`                   | 是否正在生成             |

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
├── chatHelper.agent.getAgentInfo()    // 获取 Agent 信息
├── chatHelper.session.getSessions()   // 获取会话列表
├── props.sessionCode 存在?
│   ├── 是 → chooseSession(sessionCode)
│   └── 否 → chooseSession(列表第一个)
└── emit('agent-info-loaded', chatHelper)
```

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
| `rename` | `(newName: string)` | 手动重命名会话 |
| `help-click` | 无 | 点击转人工按钮 |
| `share` | 无 | 点击分享按钮 |
| `toggle-compression` | 无 | 切换面板压缩/展开 |
| `close` | 无 | 点击关闭按钮 |

> 完整的 AIBlueking 事件监听示例见 [集成模式与示例](integration-patterns.md#aiblueking-会话相关事件)。
