# 提示词与资源

::: warning 重要：提示词与资源由 AIDev 后台配置
标准流程中，提示词（Prompts）和资源（Resources）通过 `agent/info` 接口自动加载，**无需前端定义**。
前端 `prompts` / `resources` prop 仅用于特殊场景下的覆盖或补充。
:::

AI 小鲸 v2.0 支持两种预设输入辅助：**提示词（Prompts）** 和 **资源引用（Resources）**。它们帮助用户快速发起对话或引用外部资源。

## 默认行为（零配置）

当你在 AIDev 平台配置好 Agent 的提示词和资源后，组件初始化时会自动加载并渲染到对话窗口中。**无需在前端传入任何 `prompts` 或 `resources` prop**。

## Prompt 列表配置

::: details 前端覆盖（特殊场景）
仅在需要覆盖或补充后端配置时使用。
:::

通过 `prompts` prop 配置预设提示词列表。`prompts` 是一个字符串数组，每个字符串代表一个可点击的提示词模板。

```vue
<template>
  <AIBlueking
    :url="apiUrl"
    :prompts="prompts"
  />
</template>

<script lang="ts" setup>
import AIBlueking from '@blueking/ai-blueking';
import '@blueking/ai-blueking/dist/vue3/style.css';

const apiUrl = '/api/ai/assistant/';

const prompts = [
  '请概括这段内容的主要观点',
  '请帮我分析这段文字中的问题',
  '请用简单的语言解释这个概念',
  '帮我写一个 Python 脚本，实现...',
  '假设你是一名数据库专家，请帮我写 SQL 查询',
  '你是一名经验丰富的前端开发工程师，请帮我解决以下问题...',
];
</script>
```

提示词显示在对话窗口中，用户点击后，其文本内容会直接作为消息发送给 AI。

若希望 AI 回复带**颜色、加粗、背景高亮**等行内样式，除在用户提示词中说明需求外，还应在 AIDev **系统提示词**中约定「蓝鲸行内富文本」`::bk::` 语法（勿用 HTML）。可将业务模板（如撤离通知）配在用户 `prompts` 中，格式约束写在 Agent 系统提示词里。详见 [蓝鲸行内富文本](/guide/core-features/markdown-inline-style)。

在 `ChatBot` 独立模式中同样支持：

```vue
<template>
  <ChatBot
    url="/api/ai/assistant/"
    :prompts="prompts"
  />
</template>
```

## 触发方式：输入 "/" 唤出提示词列表

`ChatInput` 组件内置了 "/" 指令触发支持。当用户在输入框中输入 `/` 字符时，会自动弹出提示词列表菜单：

- 输入 `/` 后弹出可选提示词列表
- 支持键盘导航（上下箭头选择，Enter 确认）
- 选中后自动填入输入框

## Resources 配置

通过 `resources` prop 配置资源列表，用户输入 `@` 字符时触发资源选择菜单。`resources` 使用 `IAiSlashMenuItem[]` 类型：

```vue
<template>
  <AIBlueking
    :url="apiUrl"
    :resources="resources"
  />
</template>

<script lang="ts" setup>
import AIBlueking from '@blueking/ai-blueking';
import '@blueking/ai-blueking/dist/vue3/style.css';
import type { IAiSlashMenuItem } from '@blueking/chat-x';

const apiUrl = '/api/ai/assistant/';

const resources: IAiSlashMenuItem[] = [
  {
    label: '项目文档',
    value: 'project_docs',
    description: '引用项目相关文档',
  },
  {
    label: '知识库',
    value: 'knowledge_base',
    description: '引用知识库中的内容',
  },
  {
    label: 'API 文档',
    value: 'api_docs',
    description: '引用 API 接口文档',
  },
];
</script>
```

### 触发方式

- 在输入框中输入 `@` 字符弹出资源选择菜单
- 支持键盘导航选择
- 选中后资源标识会作为上下文传递给后端

## ChatInput 内置支持

`ChatInput` 组件内置了对 `/` 和 `@` 触发菜单的支持：

- **自动弹出**：输入特殊字符时自动检测并弹出对应的菜单
- **键盘导航**：支持 `↑` `↓` 方向键选择菜单项，`Enter` 确认，`Escape` 关闭
- **模糊匹配**：输入 `/` 或 `@` 后继续输入文字可以过滤候选项
- **无缝集成**：选择后内容自动融入输入框

## 代码示例：完整配置

```vue
<template>
  <AIBlueking
    :url="apiUrl"
    :prompts="prompts"
    :resources="resources"
    :shortcuts="shortcuts"
    hello-text="你好！我是 AI 小鲸，试试输入 / 或 @ 来快速操作吧"
    placeholder="输入问题，或输入 / 查看提示词，@ 引用资源"
  />
</template>

<script lang="ts" setup>
import AIBlueking from '@blueking/ai-blueking';
import '@blueking/ai-blueking/dist/vue3/style.css';

const apiUrl = '/api/ai/assistant/';

// 预设提示词（输入 / 触发）
const prompts = [
  '请帮我分析这段代码的性能问题',
  '请将以下内容翻译为英文',
  '请帮我生成单元测试',
];

// 资源列表（输入 @ 触发）
const resources = [
  { label: '项目 README', value: 'readme' },
  { label: '接口文档', value: 'api_doc' },
  { label: '变更日志', value: 'changelog' },
];

// 快捷操作
const shortcuts = [
  {
    id: 'explain',
    name: '解释',
    components: [
      { type: 'textarea', key: 'text', name: '内容', fillBack: true },
    ],
  },
];
</script>
```
