---
name: blueking-chat-x
description: >-
  Use when 在消费方项目中接入 / 使用 @blueking/chat-x 对话组件库（已 npm 安装、非改库源码），
  涉及「某组件怎么用、有哪些 props / events / slots / expose / v-model、怎么搭 AI 对话界面、
  流式输出、停止生成、工具调用 ToolCall、快捷指令、文件上传、@ 资源、自定义消息或侧栏 Tab、
  分享多选、HITL 中断审批、Markdown / 代码 / 公式 / 图表渲染、字号与主题 CSS 变量」等问题时优先使用。
  若是在 packages/chat-x/src 内改库源码（写组件 / composable / 样式 / 测试），改用 chat-x-dev skill。
---

# 使用 @blueking/chat-x

帮助**消费方项目**（已 `npm i @blueking/chat-x`）快速理解组件库、查清每个组件的用法与 API，并写出正确的接入代码。

本 skill 的组件资料在 `references/` 下，由 `scripts/generate-references.mjs` 从库的 `wikis/` 文档自动生成（剥离演示噪音、保留完整 API 与示例）。**它就是组件 API 的真相源**——不要凭记忆臆测 props/事件/插槽名。

## 信息源优先级（先查再写）

| 想知道什么 | 去哪里查（按优先级） |
| --- | --- |
| 某组件的 Props / Events / Slots / Expose / v-model / 用法 | ① `references/_index.md` 定位 slug → ② `references/components/<slug>.md`；③ 若项目装了 chat-x MCP，可用 `get_component_doc` / `search_docs` 交叉验证 |
| 有哪些组件、按能力域怎么选 | `references/_index.md`（能力地图） |
| composable / 类型 / 主题（字号、CSS 变量） | `references/composables/*`、`references/types/*`、`references/theme/*` |
| 最小接入怎么写 | 本文「快速接入」一节 |

> references 缺失或过期时，按本文「再生成 references」一节重新生成。

## 心智模型（一句话）

**消息驱动 + 角色分发**：业务维护一份 `Message[]` → `ChatContainer`（或 `useMessageGroup`）分组 → `MessageRender` 按 `message.role` 分发到具体消息组件 → `ContentRender` 按内容类型分发 → `MarkdownContent` 按 token 分发。

接入心智：**你只负责维护 `messages` 数组和实现 `onSendMessage` 等回调**，组件负责渲染与交互。

## 快速接入（ChatContainer 一站式，推荐入口）

```vue
<template>
  <ChatContainer
    v-model="input"
    :messages="messages"
    :message-status="messageStatus"
    :on-send-message="handleSendMessage"
    :on-stop-sending="handleStopSending"
    @stop-streaming="handleStopStreaming"
  />
</template>

<script setup lang="ts">
  import { ref } from 'vue';
  import { ChatContainer, MessageRole, MessageStatus, type Message, type TagSchema, type UserMessage } from '@blueking/chat-x';

  const input = ref('');
  const messages = ref<Message[]>([]);
  const messageStatus = ref(MessageStatus.Complete);

  const handleSendMessage = async (content: UserMessage['content'], docSchema: TagSchema) => {
    messages.value.push({ id: `u_${Date.now()}`, messageId: `u_${Date.now()}`, role: MessageRole.User, content, status: MessageStatus.Complete });
    const ai: Message = { id: `a_${Date.now()}`, messageId: `a_${Date.now()}`, role: MessageRole.Assistant, content: '', status: MessageStatus.Streaming };
    messages.value.push(ai);
    messageStatus.value = MessageStatus.Streaming;
    // 接你的 SSE / WebSocket，把增量写入 ai.content
    ai.status = MessageStatus.Complete;
    messageStatus.value = MessageStatus.Complete;
  };
  const handleStopSending = async () => { messageStatus.value = MessageStatus.Stop; };
  const handleStopStreaming = () => { messageStatus.value = MessageStatus.Stop; };
</script>
```

前置依赖：`vue >= 3.5`、`bkui-vue 2.x`；样式随导入自动加载，无需手动引入。
需要完全控制布局时改用「`MessageContainer` + `ChatInput` + `useMessageGroup`」组合——细节查 `references/components/message-container.md` 与 `chat-input.md`。

## 怎么查一个组件（标准流程）

1. 在 `references/_index.md` 里按名称/能力域找到组件，拿到它的 `path`。
2. 读 `references/components/<slug>.md`：顶部是能力域 + 导入符号 + 概述 + 关联组件，正文含「核心能力 / 基础用法 / API（Props/Events/Slots/Expose/v-model）/ 类型定义」。
3. 按 API 表格落地代码，需要的类型与常量从 `@blueking/chat-x` 具名导入。

> 接入逻辑常跨多个组件（如 `ChatContainer` 透传 `ChatInput` / `MessageContainer` 的 props，自定义 `#message` 插槽需透传 `onAction` 等回调）。遇到「透传到底要带哪些参数」时，连同关联组件文档一起读。

## 常见坑（消费方高频，先看再调）

| 症状 | 原因 / 修法 |
| --- | --- |
| 自定义 `#message` 插槽后，用户消息的工具（删除/编辑/复制/引用）全失效，但 AI 消息工具正常 | 自定义 `#message` 渲染 `MessageRender` 时漏透传 `on-action` / `on-input-confirm` / `on-shortcut-confirm` / `tippy-options`；AI 消息工具在 `MessageContainer` 内部渲染不经过该插槽，故不受影响 |
| 用户消息编辑态的 `ChatInput` 上传配置与主输入区不一致 | `supportUpload` 需全链路透传 `ChatContainer → MessageContainer → MessageRender → UserMessage`，否则回退默认 `true` |
| 想自定义代码块头部动作（插入/应用代码）无从下手 | 用 `codeHeader` 插槽，参数为 `{ language, token }`（`AIBlueking/ChatBot` 已支持透传） |
| `requestOptions.data` 不知道进 body 还是 query | POST/PUT/PATCH/DELETE 合并进 body；GET/HEAD/OPTIONS 合并进 query（params） |

## 常见任务 → 入口

| 任务 | 入口组件 / 文档 |
| --- | --- |
| 搭完整对话界面 | `components/chat-container.md` |
| 自定义布局（自己拼消息列表 + 输入框） | `components/message-container.md` + `components/chat-input.md` + `composables/use-message-group.md` |
| `/` Prompt、`@` 资源、文件上传 | `components/chat-input.md` |
| 流式输出 / 停止生成 | `components/chat-container.md`（`messageStatus` + `@stop-streaming`） |
| 工具调用 / ToolCall 渲染 | `components/toolcall-render.md`、`components/tool-message.md` |
| HITL 中断 / 工具审批 / 用户提问 | `components/interrupt-message.md`、`components/tool-approval-card.md`、`components/user-question-card.md` |
| FlowAgent 执行 / 知识召回展示 | `components/flow-agent-content.md`、`components/knowledge-rag-content.md` |
| 渲染 Markdown / 代码 / 公式 / 图表 | `components/content-render.md`、`components/markdown-content.md`、`components/code-content.md` |
| 图片预览 / 文件展示 | `components/ai-image.md`、`components/image-preview-group.md`、`components/file-content.md` |
| 快捷指令表单 | `components/shortcut-render.md`、`components/chat-input.md` |
| 分享 / 多选 | `components/chat-container.md`、`components/selection-footer.md` |
| 自定义消息类型 / 侧栏 Tab | `composables/use-custom-tab.md` + `components/chat-container.md` |
| 字号 / 主题 CSS 变量 | `theme/theme.md` |

## 类型与常量速查

```typescript
// 类型按需具名导入
import type { Message, UserMessage, AssistantMessage, ToolMessage, IToolBtn, Shortcut, TagSchema } from '@blueking/chat-x';

// 枚举 / 预置工具
import {
  MessageRole, MessageStatus, MessageContentType,
  CONST_MESSAGE_TOOLS,       // AI 消息默认工具：复制 / 引用 / 重新生成 / 分享
  CONST_USER_MESSAGE_TOOLS,  // 用户消息默认工具：复制 / 引用 / 编辑 / 删除
} from '@blueking/chat-x';
```

更全的类型/常量定义查 `references/types/*`。

## 再生成 references

references 由脚本从 `wikis/` 生成。当库升级、wikis 更新，或 references 缺失/过期时重新生成（**运行脚本前需经用户同意**）：

```bash
# 在 packages/chat-x 下执行（依赖 glob / gray-matter 已在 devDependencies）
node skills/blueking-chat-x/scripts/generate-references.mjs
```

脚本会全量重建 `references/`：`glob wikis` → `gray-matter` 解析 frontmatter → 清洗正文（去 VitePress demo `<script>` / `<div class="demo">` / 内联 style，保留代码围栏与 API 表格）→ 按组件能力域 + composables/types/theme 写出 + 生成 `_index.md`。

## 通用项目规则

中文回复、不擅自处理 eslint/格式、运行脚本需先经同意、git 提交禁用 `--no-verify`、不确定先问——见仓库 `AGENTS.md` 与 `.cursor/rules/project.mdc`。
