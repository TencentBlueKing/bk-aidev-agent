# Events

组件触发的事件列表。

::: warning 版本变更提示
1.0版本对事件参数和行为有所调整，但保留了原有的事件名称以保持兼容性。
:::

## 事件列表

| 事件名             | 参数                          | 描述                                                                                                 |
| ------------------ | ----------------------------- | ---------------------------------------------------------------------------------------------------- |
| `show`             | -                             | AI 小鲸窗口显示时触发。                                                                                |
| `close`            | -                             | AI 小鲸窗口关闭时触发。                                                                                |
| `stop`             | -                             | 用户点击停止按钮或调用 `handleStop` 方法，成功停止内容生成时触发。                                     |
| `shortcut-click`   | `{ shortcut: IShortcut, formData: Array<Record<string, any>>, source: 'popup' \| 'main' }` | 点击快捷操作按钮时触发，返回所点击的快捷操作对象 (`ShortCut` 类型定义见 [Props](/api/props#shortcut-对象格式))，包含用户填写的表单数据，以及触发来源。 |
| `receive-start`    | -                             | AI 开始接收响应时触发。                                                                           |
| `receive-text`     | `text: string`                | 接收到文本片段时触发。                                                                            |
| `receive-end`      | -                             | 响应接收完成时触发。                                                                              |
| `send-message`     | `message: string`             | 发送消息时触发，参数为发送的消息内容。                                                           |
| `session-init`     | `sessionId: string`           | 会话初始化完成时触发，参数为当前会话ID。从 v1.1.6 开始支持。                                      |
| `session-initialized` | `{ openingRemark: string; predefinedQuestions: string[] }` | 会话初始化完成时触发，参数为欢迎语和预设问题列表。从 v1.1.6 开始支持。                                      |
| `sdk-error`        | `{ apiName: string; code: number; message: string; data: unknown }` | SDK错误发生时触发，参数包含API名称、错误代码、错误信息和相关数据。从 v1.2.8 开始支持。                                    |
| `transfer-messages`| `messageIds: string[]`        | 消息转移操作完成时触发，参数为转移的消息ID列表。从 v1.2.8 开始支持。                                |
| `share-messages`   | `messageIds: string[]`        | 消息分享操作完成时触发，参数为分享的消息ID列表。从 v1.2.8 开始支持。                                |
| `drag-stop`        | `{ x: number; y: number; width: number; height: number }` | 拖拽结束时触发，参数为容器的位置和尺寸信息。从 v1.2.7 开始支持。                                      |
| `resize-stop`      | `{ x: number; y: number; width: number; height: number }` | 调整大小结束时触发，参数为容器的位置和尺寸信息。从 v1.2.7 开始支持。                                      |
| `dragging`         | `{ x: number; y: number; width: number; height: number }` | 拖拽过程中触发，参数为容器的位置和尺寸信息。从 v1.2.7 开始支持。                                      |
| `resizing`         | `{ x: number; y: number; width: number; height: number }` | 调整大小过程中触发，参数为容器的位置和尺寸信息。从 v1.2.7 开始支持。                                      |

## 类型定义

```typescript
interface ShortCut {
  type: string;
  label: string;
  cite?: boolean; // 是否需要引用文本
  prompt?: string; // 发送到AI的提示词
  icon?: string; // 图标名称
}
```

## 使用示例

:::code-group
```vue [Vue 3]
<template>
  <AIBlueking
    :url="apiUrl"
    :shortcuts="myShortcuts"
    @show="onShow"
    @close="onClose"
    @stop="onStop"
    @shortcut-click="onShortcutClick"
    @receive-start="onReceiveStart"
    @receive-text="onReceiveText"
    @receive-end="onReceiveEnd"
    @send-message="onSendMessage"
    @session-init="onSessionInit"
    @session-initialized="onSessionInitialized"
    @sdk-error="onSdkError"
    @transfer-messages="onTransferMessages"
    @share-messages="onShareMessages"
    @drag-stop="onDragStop"
    @resize-stop="onResizeStop"
    @dragging="onDragging"
    @resizing="onResizing"
  />
</template>

<script lang="ts" setup>
import { AIBlueking } from '@blueking/ai-blueking';
// ... 其他导入和设置 ...

const onShow = () => console.log('Event: show');
const onClose = () => console.log('Event: close');
const onStop = () => console.log('Event: stop');
const onShortcutClick = (data) => {
  console.log('Event: shortcut-click', data.shortcut.name);
  console.log('表单数据:', data.formData);
  console.log('触发来源:', data.source);
};
const onReceiveStart = () => console.log('Event: receive-start');
const onReceiveText = (text) => console.log('Event: receive-text', text);
const onReceiveEnd = () => console.log('Event: receive-end');
const onSendMessage = (message) => console.log('Event: send-message', message);
const onSessionInit = (sessionId) => console.log('Event: session-init', sessionId);
const onSessionInitialized = (data) => console.log('Event: session-initialized', data.openingRemark, data.predefinedQuestions);
const onSdkError = (error) => console.log('Event: sdk-error', error.apiName, error.code, error.message, error.data);
const onTransferMessages = (messageIds) => console.log('Event: transfer-messages', messageIds);
const onShareMessages = (messageIds) => console.log('Event: share-messages', messageIds);
const onDragStop = (position) => console.log('Event: drag-stop', position);
const onResizeStop = (position) => console.log('Event: resize-stop', position);
const onDragging = (position) => console.log('Event: dragging', position);
const onResizing = (position) => console.log('Event: resizing', position);
</script>
```

```vue [Vue 2]
<template>
  <AIBlueking
    :url="apiUrl"
    :shortcuts="myShortcuts"
    @show="onShow"
    @close="onClose"
    @stop="onStop"
    @shortcut-click="onShortcutClick"
    @receive-start="onReceiveStart"
    @receive-text="onReceiveText"
    @receive-end="onReceiveEnd"
    @send-message="onSendMessage"
    @session-init="onSessionInit"
    @session-initialized="onSessionInitialized"
    @sdk-error="onSdkError"
    @transfer-messages="onTransferMessages"
    @share-messages="onShareMessages"
    @drag-stop="onDragStop"
    @resize-stop="onResizeStop"
    @dragging="onDragging"
    @resizing="onResizing"
  />
</template>

<script>
import { AIBlueking } from '@blueking/ai-blueking/vue2';
// ... 其他导入和设置 ...

export default {
  methods: {
    onShow() { console.log('Event: show'); },
    onClose() { console.log('Event: close'); },
    onStop() { console.log('Event: stop'); },
    onShortcutClick(data) {
      console.log('Event: shortcut-click', data.shortcut.name);
      console.log('表单数据:', data.formData);
      console.log('触发来源:', data.source);
    },
    onReceiveStart() { console.log('Event: receive-start'); },
    onReceiveText(text) { console.log('Event: receive-text', text); },
    onReceiveEnd() { console.log('Event: receive-end'); },
    onSendMessage(message) { console.log('Event: send-message', message); },
    onSessionInit(sessionId) { console.log('Event: session-init', sessionId); },
    onSessionInitialized(data) { console.log('Event: session-initialized', data.openingRemark, data.predefinedQuestions); },
    onSdkError(error) { console.log('Event: sdk-error', error.apiName, error.code, error.message, error.data); },
    onTransferMessages(messageIds) { console.log('Event: transfer-messages', messageIds); },
    onShareMessages(messageIds) { console.log('Event: share-messages', messageIds); },
    onDragStop(position) { console.log('Event: drag-stop', position); },
    onResizeStop(position) { console.log('Event: resize-stop', position); },
    onDragging(position) { console.log('Event: dragging', position); },
    onResizing(position) { console.log('Event: resizing', position); }
  }
}
</script>
```
:::
