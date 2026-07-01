---
name: ModelSelector 模型选择器
slug: model-selector
kind: component
domain: input
description: 聊天输入区的模型下拉选择器，支持搜索过滤、能力标签与键盘导航。
aiSummary: >
  聊天输入区的模型下拉选择器，支持搜索过滤、能力标签与键盘导航。
  源码位置：src/components/chat-input/model-selector/model-selector.vue。
relatedComponents:
  - slug: chat-input
    relation: 传入 models 后在发送按钮左侧默认渲染
  - slug: input-attachment
    relation: 通过 before-send 插槽与发送按钮成组布局
sinceVersion: 1.0.0
---

<script lang="ts" setup>
  import { ref } from 'vue'
  import ModelSelectorComp from '../../../src/components/chat-input/model-selector/model-selector.vue'

  const selectedModelId = ref('gpt-4')
  const models = [
    { id: 'gpt-4', name: 'GPT-4', capabilities: [{ text: '深度思考', theme: 'primary' }] },
    { id: 'claude', name: 'Claude 3', capabilities: [{ text: '快速思考', theme: 'success' }] },
    { id: 'deepseek', name: 'DeepSeek', capabilities: [{ text: '图生文', theme: 'warning' }] },
  ]

  const handleModelChange = (model) => {
    console.log('选中模型:', model)
  }
</script>

# ModelSelector 模型选择器

## 源码事实

- **源码位置**：`src/components/chat-input/model-selector/model-selector.vue`
- **能力域**：输入交互
- **能力说明**：基于 Tippy 下拉的模型选择器，包含触发器、搜索面板与能力标签展示；数据过滤逻辑由 `useModelSelector` composable 承担。

> **能力域**：输入交互

可在 [ChatInput](/components/input/chat-input) 传入 `models` 后自动出现在发送按钮左侧，也可单独使用。

## 组件结构

```
ModelSelector（Tippy 容器，theme: ai-model-selector）
├── ModelSelectorTrigger（触发器：图标 + 名称 + 箭头）
└── ModelSelectorPanel（下拉面板）
    ├── 搜索框（展开后自动聚焦）
    └── 模型列表（支持键盘导航、选中态、禁用态、能力标签）
```

## 基础用法

```vue
<template>
  <ModelSelector
    v-model="selectedModelId"
    :models="models"
    @change="handleModelChange"
  />
</template>

<script setup lang="ts">
  import { ref } from 'vue';
  import { ModelSelector, type IModelOption } from '@blueking/chat-x';

  const selectedModelId = ref('gpt-4');
  const models: IModelOption[] = [
    { id: 'gpt-4', name: 'GPT-4', capabilities: [{ text: '深度思考', theme: 'primary' }] },
    { id: 'claude', name: 'Claude 3' },
  ];

  const handleModelChange = (model: IModelOption) => {
    console.log('选中模型:', model);
  };
</script>
```

<div class="demo">
  <ModelSelectorComp
    v-model="selectedModelId"
    :models="models"
    @change="handleModelChange"
  />
</div>

## API

### Props

| 属性名            | 类型                                                                       | 默认值           | 说明                                   |
| ----------------- | -------------------------------------------------------------------------- | ---------------- | -------------------------------------- |
| disabled          | `boolean`                                                                  | `false`          | 是否禁用整个选择器                     |
| models            | `IModelOption[]`                                                           | `[]`             | 可选模型列表                           |
| placeholder       | `string`                                                                   | `选择模型`       | trigger 无选中时的占位文案             |
| searchPlaceholder | `string`                                                                   | `搜索模型关键字` | 搜索框占位文案                         |
| tippyOptions      | `Partial<Omit<TippyOptions, 'getReferenceClientRect' \| 'triggerTarget'>>` | —                | 透传给 Tippy 的额外配置                |

### v-model

| 属性名 | 类型     | 说明               |
| ------ | -------- | ------------------ |
| —      | `string` | 当前选中的模型 id |

### Events

| 事件名 | 参数                    | 说明                 |
| ------ | ----------------------- | -------------------- |
| change | `(model: IModelOption)` | 用户选中模型时触发   |

## 类型定义

```typescript
import type { IModelCapability, IModelOption, ModelCapabilityTheme } from '@blueking/chat-x';

type ModelCapabilityTheme = 'default' | 'primary' | 'success' | 'warning';

interface IModelCapability {
  theme?: ModelCapabilityTheme;
  text: string;
}

interface IModelOption {
  capabilities?: IModelCapability[];
  disabled?: boolean;
  icon?: Component | string;
  id: string;
  name: string;
}
```

## 注意事项

1. `models` 为空或 `disabled` 为 `true` 时，下拉不会展开。
2. 能力标签文案由调用方提供，不走内置 i18n。
3. 展开面板后会自动聚焦搜索框；列表支持键盘上下选择与 Enter 确认（复用 `useMenuKeydown`）。

## 关联组件

- [ChatInput](/components/input/chat-input)：传入 `models` 后默认在发送按钮左侧渲染本组件，也可通过 `#model-selector` 插槽完全自定义。
- [ChatContainer](/components/setup/chat-container)：透传 `models` 与 `v-model:selected-model-id`，并向上 emit `modelChange`。
