# Standalone 子入口

> **自 v2.1.4-beta.8 起** 可用。包路径：`@blueking/ai-blueking/standalone`。

将 Vue 3、chat-x、bkui-vue 等打入独立 bundle，供非 Vue 宿主挂载 `AIBlueking` / `ChatBot`。使用说明见 [Standalone 非 Vue 宿主集成](/guide/integration-modes/standalone-bundle)。

## 导入

```typescript
// 挂载 API + 同源 Vue runtime
import {
  mountAIBlueking,
  mountChatBot,
  mountStandaloneComponent,
  h,
  render,
  createApp,
  AIBlueking,
  ChatBot,
} from '@blueking/ai-blueking/standalone';

import '@blueking/ai-blueking/dist/standalone/style.css';
```

IIFE 全局：`window.AIBluekingStandalone`（与构建 `lib.name` 一致）。

## mountAIBlueking

在非 Vue 宿主挂载完整小鲸面板（含 Nimbus、拖拽、划词等）。

```typescript
function mountAIBlueking(
  container: string | Element,
  options?: StandaloneMountOptions<AIBluekingProps>,
): StandaloneMountHandle<AIBluekingExpose, AIBluekingProps>;
```

`AIBluekingProps` / `AIBluekingExpose` 与 [AIBlueking 组件](/api/ai-blueking/aiblueking) 一致。

## mountChatBot

在非 Vue 宿主挂载 `ChatBot`。

```typescript
function mountChatBot(
  container: string | Element,
  options?: StandaloneMountOptions<ChatBotProps>,
): StandaloneMountHandle<ChatBotExpose, ChatBotProps>;
```

挂载完成后可通过 `handle.expose.whenReady()` / `expose.isReady` 等待独立模式初始化（≥ v2.1.4-beta.13），用法与 Vue 内 `ref` 一致，见 [ChatBot — 初始化就绪](/api/ai-blueking/chatbot#初始化就绪-v214-beta13)。

## mountStandaloneComponent

挂载任意已注册的 Vue 组件（高级用法）。

```typescript
function mountStandaloneComponent<TProps extends object, TExpose>(
  container: string | Element,
  component: Component,
  options?: StandaloneMountOptions<TProps>,
): StandaloneMountHandle<TExpose, TProps>;
```

## StandaloneMountOptions

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `props` | `TProps` | 传给根组件的 props |
| `on` | `StandaloneEventHandlers` | 事件监听；键为 emit 名（kebab-case）或 `onXxx` |

```typescript
type StandaloneEventHandlers = Record<string, (...args: unknown[]) => void>;
```

## StandaloneMountHandle

| 成员 | 类型 | 说明 |
| --- | --- | --- |
| `app` | `App` | Vue 应用实例 |
| `expose` | `TExpose \| null` | 只读，当前组件 expose |
| `getExpose()` | `() => TExpose \| null` | 获取 expose |
| `updateProps(partial)` | `(partial: Partial<TProps>) => void` | 合并更新 props |
| `unmount()` | `() => void` | 卸载 |

## 工具函数

| 函数 | 说明 |
| --- | --- |
| `resolveMountContainer(container)` | 将选择器解析为 `Element`，失败抛错 |
| `buildStandaloneListeners(on)` | 将 `on` 转为 Vue listener props |

## 重导出

与默认入口相同的业务 API（`export * from './index'`），以及：

| 导出 | 说明 |
| --- | --- |
| `createApp`, `h`, `render` | bundle 内 Vue 3 runtime，**勿与外部 vue 混用** |
| `AIBlueking`, `ChatBot` | 组件本身，供 `h(Component, props)` 使用 |
| Managers、composables、类型等 | 与 `@blueking/ai-blueking` 主入口一致 |

## 构建产物

| 文件 | 格式 |
| --- | --- |
| `dist/standalone/index.es.min.js` | ESM |
| `dist/standalone/index.umd.min.js` | UMD |
| `dist/standalone/index.iife.min.js` | IIFE（`AIBluekingStandalone`） |
| `dist/standalone/style.css` | 样式（ES/UMD 需手动引入） |
| `dist/standalone.d.ts` | 类型入口 |
