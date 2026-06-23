# ShortcutRender 快捷指令表单

> 能力域：输入交互 ｜ 导入：`import { ShortcutRender } from '@blueking/chat-x'` ｜ since 1.0.0

渲染快捷指令 components 表单并回传确认数据。 源码位置：src/components/ai-shortcut/shortcut-render/shortcut-render.vue。

**关联**：shortcut-btn（与快捷指令 Shortcut 元数据一致，表单提交前在列表中选中入口）、chat-input（提交或取消后与输入框内容与状态联动）、chat-container（顶层聊天布局中承载快捷表单区域）

---

# ShortcutRender 快捷指令渲染器
## 源码事实

- **源码位置**：`src/components/ai-shortcut/shortcut-render/shortcut-render.vue`
- **能力域**：输入交互
- **能力说明**：渲染快捷指令 components 表单并回传确认数据。

> **能力域**：输入交互

快捷指令表单渲染组件，将 `Shortcut.components` 配置自动渲染为可交互表单（基于 bkui-vue 的 `Form`），支持 8 种控件类型、两列网格布局、必填校验和内置提交/取消操作。

## 组件结构

```
┌─────────────────────────────────────────────────┐
│  .shortcut-render-header（渐变左边框）            │
│  ✧ ThinkingIcon  快捷指令名称           ✕ Close  │
├─────────────────────────────────────────────────┤
│  .shortcut-render-content（max-height: 424px，   │
│   overflow-y: auto）                             │
│  ┌─────────────┬─────────────┐                   │
│  │ FormItem    │ FormItem    │  ← 两列网格        │
│  ├─────────────┴─────────────┤                   │
│  │    textarea（span 2）     │  ← 独占一行        │
│  ├─────────────────────────── ┤                   │
│  │  提交    取消（sticky）    │  ← 底部始终可见    │
│  └─────────────────────────── ┘                   │
└─────────────────────────────────────────────────┘
```

> 底部操作栏使用 `position: sticky; bottom: 1px`，滚动长表单时始终固定在底部可见区域。

## 基础用法

传入 `name` 和 `components` 即可渲染一个快捷指令表单：

```vue
<template>
  <ShortcutRender
    :name="shortcut.name"
    :components="shortcut.components"
    @close="handleClose"
    @submit="handleSubmit"
  />
</template>

<script setup lang="ts">
  import { ShortcutRender, type Shortcut } from '@blueking/chat-x';

  const shortcut: Shortcut = {
    id: 'translate',
    name: '翻译',
    components: [
      {
        type: 'select',
        key: 'targetLang',
        name: '目标语言',
        default: 'en',
        options: [
          { label: '英文', value: 'en' },
          { label: '中文', value: 'zh' },
          { label: '日文', value: 'ja' },
        ],
      },
      {
        type: 'textarea',
        key: 'content',
        name: '翻译内容',
        fillBack: true,
        placeholder: '请输入要翻译的内容',
        rows: 4,
      },
    ],
  };

  const handleClose = () => console.log('关闭');
  const handleSubmit = (formModel: Record<string, unknown>) => {
    // { targetLang: 'en', content: '...' }
    console.log('提交:', formModel);
  };
</script>
```

**渲染效果**

## 全部表单类型

`ShortcutRender` 支持 8 种控件类型，通过 `type` 字段指定：

```vue
<script setup lang="ts">
  import { type ShortcutComponent } from '@blueking/chat-x';

  const components: ShortcutComponent[] = [
    // 单行文本输入
    { type: 'input', key: 'language', name: '编程语言', placeholder: '如：TypeScript、Python' },
    // 数字输入（支持 min/max）
    { type: 'number', key: 'maxLines', name: '最大行数', default: '50', min: 1, max: 500 },
    // 下拉选择
    {
      type: 'select',
      key: 'style',
      name: '代码风格',
      default: 'concise',
      options: [
        { label: '简洁', value: 'concise' },
        { label: '详细注释', value: 'detailed' },
      ],
    },
    // 单选组
    {
      type: 'radioGroup',
      key: 'outputFormat',
      name: '输出格式',
      default: 'code',
      options: [
        { label: '代码块', value: 'code' },
        { label: '文件', value: 'file' },
      ],
    },
    // 多选组
    {
      type: 'checkboxGroup',
      key: 'features',
      name: '包含功能',
      options: [
        { label: '注释', value: 'comments' },
        { label: '错误处理', value: 'error-handling' },
      ],
    },
    // 开关
    { type: 'switcher', key: 'async', name: '异步函数' },
    // 多行文本（独占一行）
    {
      type: 'textarea',
      key: 'description',
      name: '功能描述',
      fillBack: true,
      rows: 3,
      placeholder: '请详细描述需要生成的代码功能',
    },
  ];
</script>
```

**渲染效果**

## 表单初始值

### 通过 `component.default`（推荐）

直接在 `ShortcutComponent` 上设置 `default`，该字段在表单初始化时被优先使用：

```typescript
const components: ShortcutComponent[] = [
  {
    type: 'select',
    key: 'lang',
    name: '语言',
    default: 'zh', // ← 初始选中"中文"
    options: [
      { label: '中文', value: 'zh' },
      { label: '英文', value: 'en' },
    ],
  },
];
```

### 通过 `formModel` prop

`formModel` 适合传入**不在 `components` 中的额外字段**，或特殊场景下的外部初始值。

```vue
<template>
  <ShortcutRender
    name="搜索"
    :components="components"
    :form-model="initialValues"
    @submit="handleSubmit"
  />
</template>

<script setup lang="ts">
  const components = [
    { type: 'input', key: 'keyword', name: '关键词' },
    {
      type: 'select',
      key: 'scope',
      name: '范围',
      options: [
        { label: '全部', value: 'all' },
        { label: '标题', value: 'title' },
      ],
    },
  ];

  // formModel 中与 components 同名的 key 会被 component.default 覆盖
  // 若 component 没有设置 default，对应 formModel 的值也会被 undefined 覆盖
  const initialValues = { keyword: 'Vue 3', scope: 'title' };
</script>
```

**初始化优先级（`watchEffect` 执行顺序）**：

```
① 先写入 formModel 中的所有 key-value
② 再遍历 components，对每个 component.key 写入：
   component.default ?? component.props?.default ?? component.props?.modelValue
```

> **注意**：步骤 ② 会覆盖步骤 ① 的值。若某个 component 没有设置 `default`，该 key 会被写入 `undefined`，**formModel 中对应的值会丢失**。因此，当 component 和 formModel 存在同名 key 时，应在 component 上设置 `default`，而非依赖 `formModel`。

## 必填校验（fillBack）

`fillBack: true` 将表单项映射为 bkui-vue `Form.FormItem` 的 `required: true`，提交时若为空则阻止提交并展示错误提示：

```typescript
const components: ShortcutComponent[] = [
  {
    type: 'input',
    key: 'title',
    name: '标题',
    fillBack: true, // 必填
    placeholder: '请输入标题',
  },
  {
    type: 'textarea',
    key: 'content',
    name: '内容',
    fillBack: true, // 必填
    rows: 5,
  },
  {
    type: 'select',
    key: 'category',
    name: '分类', // 选填（无 fillBack）
    options: [
      { label: '技术', value: 'tech' },
      { label: '业务', value: 'biz' },
    ],
  },
];
```

> `fillBack` 同时具有语义作用：在 `ChatInput`/`UserMessage` 场景下，标记了 `fillBack: true` 的字段内容会被回填到对话输入框中。

## 布局规则

表单使用 **两列网格**（`grid-template-columns: repeat(2, 1fr)`）排列：

| 情况                                                      | 占列数                    |
| --------------------------------------------------------- | ------------------------- |
| `type === 'textarea'`                                     | 始终 `span 2`（独占一行） |
| 最后一个 item，且前面所有 item 累计列数为偶数（独占新行） | `span 2`                  |
| 其他                                                      | `auto`（占 1 列）         |

```
┌─────────────┬─────────────┐
│   input     │   number    │  ← 各占半行
├─────────────┴─────────────┤
│         textarea          │  ← 独占一行
├─────────────┬─────────────┤
│   select    │  switcher   │  ← 各占半行
├─────────────┴─────────────┤
│    最后一个（奇数起新行）  │  ← 自动独占
└───────────────────────────┘
```

## 透传底层组件 props

通过 `component.props` 可直接透传给 bkui-vue 底层控件，`component.props.options` 优先于 `component.options`：

```typescript
const components: ShortcutComponent[] = [
  {
    type: 'select',
    key: 'lang',
    name: '语言',
    // 方式一：通过 component.options（常规）
    options: [{ label: '中文', value: 'zh' }],
    // 方式二：通过 component.props（优先级更高，覆盖 options）
    props: {
      options: [{ label: '英文', value: 'en' }], // 此处会覆盖上面的 options
      clearable: true, // 透传给 bkui-vue Select 的其他 prop
    },
  },
  {
    type: 'input',
    key: 'text',
    name: '文本',
    props: {
      clearable: true, // 透传给 bkui-vue Input
      maxlength: 100,
    },
  },
];
```

通过 `component.formItemProps` 透传给 `Form.FormItem`：

```typescript
{
  type: 'input',
  key: 'email',
  name: '邮箱',
  formItemProps: {
    description: '请输入有效的邮箱地址',  // bkui-vue FormItem 的 description prop
  },
}
```

## API

### Props

| 属性名      | 类型                      | 默认值 | 说明                                                                 |
| ----------- | ------------------------- | ------ | -------------------------------------------------------------------- |
| id          | `string`                  | —      | 快捷指令唯一标识（透传，不影响表单渲染）                             |
| name        | `string`                  | —      | 表单标题，显示在头部栏                                               |
| description | `string`                  | —      | 快捷指令描述（透传，组件内部不渲染）                                 |
| components  | `ShortcutComponent[]`     | —      | 表单控件配置列表                                                     |
| formModel   | `Record<string, unknown>` | —      | 外部初始值；与 `components` 同名 key 时，以 `component.default` 为准 |

### Events

| 事件名 | 参数                                   | 触发时机                                   |
| ------ | -------------------------------------- | ------------------------------------------ |
| close  | —                                      | 点击头部关闭图标 **或** 底部取消按钮时触发 |
| submit | `(formModel: Record<string, unknown>)` | 表单校验通过后点击提交按钮触发             |

## ShortcutComponent 配置项

### 通用字段

| 字段          | 类型                                 | 必填 | 说明                                                                                       |
| ------------- | ------------------------------------ | ---- | ------------------------------------------------------------------------------------------ |
| type          | 见[表单类型](#表单组件类型)          | ✓    | 控件类型；未知类型返回 `null`，不渲染                                                      |
| key           | `string`                             | ✓    | 表单字段名；`submit` 事件返回对象以此为 key；同时作为校验 property                         |
| name          | `string`                             | —    | 表单项标签；优先于 `formItemProps.label`，通过 `#label` 插槽渲染为 `.shortcut-render-form-label` |
| default       | `string`                             | —    | 字段初始值；优先于 `formModel`，在 `watchEffect` 中覆盖写入                                |
| fillBack      | `boolean`                            | —    | `true` 时映射为 `required: true`（必填校验），同时标记回填语义                             |
| placeholder   | `string`                             | —    | 占位文本（`input` / `textarea` / `number` 可用）                                           |
| rows          | `number`                             | —    | 文本行数（`textarea` 可用）                                                                |
| min           | `number`                             | —    | 最小值（`number` 可用）                                                                    |
| max           | `number`                             | —    | 最大值（`number` 可用）                                                                    |
| options       | `{ label: string; value: string }[]` | —    | 选项列表（`select` / `radioGroup` / `checkboxGroup` 需要）；`component.props.options` 优先 |
| props         | `object`                             | —    | 直接透传给底层 bkui-vue 控件的 props；`options` 优先于 `component.options`                 |
| formItemProps | `object`                             | —    | 直接透传给 `Form.FormItem` 的 props                                                        |

### 表单组件类型

| `type`          | 底层控件               | 说明                         |
| --------------- | ---------------------- | ---------------------------- |
| `input`         | `Input`                | 单行文本输入框               |
| `text`          | `Input`                | 同 `input`，兼容旧版写法     |
| `textarea`      | `Input[type=textarea]` | 多行文本，**始终独占一行**   |
| `number`        | `Input[type=number]`   | 数字输入，支持 `min` / `max` |
| `select`        | `Select`               | 下拉选择，需配置 `options`   |
| `radioGroup`    | `Radio.Group`          | 单选组，需配置 `options`     |
| `checkboxGroup` | `Checkbox.Group`       | 多选组，需配置 `options`     |
| `switcher`      | `Switcher`             | 开关，值为 `boolean`         |
| 其他            | —                      | 返回 `null`，不渲染任何控件  |

## 类型定义

```typescript
import type { Shortcut, ShortcutComponent } from '@blueking/chat-x';

interface Shortcut {
  id?: string;
  name?: string;
  description?: string;
  icon?: string | VNode | ((h: typeof h) => Component | VNode);
  components?: ShortcutComponent[];
  formModel?: Record<string, unknown>;
}

// ShortcutComponent 是各具体类型的联合类型
type ShortcutComponent =
  | InputShortcutComponent
  | TextShortcutComponent
  | TextareaShortcutComponent
  | NumberShortcutComponent
  | SelectShortcutComponent
  | RadioGroupShortcutComponent
  | CheckboxGroupShortcutComponent
  | SwitcherShortcutComponent;

// 所有类型共有字段（BaseShortcutComponent）
interface BaseShortcutComponent {
  type: string;
  key: string;
  name?: string;
  default?: string;
  fillBack?: boolean;
  placeholder?: string;
  rows?: number;
  min?: number;
  max?: number;
  options?: { label: string; value: string }[];
  props?: Record<string, unknown>; // 透传给底层控件
  formItemProps?: Record<string, unknown>; // 透传给 Form.FormItem
}
```

## 样式说明

表单项与控件会附加类型化 class，便于样式覆盖：`shortcut-render-form-item_{type}`（如 `_radio`、`_checkbox`），单选/多选项子项为 `shortcut-render-form-item_radio` / `shortcut-render-form-item_checkbox`。表单项标签使用 BEM 风格类名 `shortcut-render-form-label`。

## 关联组件

- [ShortcutBtn](/components/input/shortcut-btn) — 与 Shortcut 数据模型一致的入口按钮
- [ChatInput](/components/input/chat-input) — 输入区与快捷指令流程联动
- [ChatContainer](/components/setup/chat-container) — 顶层布局中挂载快捷表单
