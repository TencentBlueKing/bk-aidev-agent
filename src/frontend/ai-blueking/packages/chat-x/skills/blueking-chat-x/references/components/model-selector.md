# ModelSelector 模型选择器

> 能力域：输入交互 ｜ 导入：`import { ModelSelector } from '@blueking/chat-x'` ｜ since 1.0.0

聊天输入区的模型下拉选择器，支持搜索过滤、能力标签与键盘导航。 选项 hover 时弹出描述卡片（模型名 + 描述），模型带 property.reasoning 时卡片底部可调思考深度， 通过 v-model:reasoningEffort 与 reasoningEffortChange 交给接入方写入会话。 源码位置：src/components/chat-input/model-selector/model-selector.vue。

**关联**：chat-input（传入 models 后在发送按钮左侧默认渲染）、input-attachment（通过 before-send 插槽与发送按钮成组布局）

---

# ModelSelector 模型选择器

## 源码事实

- **源码位置**：`src/components/chat-input/model-selector/model-selector.vue`
- **能力域**：输入交互
- **能力说明**：基于 Tippy 下拉的模型选择器，包含触发器、搜索面板、能力标签，以及 hover 描述卡片（含思考深度滑块）；数据过滤逻辑由 `useModelSelector` composable 承担。

> **能力域**：输入交互

可在 [ChatInput](/components/input/chat-input) 传入 `models` 后自动出现在发送按钮左侧，也可单独使用。

## 组件结构

```
ModelSelector（Tippy 容器，theme: ai-model-selector）
├── ModelSelectorTrigger（触发器：图标 + 名称 + 思考深度档位 + 箭头）
└── ModelSelectorPanel（下拉面板）
    ├── 搜索框（展开后自动聚焦）
    ├── 模型列表（支持键盘导航、选中态、禁用态、能力标签；名称后回显思考深度档位）
    └── ModelDescriptionCard（hover 描述卡片，整表共用一个）
        └── ReasoningEffortSlider（思考深度分段滑块，模型支持时展示）
```

## 基础用法

选中值为模型的 `llm_name`；能力标签由组件依据 `property`（`support_thinking` / `support_thinking_quick` / `support_vision`）自动派生，无需调用方传入。示例里带了 `description` 的模型，悬停该选项约 300ms 后会看到描述卡片。

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

## 思考深度

模型的 `property.reasoning` 带 `supported_efforts` 时，hover 描述卡片底部会出现「思考深度」分段滑块，档位顺序即数组顺序，可点击或拖动切换（滑块聚焦后也支持 ← / → / Home / End）。按下、以及拖动跨过新档位时会立刻选中该档，与点击相同，松手不再重复触发。悬停或拖动经过某一档时，在该档交界上方显示档位名称；用 ← / → / Home / End 调档时，气泡跟随滑块。选中的档位通过 `v-model:reasoning-effort` 双向绑定，值为档位 `key`；未绑定或为空时按模型的 `default_effort` 展示。触发器和当前模型选项的名称后会显示档位文案（如「Hy3 hunyuan 中」），档位为 `none` 时不显示。

组件只负责展示和交互，不发请求。接入方在 `reasoningEffortChange` 里把档位写入会话（如 `reasoning_effort`）。拖动会按经过的档位连续触发，写入会话前建议自行防抖。切换模型时组件会把 `reasoningEffort` 清空，界面回到新模型的默认档位，接入方可按需再写回会话中的实际值。

```vue
<template>
  <ModelSelector
    v-model="selectedModel"
    v-model:reasoning-effort="reasoningEffort"
    :models="models"
    @reasoning-effort-change="handleReasoningEffortChange"
  />
</template>

<script setup lang="ts">
  import { ref } from 'vue';
  import { ModelSelector, type IModelOption, type ReasoningEffort } from '@blueking/chat-x';

  const selectedModel = ref('Hy3 hunyuan');
  // 一般取会话的 effective_reasoning_effort；为空时展示模型的 default_effort
  const reasoningEffort = ref<null | ReasoningEffort>();
  const models: IModelOption[] = [
    {
      id: 11,
      llm_code: 'hy3',
      llm_name: 'Hy3 hunyuan',
      llm_type: 'chat.completion',
      space_auth_mode: 'APPLY',
      user_auth_mode: 'PUBLIC',
      max_token_size: 4096,
      description: '混元 Hy3 模型，支持视觉理解与深度思考',
      property: {
        support_vision: true,
        reasoning: {
          supported_efforts: [
            { key: 'none', value: '关闭', desc: '不思考，直接回答' },
            { key: 'low', value: '低', desc: '简单思考，响应较快' },
            { key: 'medium', value: '中', desc: '兼顾思考深度与响应速度' },
            { key: 'high', value: '高', desc: '深入思考，回答更周全' },
          ],
          default_effort: 'medium',
          mandatory: false,
        },
      },
    },
  ];

  const handleReasoningEffortChange = (model: IModelOption, effort: ReasoningEffort) => {
    // 在这里调用会话接口写入思考深度
    console.log('思考深度:', model.llm_name, effort);
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
| tippyOptions      | `Partial<Omit<TippyOptions, 'getReferenceClientRect' \| 'triggerTarget'>>` | —                | 传给下拉 Tippy 的额外配置，`placement` 可覆盖下拉默认的 `bottom-end`。描述卡片只复用其中的 `appendTo`、`placement`、`zIndex` |

### v-model

| 属性名          | 类型                      | 说明                                                                 |
| --------------- | ------------------------- | -------------------------------------------------------------------- |
| —               | `string`                  | 当前选中模型的 `llm_name` 值                                         |
| reasoningEffort | `null \| ReasoningEffort` | 当前模型的思考深度档位 `key`；为空时按模型 `default_effort` 展示，切换模型时组件会清空 |

### Events

| 事件名                | 参数                                             | 说明                                                       |
| --------------------- | ------------------------------------------------ | ---------------------------------------------------------- |
| change                | `(model: IModelOption)`                          | 用户选中模型时触发                                         |
| reasoningEffortChange | `(model: IModelOption, effort: ReasoningEffort)` | 用户在描述卡片里改了思考深度时触发（拖动跨档会按经过的档位各触发一次）。接入方据此写入会话，连续触发时建议自行防抖 |
| show                  | —                                                | 下拉展开时触发（ChatInput 用来收起输入框菜单）             |

## 类型定义

```typescript
import type {
  IModelCapability,
  IModelOption,
  IModelProperty,
  IModelReasoning,
  IReasoningEffortOption,
  ModelCapabilityTheme,
  ReasoningEffort,
} from '@blueking/chat-x';

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
  reasoning?: IModelReasoning | null; // 思考深度配置，null 或缺省表示不支持
  support_summary?: boolean;
  support_thinking?: boolean; // → 深度思考
  support_thinking_quick?: boolean; // → 快速思考
  support_tools?: boolean;
  support_vision?: boolean; // → 图生文
  support_window?: boolean;
}

// 思考深度档位 key
type ReasoningEffort = 'high' | 'low' | 'max' | 'medium' | 'minimal' | 'none' | 'xhigh';

// 单个思考深度档位
interface IReasoningEffortOption {
  desc?: string; // 档位说明，滑块右侧档位文案的原生 title
  key: ReasoningEffort;
  value: string; // 档位展示文案
}

// 模型的思考深度配置
interface IModelReasoning {
  default_effort?: ReasoningEffort; // 未选择时展示的默认档位
  mandatory?: boolean; // 是否必须思考，组件暂不消费
  supported_efforts: IReasoningEffortOption[]; // 档位列表，按顺序排成滑块
}

// 模型选项，贴合后端模型接口结构
interface IModelOption {
  base_model?: string;
  description?: string; // 去空白后非空，或模型支持思考深度时，选项 hover 展示描述卡片；否则名称用原生 title 提示全名
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
2. 下拉默认在触发器下方展开，右边缘对齐（`placement: 'bottom-end'`）；下方空间不足时自动翻转到上方。可通过 `tippyOptions.placement` 指定方向，经 `ChatContainer` 使用时来自 `commonTippyOptions.placement`。
3. 选中值为模型的 `llm_name`；能力标签由组件依据 `property` 的 `support_thinking` / `support_thinking_quick` / `support_vision` 派生，文案走内置 i18n。
4. `description` 去掉首尾空白后有内容，或模型带 `property.reasoning.supported_efforts` 时，鼠标停在选项上约 300ms 后弹出白底描述卡片：标题为模型名，正文为纯文本描述（不解析 HTML，最多 3 行，超出省略；无描述显示 `--`）。卡片可交互，鼠标从选项移入卡片不会关闭；离开选项和卡片约 100ms 后关闭，列表滚动、搜索替换列表、下拉收起时立即关闭。同一列表同时只有一张卡片。两者都没有时不展示卡片，名称用原生 `title` 显示全名。禁用项同样展示卡片，但滑块不可操作。
5. 描述卡片默认 `appendTo` 为 `document.body`、`placement` 为 `auto`、`zIndex` 为 `EDITOR_MENU_Z_INDEX`（10001）。`tippyOptions` 的这三项会覆盖默认值，并与下拉共用；经 `ChatContainer` 使用时它们来自 `commonTippyOptions`（全屏会把 `appendTo` 改到全屏容器）。`trigger`、主题等其余字段只作用于下拉。
6. 思考深度：滑块分段数为档位数减 1，第 i 档时前 i 段高亮、滑块中心落在第 i 个分段交界（首末档贴住轨道两端），点击或拖动时吸附到离指针最近的交界；按下以及拖动跨档都会立刻选中该档（同一档不重复触发）。悬停或拖动经过某一档时，在该交界上方显示档位名称，移出轨道后消失；键盘调档时气泡跟随滑块，失焦后消失。只有一个档位时显示为整条且不可操作；右侧档位文案悬停时用原生 `title` 展示 `desc`。在非当前模型的卡片上改档位，会先选中该模型（触发 `change`），再写入档位（触发 `reasoningEffortChange`），下拉保持展开。拖动中鼠标移出卡片不会关闭，松开后才按鼠标位置判断。`mandatory` 由服务端配置档位列表时体现（如不提供 `none`），组件不额外处理。
7. 展开面板后会自动聚焦搜索框；列表支持键盘上下选择与 Enter 确认（复用 `useMenuKeydown`）。上下键移动高亮后，等本次 `scrollIntoView` 触发的滚动事件过去，再在下一帧展示当前项的描述卡片；该项没有描述且不支持思考深度时收起卡片。悬停仍保持约 300ms 延迟。
8. 图标由 [ResourceIcon](/components/helper/resource-icon) 渲染（`type="model"`）：支持图片 URL 或 Vue 组件，URL 加载失败自动回退到内置兜底图标；未提供 `icon` 时不渲染图标位。

## 关联组件

- [ChatInput](/components/input/chat-input)：传入 `models` 后默认在发送按钮左侧渲染本组件，也可通过 `#model-selector` 插槽完全自定义。
- [ChatContainer](/components/setup/chat-container)：透传 `models`、`v-model:selected-model` 与 `v-model:reasoning-effort`，并向上 emit `modelChange`、`reasoningEffortChange`。
- [ResourceIcon](/components/helper/resource-icon)：触发器与选项的图标渲染。
