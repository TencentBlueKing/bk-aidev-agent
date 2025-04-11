# Props

组件支持的属性列表。

| 属性名          | 类型              | 默认值      | 描述                                                                                                   |
| --------------- | ----------------- | ----------- | ------------------------------------------------------------------------------------------------------ |
| `url`           | `String`          | `''`        | **必需**. AI 服务接口地址。                                                                              |
| `title`         | `String`          | `'AI 小鲸'`  | 在头部显示的标题文本。                                                                                |
| `helloText`     | `String`          | `'你好，我是小鲸'` | 初始欢迎页面显示的问候语。                                                                        |
| `enablePopup`   | `Boolean`         | `true`      | 是否启用选中文本后的弹出操作窗口 (需要配合 `shortcuts` 使用)。                                            |
| `shortcuts`     | `Array<ShortCut>` | `[]`        | 快捷操作列表。详细格式参见 [内容引用与快捷操作指南](/guide/core-features/content-referencing#配置快捷操作-shortcuts)。 |
| `prompts`       | `Array<String>`   | `[]`        | 预设提示词列表。详细说明参见 [预设提示词指南](/guide/core-features/prompts)。                         |
| `requestOptions`| `Object`          | `{}`        | 自定义请求选项，可设置 `headers` 和 `data` 属性，分别合并到请求头和请求体。详细说明参见 [自定义请求指南](/guide/advanced-usage/custom-requests)。 |
| `defaultMinimize`| `Boolean`         | `false`     | 控制 AI 小鲸窗口初始是否处于最小化状态。详细说明参见 [界面定制指南](/guide/core-features/ui-customization#初始最小化状态)。 |
| `sessionContents`| `Array`           | `[] (内部)` | **只读**. 暴露当前会话内容，可用于外部访问和操作。详细说明参见 [访问会话内容指南](/guide/advanced-usage/session-access)。 |

## `ShortCut` 对象格式

`shortcuts` 数组中的每个对象应符合以下格式：

```typescript
interface ShortCut {
  label: string;       // 按钮上显示的文本
  key: string;         // 操作的唯一标识符
  prompt: string;      // 指令模板，可包含 {{ SELECTED_TEXT }} 占位符
  icon?: string;       // (可选) 按钮图标的类名
}
```