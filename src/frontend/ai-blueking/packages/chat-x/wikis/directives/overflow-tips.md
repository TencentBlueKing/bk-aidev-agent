---
name: OverflowTips
slug: overflow-tips
category: directive
description: >-
  当元素文本**水平溢出**（`scrollWidth > clientWidth`）时，鼠标悬停自动弹出 Tippy tooltip
  显示完整内容；未溢出时不创建实例，零性能损耗。
aiSummary: >
  v-overflow-tips 在元素水平溢出（scrollWidth > clientWidth）时于 mouseenter 懒创建 Tippy，展示完整文本或自定义 text/content。
  结合 IntersectionObserver 仅在可见时绑定悬停；隐藏时销毁实例。指令值为 Partial<TippyProps> 与 disabled 等。
  DescPanel、ExecutionSummary、ToolcallRender、AiSlashMenu 等用于标题或列表溢出提示。
relatedComponents:
  - slug: desc-panel
    relation: 工具描述面板溢出
  - slug: execution-summary
    relation: 执行摘要标签溢出
  - slug: toolcall-render
    relation: 工具标题行溢出
  - slug: chat-input
    relation: AiSlashMenu 资源项（侧栏子模块）
sinceVersion: 1.0.0
---

# OverflowTips 溢出提示指令

> **分类**：directive

<script setup lang="ts">
import { ref } from 'vue';
import { OverflowTips as vOverflowTips } from '@blueking/chat-x';

const longTexts = [
  '这是一段很长的文本内容，会触发溢出省略效果并弹出 tooltip 提示完整内容',
  '短文本',
  '蓝鲸智云 AI 小鲸组件库 @blueking/chat-x 提供完整的聊天界面解决方案',
];

const customText = '自定义 tooltip 内容：完整的蓝鲸智云 AI 小鲸组件使用说明';
const placement = ref<'top' | 'bottom' | 'left' | 'right'>('top');
const disabled = ref(false);
</script>

当元素文本**水平溢出**（`scrollWidth > clientWidth`）时，鼠标悬停自动弹出 Tippy tooltip 显示完整内容；未溢出时不创建实例，零性能损耗。

## 工作原理

```
元素挂载
   │
   ▼
IntersectionObserver 监听可见性（threshold=0.1）
   │
   ├─ 可见 → 绑定 mouseenter / mouseleave
   └─ 不可见 → 解绑 mouseenter / mouseleave
                    │
                    ▼ mouseenter 触发
              scrollWidth > clientWidth ?
               │               │
              否               是
               │               │
            直接返回      创建 Tippy 实例
                          [trigger: mouseenter]
                          [delay: 300ms, 0ms]
                               │
                    ┌──────────┴──────────┐
                  onShow              onHidden
              再次校验溢出         destroy() 销毁实例
              false → 取消          instance = undefined
```

## 基础用法

文本未溢出时不会弹出 tooltip；只有超出容器宽度才触发。元素需自行设置省略号 CSS。

<div class="demo">
  <div style="display: flex; flex-direction: column; gap: 12px; padding: 16px;">
    <div
      v-for="text in longTexts"
      :key="text"
      v-overflow-tips
      style="width: 240px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; padding: 6px 10px; background: #f5f7fa; border-radius: 4px; cursor: default;"
    >{{ text }}</div>
  </div>
</div>

```vue
<template>
  <div
    v-overflow-tips
    class="ellipsis"
  >
    这是一段很长的文本内容，会触发溢出省略效果并弹出 tooltip 提示完整内容
  </div>
</template>

<script setup lang="ts">
  import { OverflowTips as vOverflowTips } from '@blueking/chat-x';
</script>

<style scoped>
  .ellipsis {
    width: 240px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
</style>
```

## 自定义提示内容

通过 `text` 或 `content`（别名）指定 tooltip 显示内容，优先级：`text > content > el.innerText`。

<div class="demo">
  <div style="padding: 16px;">
    <div
      v-overflow-tips="{ text: customText }"
      style="width: 240px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; padding: 6px 10px; background: #f5f7fa; border-radius: 4px; cursor: default;"
    >悬浮查看自定义 tooltip 内容（与元素 innerText 不同）</div>
  </div>
</div>

```vue
<template>
  <div
    v-overflow-tips="{ text: '自定义 tooltip 内容：完整的蓝鲸智云 AI 小鲸组件使用说明' }"
    class="ellipsis"
  >
    悬浮查看自定义 tooltip 内容（与元素 innerText 不同）
  </div>
</template>

<script setup lang="ts">
  import { OverflowTips as vOverflowTips } from '@blueking/chat-x';
</script>
```

## 控制 placement 和禁用

`placement` 默认 `'auto'`（Tippy 自动选择最优方向）；`disabled: true` 完全跳过 tooltip 创建。

<div class="demo">
  <div style="padding: 16px; display: flex; flex-direction: column; gap: 12px;">
    <div style="display: flex; gap: 8px; align-items: center;">
      <span>弹出方向：</span>
      <select v-model="placement" style="padding: 2px 6px; border: 1px solid #dcdee5; border-radius: 4px;">
        <option value="top">top</option>
        <option value="bottom">bottom</option>
        <option value="left">left</option>
        <option value="right">right</option>
      </select>
      <span style="margin-left: 12px;">禁用：</span>
      <input type="checkbox" v-model="disabled" />
    </div>
    <div
      v-overflow-tips="{ placement, disabled }"
      style="width: 240px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; padding: 6px 10px; background: #f5f7fa; border-radius: 4px; cursor: default;"
    >这是一段很长的文本内容，可以切换弹出方向或禁用 tooltip</div>
  </div>
</div>

```vue
<template>
  <div
    v-overflow-tips="{ placement: 'bottom', disabled: isDisabled }"
    class="ellipsis"
  >
    可以切换弹出方向或禁用 tooltip
  </div>
</template>

<script setup lang="ts">
  import { ref } from 'vue';
  import { OverflowTips as vOverflowTips } from '@blueking/chat-x';

  const isDisabled = ref(false);
</script>
```

## API

### 指令值类型

```typescript
type OverflowTipsValue = Partial<TippyProps> & {
  disabled?: boolean; // 禁用 tooltip
  text?: string; // 自定义提示内容（优先级最高）
  content?: string; // text 的别名
};
```

指令值是 `Partial<TippyProps>` 的超集，所有 Tippy.js 配置均可透传，但覆盖 `onHidden` 会导致实例无法自动销毁。

### 常用配置项

| 属性        | 类型                         | 默认值          | 说明                                            |
| ----------- | ---------------------------- | --------------- | ----------------------------------------------- |
| `text`      | `string`                     | `el.innerText`  | 自定义提示内容，优先级最高                      |
| `content`   | `string`                     | `el.innerText`  | `text` 的别名，`text` 存在时忽略                |
| `placement` | `Placement`                  | `'auto'`        | tooltip 弹出方向，支持所有 Tippy placement 值   |
| `disabled`  | `boolean`                    | `false`         | `true` 时跳过 tooltip 创建，mouseenter 直接返回 |
| `delay`     | `number \| [number, number]` | `[300, 0]`      | 显示/隐藏延迟（ms）                             |
| `theme`     | `string`                     | `'ai-chat-box'` | Tippy 主题，默认使用组件库内置主题              |

### 其他 Tippy.js 配置

可直接传入任何 `tippy.js` 的 `Props`，如 `arrow`、`maxWidth`、`offset` 等，会覆盖上述默认值（除内部的 `trigger`、`onShow`、`onHidden` 逻辑外）。

> **注意**：不要覆盖 `onHidden`，否则 Tippy 实例无法在隐藏后自动销毁，导致内存泄漏。

## 溢出检测规则

指令通过 `scrollWidth > clientWidth` 判断**水平溢出**：

- 仅检测水平方向，多行文本的垂直截断（`-webkit-line-clamp`）无法被检测到
- `onShow` 会在 tooltip 即将显示时**再次校验**溢出状态，动态缩放容器后同样有效
- 若两次校验均未溢出，tooltip 不会弹出

## 生命周期细节

| 时机                | 行为                                                                  |
| ------------------- | --------------------------------------------------------------------- |
| `mounted`           | 创建 `IntersectionObserver`（阈值 10%），注册 `unObserverFunc` 到元素 |
| 元素进入视口        | 绑定 `mouseenter` / `mouseleave` 事件                                 |
| 元素离开视口        | 解绑 `mouseenter` / `mouseleave`                                      |
| `mouseenter` + 溢出 | 创建 Tippy 实例；`DelayMs+16ms` 后补偿首次不显示的 bug                |
| `onHidden`          | 销毁实例（`destroy()`），`instance = undefined`                       |
| `beforeUnmount`     | 解绑所有事件，调用 `unObserverFunc` 停止 Observer                     |

> **无 `update` 钩子**：`binding.value` 在运行时变化（如 `disabled` 切换）不会更新已创建的 Tippy 实例，只影响下一次 `mouseenter` 时的行为。

## 样式要求

指令不会自动设置省略号 CSS，需在元素上手动添加：

**单行截断**：

```css
.ellipsis {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
```

**多行截断（`-webkit-line-clamp`）**：

```css
/* 注意：多行截断时 scrollWidth <= clientWidth，tooltip 不会触发 */
.ellipsis-multiline {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
```

> 多行截断通过 `-webkit-line-clamp` 实现，`scrollWidth` 不变，指令**无法检测**此类溢出，tooltip 不会弹出。

## 注意事项

1. **仅检测水平溢出**：`scrollWidth > clientWidth`，多行 `line-clamp` 溢出无效
2. **无 `update` 钩子**：`disabled` 等状态变化仅在下次 `mouseenter` 生效
3. **勿覆盖 `onHidden`**：会导致 Tippy 实例无法自动销毁
4. **默认主题**：`'ai-chat-box'` 是组件库内置主题，替换为其他主题需引入对应 CSS
5. **事件冒泡**：`mouseenter` 内调用了 `stopPropagation()`，父元素不会收到该事件

## 关联组件

- [DescPanel](../components/atomic/desc-panel.md) — 描述区溢出
- [ExecutionSummary](../components/molecular/execution-summary.md) — 侧栏摘要标签
- [ToolcallRender](../components/molecular/toolcall-render.md) — 工具调用标题
- [ChatInput](../components/molecular/chat-input.md) — `@` 菜单项（内部 AiSlashMenu）
