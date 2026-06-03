---
name: 最佳实践
slug: best-practices
category: ai
description: >
  @blueking/chat-x 的 AI 优先开发、性能优化、安全规范和集成模式最佳实践。
aiSummary: >
  chat-x 最佳实践覆盖四个方面：AI 优先开发（aiSummary 编写、MCP 元数据、组件选型路径），
  性能优化（CSS containment、流式节流、图片懒加载、响应式粒度），安全规范（DOMPurify、
  v-html 限制、CSP），集成模式（chat-helper 配合、SSE/WebSocket、useMessageGroup
  生命周期、useCustomTab 侧栏扩展、错误处理）。
relatedComponents: []
sinceVersion: '1.0.0'
---

# 最佳实践

## AI 优先开发

### 为 AI Agent 编写文档

每个组件的 Wiki 页面应包含结构化 frontmatter，让 AI Agent 通过 MCP 快速理解组件：

```yaml
---
name: 组件显示名
slug: 唯一标识（用于 MCP 查询）
kind: component
domain: setup | message | rendering | input | agent | feedback | media | helper
description: 一句话人类可读描述
aiSummary: >
  2-4 句话面向 AI 的精确摘要，包含：
  1. 组件职责（做什么）
  2. 必填 props（必须传什么）
  3. 关键行为（有什么特殊机制）
  4. 常见搭配（和谁一起用）
relatedComponents:
  - slug: 关联组件标识
    relation: 关系描述
---
```

**aiSummary 编写原则**：

- 第一句说清「这个组件做什么」
- 提及必填 props 的名称和类型
- 说明关键交互行为（如 slot 机制、v-model 双向绑定）
- 列出常见搭配组件（如「通常与 MessageContainer 配合使用」）

### AI Agent 组件选型路径

设计 API 时应考虑 AI Agent 的选型路径——AI 通常按以下顺序决策：

```
1. 需求匹配：「我需要展示 AI 对话」→ 按 domain 过滤组件
2. 粒度选择：「一站式还是自定义」→ ChatContainer vs 自由组合
3. 配置填充：「需要哪些 props」→ 读 aiSummary 中的必填字段
4. 扩展判断：「内置能力够不够」→ 查 slot / 类型扩展 / 事件
```

API 命名应遵循可预测模式：`onXxxAction`（函数 prop）、`v-model:xxx`（双向绑定）、`#xxx`（slot）。

### MCP 服务集成

在 Cursor 等 AI IDE 中，通过 `.cursor/mcp.json` 配置 MCP Server：

```json
{
  "mcpServers": {
    "chat-x": {
      "command": "npx",
      "args": ["tsx", "packages/chat-x/mcp/server.ts"]
    }
  }
}
```

AI Agent 即可使用三个工具：

| 工具                | 参数                   | 用途                                             |
| ------------------- | ---------------------- | ------------------------------------------------ |
| `list_components`   | `kind?`, `domain?` | 按文档类型/能力域过滤组件列表                    |
| `get_component_doc` | `slug`                 | 获取组件完整文档（含 AI 摘要，已清洗运行时代码） |
| `search_docs`       | `keyword`              | 按关键词搜索文档                                 |

## 性能优化

### CSS containment

对单条消息根节点使用 `contain` 属性，将布局和绘制限制在元素内部，减轻长列表滚动时的全局重排：

```css
.message-item {
  contain: layout paint;
}
```

### 流式渲染节流

AI 流式输出时，避免每个 token 到达时同步触发重排和滚动。推荐：

- **`requestAnimationFrame`**：合并同一帧内的多次内容追加
- **业务层批量写入**：将多个 token 在 16ms 窗口内合并后一次性更新 `message.content`

```typescript
let buffer = '';
let rafId = 0;

function onToken(token: string) {
  buffer += token;
  if (!rafId) {
    rafId = requestAnimationFrame(() => {
      aiMessage.content += buffer;
      buffer = '';
      rafId = 0;
    });
  }
}
```

### 图片懒加载

`AiImage` 提供 `lazy` prop，启用后使用 `IntersectionObserver` 在接近视口时才加载图片，避免长对话一次性加载全部图片：

```vue
<AiImage :src="url" lazy />
```

### 响应式粒度

- **固定值**：不要写 `computed(() => 固定对象)`，改用模块级常量或 `const`
- **纯交互状态**（拖拽坐标、临时 hover 等不参与模板渲染）：使用普通 `let` 变量
- **渲染相关但不需深层追踪**：使用 `shallowRef` 避免不必要的深层响应式
- **`computed` + 对象展开**：`{ ...obj }` 得到普通对象，修改属性不会触发视图更新，hover 等状态应用本地 `ref` 管理

### useMessageGroup 性能

`useMessageGroup` 内部使用 `watchEffect` 对整个 `messages` 数组做分组计算。对于大量消息（1000+）的场景：

- `messages` 使用 `ref`（深层响应式）确保数组内元素变更可追踪
- 避免在分组过程中创建不必要的中间对象
- `MessageGroup` 的 `isHover`、`checked` 等 UI 状态在组件内本地管理

## 安全规范

### DOMPurify

内置 `MarkdownContent` 使用 DOMPurify 对渲染后的 HTML 做白名单清洗（含 KaTeX 扩展标签）。业务扩展 Markdown 管道时，**必须保持同一套 sanitize 策略**。

### v-html 使用原则

- 仅对 **已消毒** 的字符串使用 `v-html`
- 用户输入、模型输出默认视为不可信，必须经 sanitize 或转义

### XSS 防护

聊天场景下，用户消息、工具返回、链接、图片 URL 都可能成为注入面：

- 文本展示优先走组件库已加固的路径（Markdown + DOMPurify）
- 自定义消息类型中若拼接 HTML，使用 DOMPurify 或模板转义
- 禁止 `eval`、动态 `new Function` 执行不可信字符串

### CSP 配置

生产环境配置 `Content-Security-Policy`，限制 `script-src`、`img-src`、`connect-src`：

```
Content-Security-Policy:
  default-src 'self';
  script-src 'self';
  style-src 'self' 'unsafe-inline';
  img-src 'self' data: https:;
  connect-src 'self' wss: https:;
```

KaTeX 和 Mermaid 可能需要 `'unsafe-inline'`（style），但 `script-src` 应严格限制。

## 集成模式

### 与 @blueking/chat-helper 配合

`@blueking/chat-x` 负责 **对话 UI**，`@blueking/chat-helper` 负责 **会话管理和接口封装**：

```
chat-helper（业务 SDK）
├── 维护 messages 状态机
├── SSE/WebSocket 连接管理
├── 发送/停止/重试逻辑
└── Message[] 标准化输出
         │
         ▼
chat-x（UI 组件）
├── ChatContainer / MessageContainer
├── ChatInput
└── UI 事件通过 props 回调回接到 helper
```

### SSE / WebSocket 流式响应

标准集成模式：

```typescript
async function streamChat(userContent: string) {
  const aiMessage: Message = {
    id: `ai_${Date.now()}`,
    messageId: `ai_${Date.now()}`,
    role: MessageRole.Assistant,
    content: '',
    status: MessageStatus.Streaming,
  };
  messages.value.push(aiMessage);

  const source = new EventSource('/api/chat');
  source.onmessage = event => {
    aiMessage.content += event.data;
  };
  source.addEventListener('done', () => {
    aiMessage.status = MessageStatus.Complete;
    source.close();
  });
  source.onerror = () => {
    aiMessage.status = MessageStatus.Error;
    source.close();
  };
}
```

### 消息生命周期管理

```
创建消息 → Pending
    │
    ▼
流式输出 → Streaming（逐步追加 content）
    │
    ├─ 正常结束 → Complete
    ├─ 用户停止 → Stop
    └─ 出错 → Error
```

**关键规则**：

- 流式结束后 **必须** 将 `status` 设为 `Complete`，否则工具栏和引用行为不一致
- 切换会话时 **重置** `messages` 数组，`useMessageGroup` 会自动重新计算分组
- 末尾消息为 `User` 时，`useMessageGroup` 自动追加 `Loading` 组（显示等待动画）

### useCustomTab 侧栏扩展

深层组件（如自定义 Activity 子类型）可通过 `useCustomTabConsumer` 动态添加侧栏面板：

```typescript
import { useCustomTabConsumer } from '@blueking/chat-x';

const { addCustomTab } = useCustomTabConsumer()!;

function showDetail(item: { id: string; name: string }) {
  addCustomTab({
    label: item.name,
    name: item.id,
    data: {
      component: DetailPanel,
      props: { itemId: item.id },
    },
  });
}
```

**注意**：`useCustomTabConsumer` 依赖 `ChatContainer` 内部的 `provide`，仅在 `ChatContainer` 子树中可用。

### 错误处理

- **消息级失败**：设置 `MessageStatus.Error`，可在 `content` 中写入用户可读文案
- **通用错误展示**：使用内置 `CommonErrorContent` 组件
- **网络/解析错误**：在 helper 层统一捕获，转换为用户可读文案后写入消息，避免裸堆栈泄露

```typescript
try {
  await sendToAPI(content);
} catch (error) {
  aiMessage.status = MessageStatus.Error;
  aiMessage.content = '请求失败，请稍后重试。';
}
```

## 相关文档

- [架构总览](../architecture.md) — 渲染管线、数据流
- [设计理念](../design-philosophy.md) — AI 优先策略、API 设计原则
- [自定义消息类型](./custom-message.md) — 三级扩展机制详解
- [MCP 服务](./mcp.md) — MCP Server 配置与工具说明
