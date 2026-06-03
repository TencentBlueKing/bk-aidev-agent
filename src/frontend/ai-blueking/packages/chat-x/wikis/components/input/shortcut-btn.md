---
name: ShortcutBtn 快捷指令按钮
slug: shortcut-btn
kind: component
domain: input
description: 单个快捷指令按钮，支持默认/append 插槽和 expose focus。
aiSummary: >
  单个快捷指令按钮，支持默认/append 插槽和 expose focus。
  源码位置：src/components/ai-shortcut/shortcut-btn/shortcut-btn.vue。
relatedComponents:
  - slug: shortcut-btns
    relation: 快捷指令横向列表中作为单项渲染
  - slug: ai-selection
    relation: 划词浮窗内展示快捷操作按钮或溢出菜单项
  - slug: chat-input
    relation: 已选快捷指令在输入框底部以单按钮展示
sinceVersion: 1.0.0
---

<script lang="ts" setup>
  import { h } from 'vue';
  import ShortcutBtn from '../../../src/components/ai-shortcut/shortcut-btn/shortcut-btn.vue'

  const basicShortcut = { id: 'ask-whale', name: '问问小鲸' };
  const withComponentsShortcut = { id: 'form', name: '表单填写', components: [{ id: 'c1', name: 'x' }] };
  const emptyComponentsShortcut = { id: 'empty', name: '空 components', components: [] };
  const urlIconShortcut = {
    id: 'url-icon',
    name: '图片图标',
    icon: 'https://picsum.photos/seed/shortcut/16/16',
  };
  const cssIconShortcut = { id: 'css-icon', name: 'CSS 类图标', icon: 'bk-icon icon-star-shape' };
  const funcIconShortcut = {
    id: 'func-icon',
    name: '函数图标',
    icon: (h) => h('span', { style: 'font-size:16px;line-height:1' }, '🚀'),
  };

  const menuShortcuts = [
    { id: 'translate', name: '翻译为英文' },
    { id: 'summarize', name: '摘要总结' },
    { id: 'explain', name: '解释代码' },
    { id: 'polish', name: '润色文本' },
  ];

  const handleClick = (shortcut) => {
    alert(`选择了：${shortcut?.name ?? '(无 shortcut)'}`);
  };
  const handleRemove = () => alert('移除快捷指令');
</script>

# ShortcutBtn 快捷指令按钮
## 源码事实

- **源码位置**：`src/components/ai-shortcut/shortcut-btn/shortcut-btn.vue`
- **能力域**：输入交互
- **能力说明**：单个快捷指令按钮，支持默认/append 插槽和 expose focus。



> **能力域**：输入交互

单个快捷指令的渲染单元，封装图标选择逻辑和两种布局模式（按钮 / 菜单项）。

被 `ShortcutBtns`（快捷指令栏）、`AiSelection`（划词浮窗）和 `ChatInput`（已选指令展示）内部使用，通常不需要手动引入。

## 组件结构

```
button.ai-shortcut-btn（flex，gap: 4px，height: 28px，padding: 0 4px，white-space: nowrap）
  border: none，border-radius: 4px，background: transparent
  transition: background-color 0.2s
  mode="menu" → 追加 .is-menu-mode（height: 32px，padding: 0 12px，width: 100%，justify-content: flex-start）
  │
  ├── <slot name="default">（覆盖后图标+名称全部替换）
  │     ├── [shortcut.icon 为字符串 && 以 'http' 开头]
  │     │     加载成功：<img … />；加载失败：回退 AgentIcon.ai-shortcut-btn-icon
  │     ├── [shortcut.icon 为字符串 && 不以 'http' 开头]
  │     │     <span :class="icon" />（CSS 图标类名，无其他 class）
  │     ├── [shortcut.icon 为函数或组件]
  │     │     <component :is="typeof icon==='function' ? icon(h) : icon" class="ai-shortcut-btn-icon" />
  │     ├── [shortcut 存在，无 icon，components 为空/未设置] → AgentIcon.ai-shortcut-btn-icon
  │     ├── [shortcut 存在，无 icon，components 有内容]      → 无图标
  │     └── {{ shortcut?.name }}（XSS 安全，文本插值）
  │
  └── <slot name="append" />（渲染在名称之后，常用于关闭按钮）

defineExpose: { get $el() { return el.value } }（懒 getter，返回 button 元素引用）
```

> **`hover` cursor 说明**：CSS 中 `:hover` 先写 `cursor: pointer` 再写 `cursor: default`，后者覆盖前者，实际 hover 时显示默认指针。仅 `append` 槽内的 `.ai-close-icon` 恢复 `cursor: pointer`。

## 图标渲染规则

| `shortcut.icon` 类型                  | 渲染结果                    | 额外说明                                                         |
| ------------------------------------- | --------------------------- | ---------------------------------------------------------------- |
| 未设置（且 `components` 为空/未设置） | `AgentIcon`（默认图标）     | `components: []` 与不传效果相同                                  |
| 未设置（且 `components` 有内容）      | 无图标                      | 表单类快捷指令                                                   |
| `string`，以 `'http'` 开头            | `<img>`，失败时 `AgentIcon` | `.ai-common-icon .ai-shortcut-btn-icon`；`@error` 后回退默认图标 |
| `string`，不以 `'http'` 开头          | `<span :class="icon">`      | 视为 CSS 图标类名，无其他 class                                  |
| 函数 `(h) => Component/VNode`         | `<component :is="icon(h)">` | 有 `.ai-shortcut-btn-icon`                                       |
| 组件对象                              | `<component :is="icon">`    | 有 `.ai-shortcut-btn-icon`                                       |

## 基础用法

```vue
<template>
  <ShortcutBtn
    :shortcut="shortcut"
    @click="handleClick"
  />
</template>

<script setup lang="ts">
  import { ShortcutBtn } from '@blueking/chat-x';
  import type { Shortcut } from '@blueking/chat-x';

  const shortcut: Shortcut = { id: 'ask-whale', name: '问问小鲸' };

  const handleClick = (shortcut?: Shortcut) => {
    console.log('选择了:', shortcut?.name);
  };
</script>
```

<div class="demo" style="display: flex; gap: 8px; flex-wrap: wrap; align-items: center;">
  <ShortcutBtn :shortcut="basicShortcut" @click="handleClick" />
  <ShortcutBtn :shortcut="emptyComponentsShortcut" @click="handleClick" />
  <ShortcutBtn :shortcut="withComponentsShortcut" @click="handleClick" />
</div>

> 从左到右：无 `icon`（默认 AgentIcon）、`components: []`（同样显示 AgentIcon）、有 `components`（无图标）。

## 图标类型对比

```vue
<template>
  <!-- URL 图片图标 -->
  <ShortcutBtn :shortcut="{ id: '1', name: '图片图标', icon: 'https://…/icon.png' }" />

  <!-- CSS 类名图标（字体图标） -->
  <ShortcutBtn :shortcut="{ id: '2', name: 'CSS 类图标', icon: 'bk-icon icon-star-shape' }" />

  <!-- 函数/渲染函数图标 -->
  <ShortcutBtn :shortcut="{ id: '3', name: '函数图标', icon: h => h('span', {}, '🚀') }" />
</template>
```

<div class="demo" style="display: flex; gap: 8px; flex-wrap: wrap; align-items: center;">
  <ShortcutBtn :shortcut="urlIconShortcut" @click="handleClick" />
  <ShortcutBtn :shortcut="cssIconShortcut" @click="handleClick" />
  <ShortcutBtn :shortcut="funcIconShortcut" @click="handleClick" />
</div>

## 菜单模式（mode="menu"）

`mode="menu"` 时切换为 `is-menu-mode` 布局：左对齐、`width: 100%`、高 32px、padding `0 12px`：

```vue
<template>
  <div class="shortcut-menu">
    <ShortcutBtn
      v-for="item in shortcuts"
      :key="item.id"
      mode="menu"
      :shortcut="item"
      @click="handleClick"
    />
  </div>
</template>
```

<div class="demo">
  <div style="width: 160px; padding: 4px 0; background: #fff; border-radius: 4px; box-shadow: 0 2px 8px rgba(0,0,0,.12);">
    <ShortcutBtn
      v-for="item in menuShortcuts"
      :key="item.id"
      mode="menu"
      :shortcut="item"
      @click="handleClick"
    />
  </div>
</div>

## append 插槽：添加关闭按钮

`#append` 渲染在名称之后，`@click.stop` 可阻止冒泡到 `@click`（父 ChatInput 使用场景）：

```vue
<template>
  <ShortcutBtn
    :shortcut="shortcut"
    @click="handleSelect"
  >
    <template #append>
      <CloseIcon @click.stop="handleRemove" />
    </template>
  </ShortcutBtn>
</template>
```

<div class="demo">
  <ShortcutBtn :shortcut="basicShortcut" @click="handleClick">
    <template #append>
      <span
        @click.stop="handleRemove"
        style="margin-left: 2px; font-size: 12px; color: #979ba5; cursor: pointer; line-height: 1;"
      >✕</span>
    </template>
  </ShortcutBtn>
</div>

## default 插槽：完全自定义内容

`default` 插槽覆盖**全部**默认内容（图标 + 名称），`shortcut` prop 仅传递给 `@click` 事件：

```vue
<template>
  <ShortcutBtn
    :shortcut="shortcut"
    @click="handleClick"
  >
    <MoreAgentIcon />
    <span>更多</span>
  </ShortcutBtn>
</template>
```

<div class="demo">
  <ShortcutBtn :shortcut="basicShortcut" @click="handleClick">
    <span style="font-size: 14px; line-height: 1;">⋯</span>
    <span>更多</span>
  </ShortcutBtn>
</div>

## API

### Props

| 属性名   | 类型              | 必填 | 说明                                                         |
| -------- | ----------------- | ---- | ------------------------------------------------------------ |
| shortcut | `Shortcut`        | —    | 快捷指令配置；缺省时按钮无内容，`click` 事件传递 `undefined` |
| mode     | `'btn' \| 'menu'` | —    | 布局模式；缺省为 `btn`（水平居中），`menu` 切换为列表项布局  |

### Events

| 事件名 | 参数                    | 说明                                                                 |
| ------ | ----------------------- | -------------------------------------------------------------------- |
| click  | `(shortcut?: Shortcut)` | 点击按钮时触发，传递当前 `shortcut` prop（无 prop 则为 `undefined`） |

### Slots

| 插槽名  | 说明                                                                 |
| ------- | -------------------------------------------------------------------- |
| default | 覆盖全部默认渲染（图标 + 名称）；`shortcut` prop 仍用于 `click` 事件 |
| append  | 追加在名称之后；常用于关闭/删除图标，建议配合 `@click.stop` 阻止冒泡 |

### Expose

| 属性名 | 类型                  | 说明                                                                      |
| ------ | --------------------- | ------------------------------------------------------------------------- |
| `$el`  | `HTMLElement \| null` | 懒 getter，返回根 `<button>` 元素引用；供 `ShortcutBtns` 计算可见性时使用 |

## 类型定义

```typescript
interface Shortcut {
  id: string;
  name: string;
  description?: string;
  icon?: string | Component | ((h: typeof h) => Component | VNode);
  components?: ShortcutComponent[]; // 有内容时不显示默认 AgentIcon
  formModel?: Record<string, unknown>;
}
```

## 在各组件中的使用场景

| 使用方         | 模式          | 特殊用法                                                                                     |
| -------------- | ------------- | -------------------------------------------------------------------------------------------- |
| `ShortcutBtns` | btn           | 可见项正常渲染；溢出项隐藏（CSS `visibility: hidden`），放入下拉菜单以 `mode="menu"` 展示    |
| `AiSelection`  | btn / menu    | 最多显示 `maxShortcutCount` 个按钮，超出时以 `#default` 插槽显示"更多"，下拉用 `mode="menu"` |
| `ChatInput`    | btn（已选态） | 使用 `#append` 插槽放置 `CloseIcon`，点击关闭删除已选快捷指令                                |

## 关联组件

- [ShortcutBtns](/components/input/shortcut-btns) — 快捷指令列表容器
- [AiSelection](/components/input/ai-selection) — 划词浮窗内使用
- [ChatInput](/components/input/chat-input) — 已选快捷指令展示
