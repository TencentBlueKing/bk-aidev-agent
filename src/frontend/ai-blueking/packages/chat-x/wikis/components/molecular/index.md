# 分子组件

分子组件是由原子组件组合而成的复杂组件，提供完整的业务功能单元。

## 顶层容器（直接使用）

这类组件是业务页面的直接使用入口，通常不需要单独使用其子消息组件。

| 组件名             | 说明                                                                                                                                                                                                                    | 文档                           |
| ------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------ |
| `ChatContainer`    | 完整聊天容器；整合 `MessageContainer` + `ChatInput` + `ExecutionSummary` + `ShortcutRender`；内置分栏布局、执行摘要、自定义 Tab、分享模式和空状态欢迎页                                                                 | [查看](./chat-container.md)    |
| `ChatInput`        | 聊天输入框；`AiSlashInput` 富文本编辑，`/` 唤出 Prompt 菜单、`@` 唤出资源菜单；支持引用气泡（`CiteContent`）、文件上传（`FileUploadBtn`）、快捷指令（`ShortcutBtns`）；`onSendMessage` / `onStopSending` 控制发送与停止 | [查看](./chat-input.md)        |
| `MessageContainer` | 消息列表容器；内置 `useContainerScrollProvider` 滚动管理（自动吸底、返回底部按钮）、`useGlobalConfig` 注册 Teleport 挂载点；遍历 `messages` 调用 `MessageRender`，并注入 `MessageTools` 工具栏                          | [查看](./message-container.md) |
| `AiSelection`      | AI 划词弹窗；监听 `selectionchange` / `mouseup` / `scroll` / `resize` 等全局事件定位文本选区，Tippy 渲染快捷指令列表，触发 `@select-shortcut`                                                                           | [查看](./ai-selection.md)      |

## 渲染调度组件

根据消息类型 / 内容类型自动分发到对应子组件。

| 组件名           | 说明                                                                                                                                                                   | 文档                         |
| ---------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------- |
| `MessageRender`  | 消息级调度器；按 `message.role` 分发到 `UserMessage` / `AssistantMessage` / `InfoMessage` / `ActivityMessage` / `ReasoningMessage` / `ToolMessage` / `LoadingMessage`  | [查看](./message-render.md)  |
| `ContentRender`  | 内容级调度器；按 `MessageContentType` 分发到 `MarkdownContent` / `TextContent` / `ImageContent` / `CiteContent` / `ReferenceContent` / `KeyValueContent` 等            | [查看](./content-render.md)  |
| `ToolcallRender` | Tool Call 渲染；折叠态显示状态图标 + 名称，展开态渲染参数（JSON/键值对）+ `ToolMessage`，状态映射 `Pending`→加载 / `Streaming`→执行中 / `Complete`→成功 / `Error`→失败 | [查看](./toolcall-render.md) |
| `ShortcutRender` | 快捷指令表单渲染；按 `shortcut.components` 动态注册 Vue 组件，`watchEffect` 初始化 `formModel`（`default → props.default → modelValue`），表单提交触发 `@submit`       | [查看](./shortcut-render.md) |

## 消息类型组件

由 `MessageRender` 内部调度，也可单独使用。

| 组件名             | `MessageRole` / 触发条件     | 说明                                                                                                                           | 文档                           |
| ------------------ | ---------------------------- | ------------------------------------------------------------------------------------------------------------------------------ | ------------------------------ |
| `UserMessage`      | `user`                       | 用户消息气泡；蓝色背景，支持 `KeyValueContent` 显示引用文件信息，`useClipboard` 复制                                           | [查看](./user-message.md)      |
| `AssistantMessage` | `assistant`                  | AI 助手消息；完整状态机（完成/错误/停止/加载/流式）；调用 `ContentRender`、`ToolcallRender`、`ReasoningMessage`、`FileContent` | [查看](./assistant-message.md) |
| `LoadingMessage`   | `assistant` + `Pending` 状态 | AI 思考中占位；`AiLoading` 三色渐变动画 + "小鲸正在思考中"                                                                     | [查看](./loading-message.md)   |
| `ReasoningMessage` | `assistant` + 含推理内容     | 推理过程折叠面板；`AiLoading` / 错误图标 + `MarkdownContent` 渲染推理文本，`v-model:collapsed` 控制展开                        | [查看](./reasoning-message.md) |
| `ActivityMessage`  | `assistant` + `activityType` | 活动消息（文件引用 / 搜索结果等）；`activityType` 决定内容类型，`content.items[].name` + `originFile` 驱动渲染                 | [查看](./activity-message.md)  |
| `ToolMessage`      | `tool`                       | 工具返回结果；`DescPanel` 渲染 JSON 结构，对象→键值列表 / 数组→索引列表 / 字符串→纯文本                                        | [查看](./tool-message.md)      |
| `InfoMessage`      | `info`                       | 系统信息提示；居中灰色文字气泡，支持 `@close` 事件                                                                             | [查看](./info-message.md)      |

## 通用功能组件

跨消息类型复用的功能性组件。

| 组件名                | 说明                                                                                                                              | 内部使用方                        | 文档                           |
| --------------------- | --------------------------------------------------------------------------------------------------------------------------------- | --------------------------------- | ------------------------------ |
| `MessageTools`        | 消息工具栏；内置复制 / 点赞 / 踩 / 重新生成等 `ToolBtn`，激活态图标切换（`like` → `activeLike`），`onAction` 回调仅传 `tool` 对象 | `MessageContainer`                | [查看](./message-tools.md)     |
| `MessageUserFeedback` | 用户反馈弹层；点踩后弹出原因选择表单，提交触发 `@feedback`                                                                        | `MessageTools`                    | [查看](./user-feedback.md)     |
| `ExecutionSummary`    | 执行摘要面板；时间线展示工具调用和 FlowAgent 记录，支持关键词搜索和对话定位                                                       | `ChatContainer`                   | [查看](./execution-summary.md) |
| `FileContent`         | 附件文件展示；图标、文件名、大小三行布局，支持点击预览（`@mounted` 回调 el）                                                      | `AssistantMessage`、`UserMessage` | [查看](./file-content.md)      |

## 快速参考

### 最小完整接入

```typescript
import { MessageContainer, ChatInput, MessageStatus, MessageRole, type Message } from '@blueking/chat-x';
```

```vue
<template>
  <div class="chat-page">
    <MessageContainer
      :messages="messages"
      :message-status="messageStatus"
      :on-agent-action="handleAgentAction"
      @stop-streaming="handleStopStreaming"
    />
    <ChatInput
      v-model="inputValue"
      :message-status="messageStatus"
      :prompts="prompts"
      :on-send-message="handleSendMessage"
      :on-stop-sending="handleStopSending"
    />
  </div>
</template>

<script setup lang="ts">
  import { ref } from 'vue';
  import { MessageContainer, ChatInput, MessageStatus, type Message } from '@blueking/chat-x';

  const inputValue = ref('');
  const messageStatus = ref(MessageStatus.Complete);
  const messages = ref<Message[]>([]);
  const prompts = ['帮我写文章', '总结内容', '翻译'];

  const handleSendMessage = async (value: string) => {
    /* 发送消息 */
  };
  const handleStopSending = async () => {
    /* 停止发送 */
  };
  const handleStopStreaming = () => {
    /* 停止流式输出 */
  };
  const handleAgentAction = async tool => {
    /* 处理 Agent 动作 */
  };
</script>
```

### 单独使用消息组件

```typescript
import {
  MessageRender, // 自动调度，推荐
  AssistantMessage, // 仅 AI 消息
  UserMessage, // 仅用户消息
  ContentRender, // 仅内容区域
} from '@blueking/chat-x';
```
