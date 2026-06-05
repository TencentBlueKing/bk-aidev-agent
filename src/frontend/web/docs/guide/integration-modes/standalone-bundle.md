# Standalone 非 Vue 宿主集成

> **自 v2.1.4-beta.8 起**，`@blueking/ai-blueking` 提供 **`/standalone`** 子入口：将 **Vue 3 runtime** 与 **chat-x** 等依赖打入同一 bundle，供 **React、Angular、jQuery、纯 HTML** 等非 Vue 页面通过 `mountAIBlueking` / `mountChatBot` 挂载小鲸，无需在宿主安装 Vue。

## 适用场景

| 场景 | 说明 |
| --- | --- |
| 遗留系统 / 多技术栈页面 | 主应用不是 Vue，但需要在某一 DOM 区域嵌入 AI 对话 |
| 无构建工具的快速接入 | 通过 `<script>` 引入 IIFE，全局变量 `AIBluekingStandalone` |
| 与默认入口对比 | 默认 `@blueking/ai-blueking` 要求宿主提供 Vue 3 + chat-x；Standalone 开箱即用，包体积更大 |

::: warning 与 Vue 2 入口的区别
Standalone **仅支持 Vue 3 运行时**。Vue 2 项目请继续使用 [`@blueking/ai-blueking/vue2`](/guide/integration-modes/aiblueking-floating) 或升级宿主到 Vue 3 后再评估 Standalone。
:::

## 安装

```bash
npm install @blueking/ai-blueking
# 或 pnpm / yarn
```

## 方式一：npm + 打包工具（推荐）

### 引入样式

Standalone 的 ES/UMD 构建会将 chat-x 与图标样式合并到独立 CSS 文件，**必须**引入：

```typescript
import '@blueking/ai-blueking/dist/standalone/style.css';
```

### 挂载完整小鲸（AIBlueking）

```typescript
import { mountAIBlueking } from '@blueking/ai-blueking/standalone';

const handle = mountAIBlueking('#ai-root', {
  props: {
    url: 'https://your-aidev-url.com/api/',
    enablePopup: true,
    requestOptions: {
      headers: () => ({ Authorization: `Bearer ${getToken()}` }),
    },
  },
  on: {
    'send-message': (message: string) => console.log('发送:', message),
    'sdk-error': (error) => console.error('SDK 错误:', error),
  },
});

// 编程式 API（与 Vue 模板 ref 的 expose 一致；show 在 sessionList 就绪后 resolve）
await handle.expose?.show();
handle.expose?.sendMessage('你好');
handle.updateProps({ url: 'https://next-api.example.com/api/' });
handle.unmount();
```

### 仅挂载聊天区（ChatBot）

```typescript
import { mountChatBot } from '@blueking/ai-blueking/standalone';

const chat = mountChatBot('#chat-container', {
  props: {
    url: 'https://your-aidev-url.com/api/',
    height: '600px',
  },
  on: {
    error: (err: Error) => console.error(err),
  },
});

chat.expose?.sendMessage('Hello');
```

### 事件监听写法

`on` 的键支持：

- **kebab-case**（与组件 `emit` 名一致）：`'send-message'`、`'sdk-error'`
- **onXxx**（Vue 3 listener 形式）：`onSendMessage`、`onSdkError`

内部会统一映射为 Vue 的 `onSendMessage` 等 props。

## 方式二：`<script>` 直引（IIFE）

构建产物：`dist/standalone/index.iife.min.js`，全局名 **`AIBluekingStandalone`**。

```html
<link rel="stylesheet" href="/static/ai-blueking/standalone/style.css" />
<div id="ai-root" style="width: 100%; height: 100vh;"></div>
<script src="/static/ai-blueking/standalone/index.iife.min.js"></script>
<script>
  const ai = AIBluekingStandalone.mountAIBlueking('#ai-root', {
    props: {
      url: 'https://your-aidev-url.com/api/',
      enablePopup: true,
    },
    on: {
      sendMessage: function (message) {
        console.log(message);
      },
    },
  });

  // 打开面板
  ai.expose && ai.expose.show();
</script>
```

::: info UMD / ES 路径
- ESM：`@blueking/ai-blueking/standalone` → `dist/standalone/index.es.min.js`
- UMD：`dist/standalone/index.umd.min.js`
- 类型：`dist/standalone.d.ts`（`import type { StandaloneMountHandle } from '@blueking/ai-blueking/standalone'`）
:::

## 高级：自定义渲染（h / render）

Standalone 同时导出与 bundle **同源** 的 `h`、`render`、`createApp`。自定义侧栏、VNode 组合时**必须**从本入口导入，**不要**再安装一份外部 `vue`，否则会出现 VNode 不同源错误。

```typescript
import { h, render, ChatBot } from '@blueking/ai-blueking/standalone';
import '@blueking/ai-blueking/dist/standalone/style.css';

const container = document.querySelector('#ai-root');
if (container) {
  render(
    h(ChatBot, {
      url: 'https://your-aidev-url.com/api/',
      onError: (err: Error) => console.error(err),
    }),
    container,
  );
}
```

侧栏 `getSideRenderComponent` 的 `createElement` 参数也应使用本入口的 `h`，详见 [侧栏 Tab 自定义渲染](/guide/core-features/side-render-customization#standalone-宿主注意)。

## StandaloneMountHandle API

| 成员 | 说明 |
| --- | --- |
| `app` | 内部 `createApp` 实例 |
| `expose` / `getExpose()` | 组件 `defineExpose` 暴露的方法（如 `show`、`sendMessage`） |
| `updateProps(partial)` | 合并更新 props，不销毁应用 |
| `unmount()` | 卸载并清理 |

类型：`StandaloneMountOptions`、`StandaloneMountHandle`、`StandaloneEventHandlers` 见 [Standalone API](/api/ai-blueking/standalone)。

## 与默认入口对比

| 对比项 | `@blueking/ai-blueking`（默认） | `@blueking/ai-blueking/standalone` |
| --- | --- | --- |
| 宿主要求 | Vue 3 + 安装 chat-x 等 peer | 无 Vue 要求 |
| Vue runtime | 由宿主提供 | 打入 bundle |
| chat-x | peerDependency | 内联 |
| 集成方式 | `<AIBlueking>` / `<ChatBot>` SFC | `mountAIBlueking` / `mountChatBot` |
| 包体积 | 较小 | 较大（约 2.5MB+ gzip 后仍显著大于默认 ES 包） |
| Vue 2 | `./vue2` 子入口 | 不支持 |

## 注意事项

1. **样式**：ES/UMD 需手动引入 `dist/standalone/style.css`；IIFE 构建会将 CSS 注入 JS（与 Vue3 IIFE 行为一致），仍建议确认页面无样式冲突。
2. **容器**：`container` 支持 CSS 选择器字符串或 `Element`；找不到节点时抛出 `[ai-blueking] mount container not found: ...`。
3. **expose 时机**：挂载后建议 `await nextTick()` 或短延迟后再调用 `expose` 上的方法（与 Vue 组件一致）。
4. **Slots**：非 Vue 宿主无法使用 Vue 插槽语法；需通过 `h` 传 slot 对象，或使用 `mountStandaloneComponent` 自行封装（见 API 文档）。

## 相关文档

- [Standalone API](/api/ai-blueking/standalone)
- [编程式控制](/guide/advanced-usage/programmatic-control)（Vue 宿主下的 ref / expose）
- [ChatBot 页面嵌入](/guide/integration-modes/chatbot-embedded)（Vue SFC 等价场景）
- [AIBlueking 浮窗模式](/guide/integration-modes/aiblueking-floating)
