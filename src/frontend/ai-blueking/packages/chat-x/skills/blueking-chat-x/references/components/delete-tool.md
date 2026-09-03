# DeleteTool 删除确认按钮

> 能力域：工具与反馈 ｜ 未从包入口导出：内部组件，请通过上层组件使用 ｜ since 1.0.0

消息删除二次确认工具。 源码位置：src/components/message-tools/delete-tool/delete-tool.vue。

**关联**：tool-btn（删除图标与触发入口）、message-tools（delete 工具 id 时自动采用本组件）

---

# DeleteTool 删除确认按钮
## 源码事实

- **源码位置**：`src/components/message-tools/delete-tool/delete-tool.vue`
- **能力域**：工具与反馈
- **能力说明**：消息删除二次确认工具。

> **能力域**：工具与反馈

删除操作的二次确认组件。点击删除图标后弹出确认弹窗，用户需再次点击"删除"按钮才会触发 `confirm` 事件，防止误删。内部由 `ToolBtn`（触发按钮）+ `Tippy`（确认弹窗）组合实现。

> **提示**：此组件通常**不需要手动使用**，`MessageTools` 在工具列表中检测到 `id === 'delete'` 时会自动使用此组件替换普通 `ToolBtn`。

## 组件结构

```
Tippy（trigger='click'，interactive，appendTo=body）
  │
  ├── ToolBtn（触发按钮，id/name/description/disabled 透传）
  │
  └── #content: div.ai-delete-confirm（width: 280px）
        ├── .ai-delete-confirm__title   "确认删除该回答？"（16px, bold）
        ├── .ai-delete-confirm__desc    "删除操作无法撤回，请谨慎操作！"
        └── .ai-delete-confirm__actions（justify-content: flex-end，gap: 8px）
              ├── Button（theme="danger", size="small"）→ 点击触发 confirm + 关闭弹窗
              └── Button（size="small"）→ 点击触发 cancel + 关闭弹窗

disabled=true 时：Tippy onShow 返回 false，弹窗不打开
```

## 基础用法

```vue
<template>
  <DeleteTool
    id="delete"
    name="删除"
    description="删除消息"
    @confirm="handleConfirm"
    @cancel="handleCancel"
  />
</template>

<script setup lang="ts">
  import { DeleteTool } from '@blueking/chat-x';

  const handleConfirm = () => {
    console.log('用户确认删除，执行删除操作');
  };

  const handleCancel = () => {
    console.log('用户取消删除');
  };
</script>
```

## 禁用状态

`disabled=true` 时，点击按钮不弹出确认弹窗：

```vue
<template>
  <DeleteTool
    id="delete"
    name="删除"
    description="删除消息"
    :disabled="true"
    @confirm="handleConfirm"
  />
</template>
```

## 在 MessageTools 中的自动使用

`MessageTools` 在渲染工具列表时，若检测到 `tool.id === 'delete'`，会自动使用 `DeleteTool` 替换普通 `ToolBtn`，无需手动配置：

```vue
<template>
  <MessageTools
    :update-tools="updateTools"
    :on-action="handleAction"
  />
</template>

<script setup lang="ts">
  import { MessageTools, type IToolBtn } from '@blueking/chat-x';

  // delete 会自动使用 DeleteTool 渲染，点击弹确认框，确认后 onAction 触发
  const updateTools: IToolBtn[] = [
    { id: 'like', name: '点赞', description: '点赞' },
    { id: 'unlike', name: '不满意', description: '不满意' },
    { id: 'delete', name: '删除', description: '删除消息' },
  ];

  const handleAction = async (tool: IToolBtn) => {
    if (tool.id === 'delete') {
      // 只有用户在弹窗中点击"删除"确认后，才会走到这里
      console.log('执行删除:', tool.id);
    }
  };
</script>
```

## API

### Props

| 属性名       | 类型                                                                       | 必填 | 默认值 | 说明                                                                 |
| ------------ | -------------------------------------------------------------------------- | ---- | ------ | -------------------------------------------------------------------- |
| id           | `string`                                                                   | 是   | —      | 按钮标识，传 `"delete"` 时显示删除图标                               |
| name         | `string`                                                                   | 否   | —      | 按钮名称，`id` 无对应图标时作为文本内容渲染                          |
| description  | `string`                                                                   | 否   | —      | `ToolBtn` 的 tooltip 文本；`disabled=true` 时不显示                  |
| disabled     | `boolean`                                                                  | 否   | —      | 禁用态；`true` 时点击不弹出确认弹窗，`ToolBtn` 同步禁用              |
| tippyOptions | `Partial<Omit<TippyOptions, 'getReferenceClientRect' \| 'triggerTarget'>>` | 否   | —      | 覆盖确认弹窗（`Tippy`）的默认配置；可覆盖 `placement`、`appendTo` 等 |

### Events

| 事件名  | 参数 | 触发时机                           |
| ------- | ---- | ---------------------------------- |
| confirm | —    | 用户在确认弹窗点击"删除"按钮后触发 |
| cancel  | —    | 用户在确认弹窗点击"取消"按钮后触发 |

## 类型定义

```typescript
import type { IToolBtn } from '@blueking/chat-x';
import type { TippyOptions } from 'vue-tippy';

export type DeleteToolProps = IToolBtn & {
  disabled?: boolean;
  tippyOptions?: Partial<Omit<TippyOptions, 'getReferenceClientRect' | 'triggerTarget'>>;
};
```

## 样式说明

确认弹窗（`.ai-delete-confirm`）样式：

```scss
.ai-delete-confirm {
  width: 280px;
  padding: 16px;
  font-size: 12px;
  color: #4d4f56;
  background: #fff;
  border: 1px solid #dcdee5;
  box-shadow: 0 2px 6px 0 #0000001a;

  &__title {
    margin-bottom: 6px;
    font-size: 16px;
    font-weight: 600;
    line-height: 22px;
    color: #313238;
  }

  &__desc {
    margin-bottom: 16px;
    line-height: 20px;
  }

  &__actions {
    display: flex;
    gap: 8px;
    justify-content: flex-end;
  }
}
```

## 注意事项

1. **确认才触发**：`confirm` 事件只在用户点击弹窗内"删除"按钮后触发；直接点击 `ToolBtn` 触发器不会触发任何业务事件
2. **`disabled` 双重保障**：`disabled=true` 时，`ToolBtn` 的 JS 层拦截 click，且 `Tippy` 的 `onShow` 返回 `false`，弹窗不会弹出
3. **弹窗挂载至 body**：默认 `appendTo: () => document.body`，避免被父容器 `overflow: hidden` 裁剪
4. **组件卸载自动关闭**：`onUnmounted` 时调用 `hide()` 关闭弹窗，防止组件销毁后弹窗残留
5. **`MessageTools` 自动处理**：通常不需要直接使用此组件，`MessageTools` 会在 `id === 'delete'` 时自动替换

## 关联组件

- [ToolBtn](/components/feedback/tool-btn) — 触发按钮
- [MessageTools](/components/feedback/message-tools) — 工具栏中 delete 替换入口
