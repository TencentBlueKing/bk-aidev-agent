# 消息自定义渲染

> 让 AI 对话不再局限于纯文本 —— 在消息中嵌入图表、表单、iframe 等任意自定义组件。

![自定义渲染 Demo](/images/guide/custom-message-rendering.png)

## 概述

AI Blueking 提供了灵活的消息自定义渲染机制，允许业务方在 AI 对话中嵌入**任意自定义内容**：

- **数据可视化**：柱状图、折线图、饼图、K 线图、热力图等
- **外部页面嵌入**：iframe 内嵌仪表盘、文档、第三方应用
- **用户交互**：表单、按钮、选择器等交互组件
- **业务逻辑**：审批流程、状态展示、操作面板等
- **混合展示**：文本 + 自定义组件自由组合

**核心理念**：ai-blueking 只提供渲染框架和解析机制，具体的组件实现由业务方根据自身需求定义。

---

## 工作原理

整个机制分为三个层次

![自定义消息渲染机制](/images/guide/custom-message-render.png)

**核心约定**：AI 在回复中用 ` ```custom-component ` 代码块包裹 JSON 数据，业务方通过 `parseCustomBlocks()` 将消息内容解析为「文本块」与「自定义组件块」的混合列表，再分发给对应的 Vue 组件渲染。

### 解析工具函数

`parseCustomBlocks` 已内置在 `@blueking/ai-blueking` 中，**直接 import 使用即可，无需自行实现**：

```typescript
import { parseCustomBlocks } from "@blueking/ai-blueking"
import type { ContentBlock, CustomBlock, TextBlock } from "@blueking/ai-blueking"
```

函数签名：

```typescript
// 文本块
interface TextBlock {
  type: "text"
  content: string
}

// 自定义组件块（AI 输出的 JSON 被解析后放入 data）
interface CustomBlock {
  type: "custom"
  data: Record<string, unknown>
  raw: string
}

type ContentBlock = CustomBlock | TextBlock

// 将消息内容解析为 blocks 列表
function parseCustomBlocks(content: unknown): ContentBlock[]
```

调用示例：

```typescript
const blocks = parseCustomBlocks(`
这是文本部分。

\`\`\`custom-component
{"type": "chart", "title": "销售数据", "data": {"labels": ["Q1","Q2"], "values": [100,150]}}
\`\`\`
`)

// 结果：
// [
//   { type: "text", content: "这是文本部分。" },
//   { type: "custom", data: { type: "chart", title: "销售数据", ... }, raw: "..." }
// ]
```

---

## 快速开始

开发自定义消息渲染需要三步：**实现自定义组件** → **组合消息渲染器** → **接入 ChatBot**。

### 第一步：实现自定义组件

根据业务需求，为每种自定义内容创建对应的 Vue 组件。组件通过 `data` prop 接收 AI 输出的 JSON 数据。

以下是三个典型示例。

#### 示例 1：图表组件 (ChartWidget)

```vue
<!-- components/custom-widgets/ChartWidget.vue -->
<template>
  <div class="chart-widget">
    <div class="chart-title">{{ data.title || "图表" }}</div>
    <div ref="chartRef" class="chart-container" />
  </div>
</template>

<script setup lang="ts">
  import { onMounted, ref, watch } from "vue"
  import * as echarts from "echarts"

  const props = defineProps<{
    data: {
      title?: string
      chartType?: string
      data?: {
        labels?: string[]
        values?: number[]
      }
    }
  }>()

  const chartRef = ref<HTMLElement>()
  let chart: echarts.ECharts | null = null

  const renderChart = () => {
    if (!chartRef.value) return
    if (!chart) {
      chart = echarts.init(chartRef.value)
    }
    const labels = props.data?.data?.labels || []
    const values = props.data?.data?.values || []
    const type = props.data?.chartType || "bar"
    chart.setOption({
      tooltip: { trigger: "axis" },
      xAxis: { type: "category", data: labels },
      yAxis: { type: "value" },
      series: [{ type, data: values }],
    })
  }

  onMounted(renderChart)
  watch(() => props.data, renderChart, { deep: true })
</script>

<style scoped>
  .chart-widget {
    padding: 16px;
    background: #fafbfd;
    border: 1px solid #e1ecff;
    border-radius: 8px;
  }
  .chart-title {
    margin-bottom: 12px;
    font-size: 14px;
    font-weight: 600;
    color: #313238;
  }
  .chart-container {
    width: 100%;
    height: 200px;
  }
</style>
```

#### 示例 2：iframe 嵌入组件 (IframeWidget)

```vue
<!-- components/custom-widgets/IframeWidget.vue -->
<template>
  <div class="iframe-widget">
    <div class="iframe-header">
      <span class="iframe-title">{{ data.title || "嵌入页面" }}</span>
      <a :href="data.src" target="_blank" class="iframe-link">在新窗口打开</a>
    </div>
    <iframe
      :src="data.src"
      :style="{ height: (data.height || 400) + 'px' }"
      class="iframe-content"
      sandbox="allow-scripts allow-same-origin allow-forms"
    />
  </div>
</template>

<script setup lang="ts">
  defineProps<{
    data: {
      title?: string
      src: string
      height?: number
    }
  }>()
</script>

<style scoped>
  .iframe-widget {
    overflow: hidden;
    border: 1px solid #e1ecff;
    border-radius: 8px;
  }
  .iframe-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 8px 12px;
    background: #f0f5ff;
    border-bottom: 1px solid #e1ecff;
  }
  .iframe-title {
    font-size: 13px;
    font-weight: 500;
    color: #313238;
  }
  .iframe-link {
    font-size: 12px;
    color: #3a84ff;
    text-decoration: none;
  }
  .iframe-content {
    display: block;
    width: 100%;
    border: none;
  }
</style>
```

#### 示例 3：交互表单组件 (FormWidget)

```vue
<!-- components/custom-widgets/FormWidget.vue -->
<template>
  <div class="form-widget">
    <div class="form-title">{{ data.title || "交互表单" }}</div>
    <div class="form-fields">
      <div v-for="(field, index) in data.fields" :key="index" class="form-field">
        <label class="field-label">{{ field.label }}</label>
        <select v-if="field.type === 'select'" v-model="formValues[field.label]" class="field-input">
          <option v-for="opt in field.options" :key="opt" :value="opt">{{ opt }}</option>
        </select>
        <input v-else v-model="formValues[field.label]" class="field-input" :placeholder="field.placeholder || ''" />
      </div>
    </div>
    <div class="form-actions">
      <button
        v-for="action in data.actions"
        :key="action"
        class="form-btn"
        :class="{ primary: action === '确认' || action === '提交' }"
        @click="handleAction(action)"
      >
        {{ action }}
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
  import { reactive } from "vue"

  const props = defineProps<{
    data: {
      title?: string
      fields?: Array<{
        label: string
        type?: string
        options?: string[]
        placeholder?: string
      }>
      actions?: string[]
    }
  }>()

  const formValues = reactive<Record<string, string>>({})

  ;(props.data.fields || []).forEach((field) => {
    formValues[field.label] = field.options?.[0] || ""
  })

  const handleAction = (action: string) => {
    console.log("[FormWidget] action:", action, "values:", { ...formValues })
    // 在这里触发业务逻辑，如发送消息、调用 API 等
  }
</script>

<style scoped>
  .form-widget {
    padding: 16px;
    background: #fafbfd;
    border: 1px solid #e1ecff;
    border-radius: 8px;
  }
  .form-title {
    margin-bottom: 12px;
    font-size: 14px;
    font-weight: 600;
    color: #313238;
  }
  .form-fields {
    display: flex;
    flex-direction: column;
    gap: 10px;
    margin-bottom: 16px;
  }
  .form-field {
    display: flex;
    gap: 8px;
    align-items: center;
  }
  .field-label {
    flex-shrink: 0;
    width: 80px;
    font-size: 13px;
    color: #63656e;
  }
  .field-input {
    flex: 1;
    height: 32px;
    padding: 0 10px;
    font-size: 13px;
    border: 1px solid #dcdee5;
    border-radius: 4px;
  }
  .form-actions {
    display: flex;
    gap: 8px;
    justify-content: flex-end;
  }
  .form-btn {
    height: 32px;
    padding: 0 16px;
    font-size: 13px;
    color: #63656e;
    background: #fff;
    border: 1px solid #dcdee5;
    border-radius: 4px;
    cursor: pointer;
  }
  .form-btn.primary {
    color: #fff;
    background: #3a84ff;
    border-color: #3a84ff;
  }
</style>
```

### 第二步：组合消息渲染器

将 `parseCustomBlocks` 与自定义组件组合，创建消息渲染器。它负责：

- 非 Assistant 消息直接交给默认渲染
- Assistant 消息解析 blocks，按类型分发到对应组件

```vue
<!-- components/custom-widgets/CustomMessageRenderer.vue -->
<template>
  <!-- 非 Assistant 消息：使用默认渲染 -->
  <MessageRender v-if="message.role !== MessageRole.Assistant" :message="message" />

  <!-- Assistant 消息：解析 blocks 并分发渲染 -->
  <div v-else class="custom-message-renderer">
    <template v-for="(block, index) in blocks" :key="index">
      <!-- 文本块：交给 MessageRender 渲染 Markdown -->
      <MessageRender v-if="block.type === 'text'" :message="{ ...message, content: block.content }" />
      <!-- 自定义组件块：按 type 分发 -->
      <div v-else-if="block.type === 'custom'" class="custom-block-wrapper">
        <ChartWidget v-if="block.data.type === 'chart'" :data="block.data" />
        <IframeWidget v-else-if="block.data.type === 'iframe'" :data="block.data" />
        <FormWidget v-else-if="block.data.type === 'form'" :data="block.data" />
        <!-- 继续添加你的组件类型 -->
        <div v-else class="unknown-block">未知组件类型: {{ block.data.type }}</div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
  import { computed } from "vue"
  import { MessageRender, MessageRole } from "@blueking/chat-x"
  import { parseCustomBlocks } from "@blueking/ai-blueking"
  import type { Message } from "@blueking/chat-x"
  import ChartWidget from "./ChartWidget.vue"
  import IframeWidget from "./IframeWidget.vue"
  import FormWidget from "./FormWidget.vue"

  const props = defineProps<{
    message: Message
  }>()

  const blocks = computed(() => parseCustomBlocks(props.message.content || ""))
</script>

<style scoped>
  .custom-message-renderer {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .custom-block-wrapper {
    margin: 8px 0;
  }
  .unknown-block {
    padding: 12px;
    font-size: 13px;
    color: #ea3636;
    background: #fff5f5;
    border: 1px solid #fedddd;
    border-radius: 8px;
  }
</style>
```

### 第三步：接入 ChatBot / AIBlueking

通过 `#message` 插槽传入你的渲染器：

```vue
<template>
  <ChatBot :chat-helper="chatHelper" :url="apiUrl">
    <template #message="{ message }">
      <CustomMessageRenderer :message="message" />
    </template>
  </ChatBot>
</template>

<script setup>
  import { ChatBot } from "@blueking/ai-blueking"
  import CustomMessageRenderer from "./components/custom-widgets/CustomMessageRenderer.vue"
</script>
```

至此，当 AI 回复中出现 ` ```custom-component ` 代码块时，就会被自动识别并渲染为对应组件。

---

## 配置 AI Prompt

自定义渲染的完整效果依赖 AI 的配合——需要在系统 Prompt 中告知模型何时、以何种格式输出自定义组件。

### AI 输出格式

AI 通过 `custom-component` 代码块输出组件数据，内容为合法 JSON：

````
```custom-component
{"type": "组件类型", ...其他字段}
```
````

AI 回复可以**混合文本与多个自定义组件**：

````
这是本月销售分析报告：

```custom-component
{"type": "chart", "chartType": "bar", "title": "月度销售额", "data": {"labels": ["1月","2月","3月"], "values": [120,150,180]}}
```

**关键发现：**
- Q2 增长率提升 15%

```custom-component
{"type": "form", "title": "反馈收集", "fields": [{"label": "评价", "type": "select", "options": ["好","一般","差"]}], "actions": ["提交"]}
```
````

### 系统 Prompt 模板

将以下内容加入系统 Prompt，AI 就能正确输出你注册的组件：

```
你可以使用自定义组件来丰富回复内容。输出格式如下：

\`\`\`custom-component
{"type": "组件类型", ...字段}
\`\`\`

支持的组件类型：

1. 图表 (chart)
   - chartType: "bar" / "line" / "pie"
   - title: 图表标题（可选）
   - data: { labels: string[], values: number[] }

2. iframe 嵌入 (iframe)
   - src: 嵌入页面的 URL（必填）
   - title: 标题（可选）
   - height: 高度（像素，可选，默认 400）

3. 交互表单 (form)
   - title: 表单标题（可选）
   - fields: [{ label, type, options, placeholder }]
   - actions: 按钮文本数组

4. 审批流程 (approval)
   - requestId: 请求 ID（必填）
   - status: "pending" / "approved" / "rejected"（必填）
   - requester: 申请人（必填）
   - description: 描述（可选）

注意：
- JSON 必须合法，字符串中的引号需正确转义
- 可以在一条消息中混合文本和多个自定义组件
- 不在上述列表中的 type 将显示"未知组件类型"
```

### 组件字段速查表

| 组件类型   | type         | 必填字段                                  | 可选字段          |
| ---------- | ------------ | ----------------------------------------- | ----------------- |
| 图表       | `chart`      | `chartType`, `data.labels`, `data.values` | `title`           |
| iframe     | `iframe`     | `src`                                     | `title`, `height` |
| 表单       | `form`       | `fields`, `actions`                       | `title`           |
| 审批       | `approval`   | `requestId`, `status`, `requester`        | `description`     |

---

## 扩展新组件类型

扩展新组件只需三步：

**1. 实现组件**

```vue
<!-- components/custom-widgets/ApprovalWidget.vue -->
<template>
  <div class="approval-widget">
    <div class="approval-title">{{ data.title }}</div>
    <div class="approval-status" :class="data.status">状态：{{ statusText }}</div>
    <div v-if="data.status === 'pending'" class="approval-actions">
      <button class="btn approve" @click="handleApprove">批准</button>
      <button class="btn reject" @click="handleReject">拒绝</button>
    </div>
  </div>
</template>

<script setup lang="ts">
  import { computed } from "vue"

  const props = defineProps<{
    data: {
      type: string
      title: string
      requestId: string
      status: "pending" | "approved" | "rejected"
      requester: string
      description: string
    }
  }>()

  const statusText = computed(() => {
    const map = { pending: "待审批", approved: "已批准", rejected: "已拒绝" }
    return map[props.data.status]
  })

  const handleApprove = () => {
    console.log("Approve:", props.data.requestId)
    // 调用审批 API
  }

  const handleReject = () => {
    console.log("Reject:", props.data.requestId)
  }
</script>
```

**2. 在 CustomMessageRenderer 中注册**

```vue
<ChartWidget v-if="block.data.type === 'chart'" :data="block.data" />
<IframeWidget v-else-if="block.data.type === 'iframe'" :data="block.data" />
<FormWidget v-else-if="block.data.type === 'form'" :data="block.data" />
<!-- 新增：审批组件 -->
<ApprovalWidget v-else-if="block.data.type === 'approval'" :data="block.data" />
```

**3. 更新系统 Prompt**

在系统 Prompt 的组件列表中补充新组件的格式描述，让 AI 知道如何使用它。

### 自定义组件开发规范

| 规范         | 说明                                                         |
| ------------ | ------------------------------------------------------------ |
| Props 设计   | 组件统一通过 `data` prop 接收 AI 输出的 JSON 数据           |
| 类型定义     | 为 `data` 定义 TypeScript 接口，明确每个字段的类型和是否必填 |
| 默认值处理   | 所有可选字段在模板中提供兜底值，避免因数据缺失导致渲染异常  |
| 样式隔离     | 使用 `scoped` 样式，避免污染全局样式                         |
| 性能优化     | 复杂组件（如图表）使用 `shallowRef` 避免不必要的响应式开销  |
| 安全考虑     | iframe 组件使用 `sandbox` 属性限制第三方页面权限             |

---

## 文件结构建议

```
your-project/
├── src/
│   └── components/
│       └── custom-widgets/
│           ├── CustomMessageRenderer.vue  ← 消息渲染器（必须实现）
│           ├── ChartWidget.vue            ← 图表组件
│           ├── IframeWidget.vue           ← iframe 组件
│           ├── FormWidget.vue             ← 表单组件
│           └── ...更多自定义组件
```

> `parseCustomBlocks` 和相关类型定义直接从 `@blueking/ai-blueking` 引入，**无需在项目中维护工具函数**。

---

## 相关文档

- [@blueking/chat-x](/api/chat-x/components) - 原子对话 UI 组件库
- [@blueking/ai-blueking](/api/ai-blueking/chatbot) - 小鲸业务组件
- [侧栏 Tab 自定义渲染](/guide/core-features/side-render-customization) — 执行情况侧栏节点详情等（≥ v2.1.4-beta.7）
- [ECharts 文档](https://echarts.apache.org/zh/index.html) - 图表配置参考
