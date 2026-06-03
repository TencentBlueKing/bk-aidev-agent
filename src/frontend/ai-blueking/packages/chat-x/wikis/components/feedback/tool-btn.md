---
name: ToolBtn 工具按钮
slug: tool-btn
kind: component
domain: feedback
description: 工具栏图标按钮。
aiSummary: >
  工具栏图标按钮。
  源码位置：src/components/ai-buttons/tool-btn/tool-btn.vue。
relatedComponents:
  - slug: message-tools
    relation: 父级组装多个工具按钮与交互
  - slug: delete-tool
    relation: 删除确认场景内嵌为触发控件
sinceVersion: 1.0.0
---

<script lang="ts" setup>
  import { ref } from 'vue';
  import ToolBtn from '../../../src/components/ai-buttons/tool-btn/tool-btn.vue';
  import { FullScreenIcon } from '../../../src/icons/screen';

  const activeId = ref<string | null>(null);
  const toggleActive = (data) => {
    const baseId = data.id.replace(/^active/, '').replace(/^./, c => c.toLowerCase());
    activeId.value = activeId.value === baseId ? null : baseId;
  };

  const isDisabled = ref(true);

  const handleClick = (data, event) => {
    alert(`点击了：${data.name || data.id}`);
  };
</script>

# ToolBtn 工具按钮
## 源码事实

- **源码位置**：`src/components/ai-buttons/tool-btn/tool-btn.vue`
- **能力域**：工具与反馈
- **能力说明**：工具栏图标按钮。



> **能力域**：工具与反馈

消息工具栏中的单个操作按钮，内置 SVG 图标映射、Tippy 悬浮提示、激活态与禁用态，通常由 `MessageTools` 管理，一般不需要手动使用。

## 组件结构

```
div.ai-tool-btn（v-tippy，flex，min-width: 20px，height: 20px，border-radius: 4px）
  color: #a8aab2; background: transparent
  active=true  → .is-active（color: var(--ai-tool-btn-active-color)）
  disabled=true → .is-disabled（color: #979ba5; cursor: not-allowed）
  :not(.is-disabled):hover → color: #4d4f56; background: #eaebf0
  │
  └── <slot>（默认内容，可完全自定义）
        ├── [id && id in ToolIconsMap] → <component :is="ToolIconsMap[id]" />（SVG 图标）
        └── [其他] → <div>{{ name }}</div>（文本回退，XSS 安全）

Tippy：content=description, theme='ai-chat-box', disabled=true 时 onShow 返回 false 不显示
click 事件：disabled=true 时被 JS 拦截，不触发 emit

激活色（CSS 变量 --ai-tool-btn-active-color）：
  id === 'like' 或 'activeLike' → #3a84ff（蓝色）
  其他 id（如 'unlike'、'delete'） → #E71818（红色）
```

## 预置图标（ToolIconsMap）

| id             | 说明           | 备注                     |
| -------------- | -------------- | ------------------------ |
| `copy`         | 复制           |                          |
| `cite`         | 引用           |                          |
| `rebuild`      | 重新生成       |                          |
| `share`        | 分享           |                          |
| `like`         | 点赞（空心）   | 配合 `activeLike` 使用   |
| `unlike`       | 不满意（空心） | 配合 `activeUnLike` 使用 |
| `delete`       | 删除           |                          |
| `edit`         | 编辑           |                          |
| `activeLike`   | 点赞（实心）   | 激活态填充图标           |
| `activeUnLike` | 不满意（实心） | 激活态填充图标           |

> 未传入 `id`、或 `id` 不在上表时，组件渲染 `<div>{{ name }}</div>` 作为文本回退。也可通过默认插槽完全自定义按钮内容（如全屏图标），此时可不传 `id`。

## 基础用法

```vue
<template>
  <div style="display: flex; gap: 6px;">
    <ToolBtn
      id="copy"
      name="复制"
      description="复制消息内容"
      @click="handleClick"
    />
    <ToolBtn
      id="cite"
      name="引用"
      description="引用此消息"
      @click="handleClick"
    />
    <ToolBtn
      id="rebuild"
      name="重新生成"
      description="重新生成回答"
      @click="handleClick"
    />
    <ToolBtn
      id="share"
      name="分享"
      description="分享消息"
      @click="handleClick"
    />
    <ToolBtn
      id="like"
      name="点赞"
      description="对此回答满意"
      @click="handleClick"
    />
    <ToolBtn
      id="unlike"
      name="不满意"
      description="对此回答不满意"
      @click="handleClick"
    />
    <ToolBtn
      id="edit"
      name="编辑"
      description="编辑消息"
      @click="handleClick"
    />
    <ToolBtn
      id="delete"
      name="删除"
      description="删除消息"
      @click="handleClick"
    />
  </div>
</template>

<script setup lang="ts">
  import { ToolBtn } from '@blueking/chat-x';
  import type { IToolBtn } from '@blueking/chat-x';

  const handleClick = (data: IToolBtn & { active?: boolean; disabled?: boolean }, event: MouseEvent) => {
    console.log('点击了:', data.id, data.name);
  };
</script>
```

<div class="demo">
  <div class="flex-gap-6">
    <ToolBtn id="copy"    name="复制"     description="复制消息内容"   @click="handleClick" />
    <ToolBtn id="cite"    name="引用"     description="引用此消息"     @click="handleClick" />
    <ToolBtn id="rebuild" name="重新生成" description="重新生成回答"   @click="handleClick" />
    <ToolBtn id="share"   name="分享"     description="分享消息"       @click="handleClick" />
    <ToolBtn id="like"    name="点赞"     description="对此回答满意"   @click="handleClick" />
    <ToolBtn id="unlike"  name="不满意"   description="对此回答不满意" @click="handleClick" />
    <ToolBtn id="edit"    name="编辑"     description="编辑消息"       @click="handleClick" />
    <ToolBtn id="delete"  name="删除"     description="删除消息"       @click="handleClick" />
  </div>
</div>

## 激活态与图标切换（点赞/踩）

`active` 只控制 `.is-active` 背景高亮，不自动切换图标。若需要填充图标，需在 `:id` 绑定中主动切换 `activeLike` / `activeUnLike`：

```vue
<template>
  <div style="display: flex; gap: 6px;">
    <!-- 切换 id 实现图标填充 -->
    <ToolBtn
      :id="activeId === 'like' ? 'activeLike' : 'like'"
      name="点赞"
      description="点赞"
      :active="activeId === 'like'"
      @click="toggleActive"
    />
    <ToolBtn
      :id="activeId === 'unlike' ? 'activeUnLike' : 'unlike'"
      name="不满意"
      description="不满意"
      :active="activeId === 'unlike'"
      @click="toggleActive"
    />
  </div>
</template>

<script setup lang="ts">
  import { ref } from 'vue';
  import { ToolBtn } from '@blueking/chat-x';
  import type { IToolBtn } from '@blueking/chat-x';

  const activeId = ref<string | null>(null);

  const toggleActive = (data: IToolBtn) => {
    // 规范化 id（activeLike → like）后再比较
    const baseId = data.id.replace(/^active/, '').replace(/^./, c => c.toLowerCase());
    activeId.value = activeId.value === baseId ? null : baseId;
  };
</script>
```

<div class="demo">
  <div class="flex-gap-6">
    <ToolBtn
      :id="activeId === 'like' ? 'activeLike' : 'like'"
      name="点赞"
      description="点赞"
      :active="activeId === 'like'"
      @click="toggleActive"
    />
    <ToolBtn
      :id="activeId === 'unlike' ? 'activeUnLike' : 'unlike'"
      name="不满意"
      description="不满意"
      :active="activeId === 'unlike'"
      @click="toggleActive"
    />
  </div>
  <p style="margin-top: 8px; font-size: 12px; color: #979ba5;">点击切换：active 时背景高亮 + 图标变为填充版本</p>
</div>

## 禁用状态

`disabled=true` 时：JS 拦截 click 不触发事件 + Tippy 的 `onShow` 返回 `false` 不显示 tooltip：

```vue
<template>
  <div style="display: flex; gap: 6px; align-items: center;">
    <ToolBtn
      id="copy"
      name="复制"
      description="复制"
      :disabled="isDisabled"
      @click="handleClick"
    />
    <ToolBtn
      id="edit"
      name="编辑"
      description="编辑"
      :disabled="isDisabled"
      @click="handleClick"
    />
    <button @click="isDisabled = !isDisabled">{{ isDisabled ? '启用' : '禁用' }}</button>
  </div>
</template>
```

<div class="demo">
  <div class="flex-gap-6" style="align-items: center;">
    <ToolBtn id="copy" name="复制" description="复制" :disabled="isDisabled" @click="handleClick" />
    <ToolBtn id="edit" name="编辑" description="编辑" :disabled="isDisabled" @click="handleClick" />
    <button
      @click="isDisabled = !isDisabled"
      style="padding: 2px 10px; font-size: 12px; border: 1px solid #dcdee5; border-radius: 4px; cursor: pointer; background: #fff;"
    >
      {{ isDisabled ? '启用' : '禁用' }}
    </button>
  </div>
</div>

## 未知 ID 的文本回退

`id` 不在 `ToolIconsMap` 时渲染 `name` 文本，适用于自定义扩展场景：

<div class="demo">
  <div class="flex-gap-6">
    <ToolBtn id="custom" name="摘要" description="生成摘要" @click="handleClick" />
    <ToolBtn id="export" name="导出" description="导出内容" @click="handleClick" />
  </div>
</div>

## 自定义插槽内容

通过默认插槽可完全替换内置图标/文本，适用于预置 `ToolIconsMap` 未覆盖的图标场景（如侧栏全屏按钮）：

```vue
<template>
  <ToolBtn
    description="全屏"
    :tippy-options="{ content: '全屏' }"
    @click="handleFullScreen"
  >
    <FullScreenIcon />
  </ToolBtn>
</template>

<script setup lang="ts">
  import { ToolBtn, FullScreenIcon } from '@blueking/chat-x';

  const handleFullScreen = () => {
    // 进入全屏逻辑
  };
</script>
```

<div class="demo">
  <ToolBtn description="全屏" :tippy-options="{ content: '全屏' }" @click="handleClick">
    <FullScreenIcon />
  </ToolBtn>
</div>

## API

### Props

| 属性名       | 类型                                                                       | 必填 | 默认值 | 说明                                                                                                               |
| ------------ | -------------------------------------------------------------------------- | ---- | ------ | ------------------------------------------------------------------------------------------------------------------ |
| id           | `keyof typeof ToolIconsMap`                                                | 否   | —      | 按钮标识；在 `ToolIconsMap` 中时渲染对应 SVG 图标，否则渲染 `name` 文本；使用插槽自定义内容时可省略                  |
| name         | `string`                                                                   | 否   | —      | 按钮名称；`id` 无对应图标时作为文本内容渲染                                                                        |
| description  | `string`                                                                   | 否   | —      | Tippy tooltip 内容；`disabled=true` 时不显示 tooltip                                                               |
| active       | `boolean`                                                                  | 否   | —      | 激活态；`true` 时追加 `.is-active`（字色由 `id` 决定：`like`/`activeLike` 为蓝色 `#3a84ff`，其他为红色 `#E71818`） |
| disabled     | `boolean`                                                                  | 否   | —      | 禁用态；`true` 时追加 `.is-disabled`，阻止 click 事件，隐藏 tooltip                                                |
| tippyOptions | `Partial<Omit<TippyOptions, 'getReferenceClientRect' \| 'triggerTarget'>>` | 否   | —      | 自定义 Tippy 配置，与内部默认配置合并；可用于控制 `content`、`appendTo`、`placement` 等                            |

### Events

| 事件名 | 参数                                                                             | 说明                                                                                        |
| ------ | -------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------- |
| click  | `(data: IToolBtn & { active?: boolean; disabled?: boolean }, event: MouseEvent)` | 点击时触发；`data` 为组件当前全量 props（含 `active`/`disabled`）；`disabled=true` 时不触发 |

### Slots

| 插槽名  | 说明                                                                                       |
| ------- | ------------------------------------------------------------------------------------------ |
| default | 按钮内容；传入时替换默认的图标/文本渲染逻辑，常用于自定义 SVG 图标（如全屏、退出全屏按钮） |

## 类型定义

```typescript
// 来自 @blueking/chat-x 导出
interface IToolBtn {
  id?: keyof typeof ToolIconsMap; // 预置 ID；省略时走 name 文本或插槽
  name?: string;
  description?: string;
}

// ToolBtn 完整 Props
type ToolBtnProps = IToolBtn & {
  active?: boolean;
  disabled?: boolean;
  tippyOptions?: Partial<Omit<TippyOptions, 'getReferenceClientRect' | 'triggerTarget'>>;
};

// 预置 ID 枚举
type ToolIcons =
  | 'copy'
  | 'cite'
  | 'rebuild'
  | 'share'
  | 'like'
  | 'unlike'
  | 'delete'
  | 'edit'
  | 'activeLike'
  | 'activeUnLike';
```

## 注意事项

1. **`click` 事件的 `data` 参数**是组件的完整 props 对象（含 `active`、`disabled`），并非单纯的 `IToolBtn`
2. **`activeLike` / `activeUnLike`**：是单独的填充版图标 ID，并非 `active=true` 时自动切换，需要手动在 `:id` 绑定中控制
3. **根元素是 `<div>` 而非 `<button>`**：没有原生按钮语义，键盘无障碍访问需外部额外处理
4. **`description` 可选**：不传时 tooltip 内容为 `undefined`，Tippy 不显示提示
5. **`disabled` 的 CSS**：`pointer-events: hover` 为无效 CSS 值（应为 `none`），鼠标事件实际由 JS 层拦截，CSS 层仍可触发 hover 样式
6. **`tippyOptions` 优先级**：`tippyOptions` 中的配置会覆盖内部默认值（包括 `content`、`theme`），但 `onShow` 始终保留内部逻辑（禁用时不显示）。`getReferenceClientRect`、`triggerTarget` 两个字段被 Omit 排除，不可通过此 prop 覆盖；`content` 已可通过 `tippyOptions.content` 覆盖

## 关联组件

- [MessageTools](/components/feedback/message-tools) — 工具栏容器
- [DeleteTool](/components/feedback/delete-tool) — 删除确认内嵌触发
