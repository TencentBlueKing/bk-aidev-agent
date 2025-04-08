# Events

组件触发的事件列表。

| 事件名             | 参数                          | 描述                                                                                                 |
| ------------------ | ----------------------------- | ---------------------------------------------------------------------------------------------------- |
| `show`             | -                             | AI 小鲸窗口显示时触发。                                                                                |
| `close`            | -                             | AI 小鲸窗口关闭时触发。                                                                                |
| `stop`             | -                             | 用户点击停止按钮或调用 `handleStop` 方法，成功停止内容生成时触发。                                     |
| `shortcut-click`   | `shortcut: ShortCut`          | 点击快捷操作按钮时触发，返回所点击的快捷操作对象 (`ShortCut` 类型定义见 [Props](/api/props#shortcut-对象格式))。 |

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
  />
</template>

<script lang="ts" setup>
import AIBlueking from '@blueking/ai-blueking';
 // ... 其他导入和设置 ...

const onShow = () => console.log('Event: show');
const onClose = () => console.log('Event: close');
const onStop = () => console.log('Event: stop');
const onShortcutClick = (shortcut) => console.log('Event: shortcut-click', shortcut);
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
  />
</template>

<script>
import AIBlueking from '@blueking/ai-blueking/vue2';
 // ... 其他导入和设置 ...

export default {
  methods: {
    onShow() { console.log('Event: show'); },
    onClose() { console.log('Event: close'); },
    onStop() { console.log('Event: stop'); },
    onShortcutClick(shortcut) { console.log('Event: shortcut-click', shortcut); }
  }
}
</script>
```
:::
