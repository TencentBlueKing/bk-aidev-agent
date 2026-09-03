# ModelSelector 模型选择器

> 能力域：输入交互 ｜ 导入：`import { ModelSelector } from '@blueking/chat-x'` ｜ since 1.0.0

聊天输入区的模型下拉选择器，支持搜索过滤、能力标签与键盘导航。 源码位置：src/components/chat-input/model-selector/model-selector.vue。

**关联**：chat-input（传入 models 后在发送按钮左侧默认渲染）、input-attachment（通过 before-send 插槽与发送按钮成组布局）

---

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

选中值为模型的 `llm_name`；能力标签由组件依据 `property`（`support_thinking` / `support_thinking_quick` / `support_vision`）自动派生，无需调用方传入。

```vue
<template>
  <ModelSelector
    v-model="selectedModel"
    :models="models"
    @change="handleModelChange"
  />
</template>

<script setup lang="ts">
  import { ref } from 'vue';
  import { ModelSelector, type IModelOption } from '@blueking/chat-x';

  // 选中值为 llm_name
  const selectedModel = ref('DeepSeek-V4-Pro-Online-32k');
  const models: IModelOption[] = [
    {
      id: 119,
      llm_code: 'DeepSeek-V4-Pro-Online-32k',
      llm_name: 'DeepSeek-V4-Pro-Online-32k',
      llm_type: 'chat.completion',
      space_auth_mode: 'APPLY',
      user_auth_mode: 'PUBLIC',
      max_token_size: 4096,
      icon: 'https://example.com/deepseek.png',
      description: 'DeepSeek-V4-Pro 旗舰版本，支持超长上下文与复杂任务处理',
      base_model: 'deepseek',
      tag_names: [],
      // support_thinking → 深度思考、support_vision → 图生文
      property: { support_thinking: true, support_vision: true, max_model_len: 32000 },
    },
  ];

  const handleModelChange = (model: IModelOption) => {
    console.log('选中模型:', model);
  };
</script>
```

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

| 属性名 | 类型     | 说明                          |
| ------ | -------- | ----------------------------- |
| —      | `string` | 当前选中模型的 `llm_name` 值 |

### Events

| 事件名 | 参数                    | 说明                 |
| ------ | ----------------------- | -------------------- |
| change | `(model: IModelOption)` | 用户选中模型时触发   |

## 类型定义

```typescript
import type { IModelCapability, IModelOption, IModelProperty, ModelCapabilityTheme } from '@blueking/chat-x';

type ModelCapabilityTheme = 'default' | 'primary' | 'success' | 'warning';

// 能力标签由组件依据 property 派生（文案走内置 i18n）
interface IModelCapability {
  theme?: ModelCapabilityTheme;
  text: string;
}

// 模型能力属性，决定派生出的能力标签
interface IModelProperty {
  agent_type?: string;
  default?: boolean;
  is_self_host?: boolean;
  max_model_len?: number;
  support_summary?: boolean;
  support_thinking?: boolean; // → 深度思考
  support_thinking_quick?: boolean; // → 快速思考
  support_tools?: boolean;
  support_vision?: boolean; // → 图生文
  support_window?: boolean;
}

// 模型选项，贴合后端模型接口结构
interface IModelOption {
  base_model?: string;
  description?: string; // 选项 hover 的 title 提示
  disabled?: boolean; // 前端扩展字段，禁用项不可选中
  icon?: Component | string; // 图标 URL 或 Vue 组件，由 ResourceIcon 渲染
  id: number;
  llm_code: string;
  llm_name: string; // 展示名，同时作为选中值
  llm_type: string;
  max_token_size: number;
  property: IModelProperty;
  space_auth_mode: string;
  tag_names?: string[];
  user_auth_mode: string;
}
```

## 注意事项

1. `models` 为空或 `disabled` 为 `true` 时，下拉不会展开。
2. 选中值为模型的 `llm_name`；能力标签由组件依据 `property` 的 `support_thinking` / `support_thinking_quick` / `support_vision` 派生，文案走内置 i18n。
3. `description` 会作为选项 hover 的 `title` 提示展示。
4. 展开面板后会自动聚焦搜索框；列表支持键盘上下选择与 Enter 确认（复用 `useMenuKeydown`）。
5. 图标由 [ResourceIcon](/components/helper/resource-icon) 渲染（`type="model"`）：支持图片 URL 或 Vue 组件，URL 加载失败自动回退到内置兜底图标；未提供 `icon` 时不渲染图标位。

## 关联组件

- [ChatInput](/components/input/chat-input)：传入 `models` 后默认在发送按钮左侧渲染本组件，也可通过 `#model-selector` 插槽完全自定义。
- [ChatContainer](/components/setup/chat-container)：透传 `models` 与 `v-model:selected-model`，并向上 emit `modelChange`。
- [ResourceIcon](/components/helper/resource-icon)：触发器与选项的图标渲染。
