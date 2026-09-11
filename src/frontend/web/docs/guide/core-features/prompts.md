# 提示词与资源

::: warning 重要：提示词与资源由 AIDev 后台配置
标准流程中，提示词（Prompts）、技能（Skills）和资源（Resources）通过 `agent/info` 接口自动加载，**无需前端定义**。
前端 `prompts` / `resources` / `skills` prop 仅用于特殊场景下的覆盖或补充。
`AIBlueking` **没有** `skills` prop，Skill 只来自 `agent.info.relatedSkills`。
:::

AI 小鲸支持四类输入辅助，chat-x ≥ 0.0.52 后统一映射为 `menuSources`，宿主仍可继续传旧 props：

| 触发符 | 分组 | 数据来源 |
| --- | --- | --- |
| `/` | Skill / MCP / 工具 | `ChatBot.skills` 或 `agent.info.relatedSkills` + `resources` |
| `@` | 知识库 / 会话产物 | `resources` 或 `agent.info.resources`；产物由 chat-x 自动收集 |
| `\` | Prompt | `prompts` 或 `agent.info.conversationSettings.predefinedQuestions` |
| `+` | 全部分组 | 以上全部；含内置「文件」上传 |

`prompts` 仍是 `string[]`：`name` 与 `content` 都用全文，不截断。选中 prompt 会整体替换输入框文本，不产生标签。

## 默认行为（零配置）

当你在 AIDev 平台配置好 Agent 的提示词、技能和资源后，组件初始化时会自动加载。**无需在前端传入任何 `prompts` / `resources` / `skills` prop**。

## Prompt 列表配置

::: details 前端覆盖（特殊场景）
仅在需要覆盖或补充后端配置时使用。
:::

通过 `prompts` prop 配置预设提示词列表。`prompts` 是一个字符串数组，每个字符串代表一条可插入的提示词。

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
];
</script>
```

输入 **`\`** 唤出提示词列表（不是 `/`）。选中后全文替换输入框，用户再发送。

若希望 AI 回复带**颜色、加粗、背景高亮**等行内样式，除在用户提示词中说明需求外，还应在 AIDev **系统提示词**中约定「蓝鲸行内富文本」`::bk::` 语法（勿用 HTML）。详见 [蓝鲸行内富文本](/guide/core-features/markdown-inline-style)。

## Resources 配置

通过 `resources` prop 覆盖资源列表，类型为 `IHostResourceItem[]`（保持旧字段形状：`type` / `name` / `code` / `id` / `icon`）。内部会映射为 chat-x `IInputMenuItem`：

- `tool` / `mcp`：菜单 `id` = `code`
- `knowledgebase` / `doc`：菜单 `id` = `String(数值 id)`，`id` 为 null 时回退 `code`
- `shortcut` / `file` / `artifact` / 未知 type / 空 id 会被丢弃（快捷指令走 `shortcuts`，文件走内置上传，产物由 chat-x 自动收集）

```vue
<template>
  <AIBlueking
    :url="apiUrl"
    :resources="resources"
  />
</template>

<script lang="ts" setup>
import AIBlueking from '@blueking/ai-blueking';
import type { IHostResourceItem } from '@blueking/ai-blueking';
import '@blueking/ai-blueking/dist/vue3/style.css';

const apiUrl = '/api/ai/assistant/';

const resources: IHostResourceItem[] = [
  { type: 'tool', name: '搜索工具', code: 'search_tool', id: 1, icon: '' },
  { type: 'knowledgebase', name: '运维知识库', code: 'ops_kb', id: 58, icon: '' },
];
</script>
```

## 发送协议：`property.docSchema`

选中资源后，发送载荷把编辑器文档**原样**放在 `property.docSchema`（与 `extra` **同级**）。**不再发送** `extra.resources`。`extra` 只保留 `cite` / `command` / `context`。

纯文本消息（文档里没有任何标签）不写 `docSchema`。上传文件除 `content` 里的 Binary 外，文档里还会带一条 `artifact` 标签：`label` 取上传接口 `name`，`value` 取 `path`，接口 `type: file` 映射为 `artifact`。这条标签由 chat-x 在发送前注入进文档，`ai-blueking` 只原样透传。

标签节点只携带 5 个字段：`{ type, label, value, icon, description }`。后端识别靠 `value`：

| `data.type` | `value` |
| --- | --- |
| `skill` | `skill_code` |
| `mcp` / `tool` | `code` |
| `knowledgebase` / `doc` | `String(id)`，null 时回退 `code` |
| `artifact` | PV 相对路径 |

整段 cite 工具栏已移除，但 `v-model:cite` / `setCiteText` 仍可用。
