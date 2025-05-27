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
| `shortcut-click`   | `shortcut: ShortCut`          | 点击快捷操作按钮时触发，返回所点击的快捷操作对象。 |
| `receive-start`    | -                             | AI 开始接收响应时触发。                                                                           |
| `receive-text`     | -                             | 接收到文本片段时触发。                                                                            |
| `receive-end`      | -                             | 响应接收完成时触发。                                                                              |
| `send-message`     | `message: string`             | 发送消息时触发，参数为发送的消息内容。                                                           |                                                   |

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
    @init-session="onInitSession"
  />
</template>

<script lang="ts" setup>
import { AIBlueking } from '@blueking/ai-blueking';
// ... 其他导入和设置 ...

const onShow = () => console.log('Event: show');
const onClose = () => console.log('Event: close');
const onStop = () => console.log('Event: stop');
const onShortcutClick = (shortcut) => console.log('Event: shortcut-click', shortcut);
const onReceiveStart = () => console.log('Event: receive-start');
const onReceiveText = () => console.log('Event: receive-text');
const onReceiveEnd = () => console.log('Event: receive-end');
const onSendMessage = (message) => console.log('Event: send-message', message);
const onInitSession = (success) => console.log('Event: init-session', success ? '成功' : '失败');
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
    @init-session="onInitSession"
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
    onShortcutClick(shortcut) { console.log('Event: shortcut-click', shortcut); },
    onReceiveStart() { console.log('Event: receive-start'); },
    onReceiveText() { console.log('Event: receive-text'); },
    onReceiveEnd() { console.log('Event: receive-end'); },
    onSendMessage(message) { console.log('Event: send-message', message); },
    onInitSession(success) { console.log('Event: init-session', success ? '成功' : '失败'); }
  }
}
</script>
```
:::
