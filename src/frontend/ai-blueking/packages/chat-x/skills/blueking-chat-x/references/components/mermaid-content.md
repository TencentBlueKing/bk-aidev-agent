# MermaidContent Mermaid 图表

> 能力域：内容渲染 ｜ 导入：`import { MermaidContent } from '@blueking/chat-x'` ｜ since 1.0.0

渲染 Mermaid 图表并处理渲染事件。 源码位置：src/components/markdown-token/mermaid-content/mermaid-content.vue。

**关联**：markdown-content（解析 mermaid 类型 fence 代码块后传入 token）

---

# MermaidContent Mermaid 图表渲染
## 源码事实

- **源码位置**：`src/components/markdown-token/mermaid-content/mermaid-content.vue`
- **能力域**：内容渲染
- **能力说明**：渲染 Mermaid 图表并处理渲染事件。

> **能力域**：内容渲染

Markdown Token 层的 Mermaid 图表渲染基础组件，被 `MarkdownContent` 在检测到 mermaid fence token 时自动调用，通常无需手动引入。

核心能力：**按需懒加载 Mermaid**（动态 import 单例）、**三级去重跳过**（代码比对 → 语法校验 → SVG 比对）、**100ms throttle** 流式防抖、**错误静默**（parse 失败时保持上一次 SVG）。

## 组件结构与渲染流程

```
props.token（Token[]）
│
├─ extractMermaidCode(tokens)
│    → 遍历找第一个 type==='fence' && info.trim()==='mermaid' && content 非空的 token
│    → 返回 content（无匹配返回空字符串）
│
└─ renderMermaid（throttle 100ms，leading + trailing）
      │
      ├─ 1. newCode === lastMermaidCode  → return（代码未变，跳过）
      ├─ 2. lastMermaidCode = newCode
      ├─ 3. getMermaidInstance()         → 动态 import('mermaid') 单例，初始化一次
      ├─ 4. mermaid.parse(code, { suppressErrors: true })
      │      → !isValid → return（语法无效，保持上次 SVG）
      ├─ 5. mermaid.render('mermaid-content-' + randomId, code) → { svg }
      ├─ 6. svgDomStr.value === svg      → return（SVG 无变化，跳过）
      └─ 7. svgDomStr.value = svg
             nextTick → emit('mounted', { get el() { return mermaidContentRef.value } })

模板：
div.ai-mermaid-content（:key="svgDomStr"，v-html="svgDomStr"）
  注：:key 绑定 svgDomStr，每次 SVG 变化会重建 div 而非就地 patch
```

## 基础用法

```vue
<template>
  <MermaidContent
    :token="tokens"
    @mounted="handleMounted"
  />
</template>

<script setup lang="ts">
  import { MermaidContent } from '@blueking/chat-x';
  import type { Token } from 'markdown-it';

  const tokens: Token[] = [
    {
      type: 'fence',
      tag: 'code',
      info: 'mermaid',
      content: `graph TD
    A[开始] --> B{判断}
    B -->|是| C[执行]
    B -->|否| D[结束]`,
    } as Token,
  ];

  const handleMounted = ({ el }: { el: HTMLElement | null }) => {
    // el 是 lazy getter，值为渲染后的 .ai-mermaid-content 元素
    console.log('渲染完成:', el);
  };
</script>
```

## 支持的图表类型

### 时序图（Sequence Diagram）

### 甘特图（Gantt）

### 类图（Class Diagram）

### 状态图（State Diagram）

### 饼图（Pie Chart）

## 流式渲染

流式输入时 Mermaid 语法逐步完整，组件通过 throttle + `parse` 语法校验避免无效渲染：

```vue
<template>
  <MermaidContent :token="streamingTokens" />
</template>

<script setup lang="ts">
  import { ref } from 'vue';
  import { MermaidContent } from '@blueking/chat-x';

  const streamingTokens = ref([{ type: 'fence', tag: 'code', info: 'mermaid', content: '' }]);

  const simulate = async () => {
    const code = `graph TD\n    A[开始] --> B[处理]\n    B --> C[结束]`;
    let content = '';
    for (const char of code) {
      await new Promise(r => setTimeout(r, 50));
      content += char;
      streamingTokens.value = [{ type: 'fence', tag: 'code', info: 'mermaid', content }];
    }
  };
</script>
```

**流式过程中的行为**：

| 阶段                       | `parse` 结果 | 行为                                      |
| -------------------------- | ------------ | ----------------------------------------- |
| 代码未变化                 | —            | 三级去重第 1 关：直接跳过，不调用 Mermaid |
| 语法不完整（如 `graph T`） | `false`      | 三级去重第 2 关：跳过渲染，保持上次 SVG   |
| 语法完整，SVG 相同         | `true`       | 三级去重第 3 关：跳过 DOM 更新            |
| 语法完整，SVG 变化         | `true`       | 更新 SVG，触发 `mounted` 事件             |

## API

### Props

| 属性名 | 类型      | 必填 | 说明                                                                                         |
| ------ | --------- | ---- | -------------------------------------------------------------------------------------------- |
| token  | `Token[]` | ✓    | markdown-it Token 数组；组件自动从中提取第一个 `type==='fence' && info==='mermaid'` 的 token |

### Events

| 事件名  | 参数                          | 触发时机                                                                           |
| ------- | ----------------------------- | ---------------------------------------------------------------------------------- |
| mounted | `{ el: HTMLElement \| null }` | SVG 更新后的 `nextTick`；`el` 为 lazy getter，返回当前 `.ai-mermaid-content` 元素引用 |

### Token 结构

```typescript
// 组件只识别 type === 'fence' 且 info.trim() === 'mermaid' 的 token
{
  type: 'fence';
  tag?: 'code';         // 可选
  info: 'mermaid';      // 必须严格等于 'mermaid'（trim 后）
  content: string;      // Mermaid 图表定义语法
}
```

## 性能与错误处理细节

### 单例 Mermaid 实例

```typescript
// 模块级变量，所有 MermaidContent 实例共享同一个 mermaid 模块
let mermaidInstance: MermaidModule | null = null;

// 初始化时调用一次（suppressErrorRendering: true 抑制 Mermaid 内部错误 UI）
mermaidInstance.default.initialize({ suppressErrorRendering: true });
```

首次渲染因动态 import 会有约 200~500ms 的网络加载延迟，之后复用实例无额外开销。

### SVG ID 随机化

每次调用 `mermaid.render` 时生成随机 ID：

```typescript
mermaid.default.render('mermaid-content-' + Math.random().toString(36).substring(2, 15), code);
```

避免多个 MermaidContent 实例或同一实例多次渲染时 DOM ID 冲突。

### 错误静默

- `mermaid.parse` 失败（语法无效）→ `return`，不修改 `svgDomStr`，保持上次成功的 SVG
- `mermaid.render` 抛出异常 → `console.warn`，不修改 `svgDomStr`，保持上次成功的 SVG
- 两种情况下组件界面均无错误提示（静默降级）

## 关联组件

- [MarkdownContent](/components/rendering/markdown-content) — mermaid fence token 的来源与挂载
