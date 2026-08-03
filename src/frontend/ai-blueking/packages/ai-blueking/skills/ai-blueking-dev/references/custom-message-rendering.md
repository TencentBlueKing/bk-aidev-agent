# 自定义消息渲染

在 AI 对话中嵌入图表、表单、iframe 等任意自定义组件。ai-blueking 提供渲染框架和解析机制，具体组件由业务方实现。

> 📂 **本文示例即取自可运行的 playground 文件**（可直接运行对照）：
> - `packages/ai-blueking/playground/components/custom-widgets/` — `CustomMessageRenderer.vue` + `ChartWidget/IframeWidget/FormWidget.vue`，配套视图 `views/CustomMessageSlotView.vue`
> - `packages/chat-x/playground/custom-message/` — 更接近生产的示例：`stock.ts` / `stock-echarts.ts`（ECharts）/ `tree-map.ts`；以及 `custom-content.vue`（`ContentRender` 默认插槽扩展）
>
> 完整索引见 [Playground 实例索引](playground-examples.md)。

---

## 核心机制

```
AI 输出 → ```custom-component 代码块（JSON）→ parseCustomBlocks() 解析 → CustomMessageRenderer 分发 → 业务组件渲染
```

**架构**：

```
ChatBot / AIBlueking
  └── #message slot
        └── CustomMessageRenderer（你实现）
              ├── TextBlock → MessageRender（默认渲染）
              └── CustomBlock → 按 data.type 分发
                    ├── chart → ChartWidget
                    ├── iframe → IframeWidget
                    ├── form → FormWidget
                    └── ... 任意扩展
```

---

## 快速开始

### 1. 解析器

`parseCustomBlocks` 从 `@blueking/ai-blueking` 导出，将消息内容解析为文本块和自定义组件块：

```typescript
import { parseCustomBlocks, type ContentBlock, type CustomBlock, type TextBlock } from '@blueking/ai-blueking';

const blocks = parseCustomBlocks(message.content);
// ContentBlock[] = TextBlock[] | CustomBlock[]
// TextBlock  = { type: 'text', content: string }
// CustomBlock = { type: 'custom', data: Record<string, unknown>, raw: string }
```

### 2. CustomMessageRenderer

组合解析器和业务组件，处理消息分发：

```vue
<!-- CustomMessageRenderer.vue -->
<template>
  <!-- 非 Assistant 消息（含 HITL 的 MessageRole.Interrupt）交给默认渲染，
       必须透传 onInterruptResume，否则审批/提问/节点重试跳过失效 -->
  <MessageRender
    v-if="message.role !== MessageRole.Assistant"
    :message="message"
    :on-interrupt-resume="onInterruptResume"
  />

  <div v-else class="custom-message-renderer">
    <template v-for="(block, index) in blocks" :key="index">
      <MessageRender
        v-if="block.type === 'text'"
        :message="{ ...message, content: block.content }"
      />
      <div v-else-if="block.type === 'custom'" class="custom-block-wrapper">
        <!-- 按 block.data.type 分发你的组件 -->
        <ChartWidget v-if="block.data.type === 'chart'" :data="block.data" />
        <IframeWidget v-else-if="block.data.type === 'iframe'" :data="block.data" />
        <FormWidget v-else-if="block.data.type === 'form'" :data="block.data" />
        <div v-else class="unknown-block">未知组件类型: {{ block.data.type }}</div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { MessageRender, MessageRole } from '@blueking/chat-x';
import { parseCustomBlocks } from '@blueking/ai-blueking';
import type { Message, OnInterruptResume } from '@blueking/chat-x';

// onInterruptResume 由 #message 插槽作用域传入，需一路透传（HITL 依赖）
const props = defineProps<{ message: Message; onInterruptResume?: OnInterruptResume }>();
const blocks = computed(() => parseCustomBlocks(props.message.content || ''));
</script>
```

### 3. 接入 ChatBot / AIBlueking

```vue
<template>
  <ChatBot :chat-helper="chatHelper" :url="apiUrl">
    <!-- 透传 onInterruptResume，保证 HITL 中断卡片可交互 -->
    <template #message="{ message, onInterruptResume }">
      <CustomMessageRenderer :message="message" :on-interrupt-resume="onInterruptResume" />
    </template>
  </ChatBot>
</template>
```

> **HITL 注意**：`#message` 插槽作用域含 `message`、`messageToolsStatus`、`onInterruptResume` 三个参数。自定义渲染器只要还会渲染非 Assistant 消息（中断消息 `MessageRole.Interrupt` 即属此类），就必须把 `onInterruptResume` 透传给内部 `MessageRender`。详见 [HITL 人机协同](hitl.md)。

---

## AI 输出格式

AI 在回复中使用 ` ```custom-component ` 代码块输出 JSON：

### 单个组件

````
```custom-component
{"type": "chart", "chartType": "bar", "title": "销售数据", "data": {"labels": ["Q1","Q2","Q3","Q4"], "values": [100,150,120,180]}}
```
````

### 混合内容（文本 + 多个组件）

````
这是本月销售分析报告：

```custom-component
{"type": "chart", "chartType": "bar", "title": "月度销售额", "data": {...}}
```

**关键发现：**
- Q2 增长率提升 15%

```custom-component
{"type": "form", "title": "反馈收集", "fields": [...], "actions": [...]}
```
````

---

## 组件示例

### ChartWidget（图表）

```vue
<!-- ChartWidget.vue -->
<template>
  <div class="chart-widget">
    <div class="chart-title">{{ data.title || '图表' }}</div>
    <div ref="chartRef" class="chart-container" />
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref, watch } from 'vue';
import * as echarts from 'echarts';

const props = defineProps<{
  data: {
    title?: string;
    chartType?: string;
    data?: { labels?: string[]; values?: number[] };
  };
}>();

const chartRef = ref<HTMLElement>();
let chart: echarts.ECharts | null = null;

const renderChart = () => {
  if (!chartRef.value) return;
  if (!chart) chart = echarts.init(chartRef.value);
  const labels = props.data?.data?.labels || [];
  const values = props.data?.data?.values || [];
  chart.setOption({
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: labels },
    yAxis: { type: 'value' },
    series: [{ type: props.data?.chartType || 'bar', data: values }],
  });
};

onMounted(renderChart);
watch(() => props.data, renderChart, { deep: true });
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
.chart-container { width: 100%; height: 200px; }
</style>
```

### IframeWidget（嵌入页面）

```vue
<!-- IframeWidget.vue -->
<template>
  <div class="iframe-widget">
    <div class="iframe-header">
      <span class="iframe-title">{{ data.title || '嵌入页面' }}</span>
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
defineProps<{ data: { title?: string; src: string; height?: number } }>();
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
.iframe-title { font-size: 13px; font-weight: 500; color: #313238; }
.iframe-link { font-size: 12px; color: #3a84ff; text-decoration: none; }
.iframe-content { display: block; width: 100%; border: none; }
</style>
```

### FormWidget（交互表单）

```vue
<!-- FormWidget.vue -->
<template>
  <div class="form-widget">
    <div class="form-title">{{ data.title || '交互表单' }}</div>
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
import { reactive } from 'vue';

const props = defineProps<{
  data: {
    title?: string;
    fields?: Array<{ label: string; type?: string; options?: string[]; placeholder?: string }>;
    actions?: string[];
  };
}>();

const formValues = reactive<Record<string, string>>({});
(props.data.fields || []).forEach(field => {
  formValues[field.label] = field.options?.[0] || '';
});

const handleAction = (action: string) => {
  console.log('[FormWidget] action:', action, 'values:', { ...formValues });
};
</script>

<style scoped>
.form-widget { padding: 16px; background: #fafbfd; border: 1px solid #e1ecff; border-radius: 8px; }
.form-title { margin-bottom: 12px; font-size: 14px; font-weight: 600; color: #313238; }
.form-fields { display: flex; flex-direction: column; gap: 10px; margin-bottom: 16px; }
.form-field { display: flex; gap: 8px; align-items: center; }
.field-label { flex-shrink: 0; width: 80px; font-size: 13px; color: #63656e; }
.field-input { flex: 1; height: 32px; padding: 0 10px; font-size: 13px; border: 1px solid #dcdee5; border-radius: 4px; }
.form-actions { display: flex; gap: 8px; justify-content: flex-end; }
.form-btn { height: 32px; padding: 0 16px; font-size: 13px; color: #63656e; background: #fff; border: 1px solid #dcdee5; border-radius: 4px; cursor: pointer; }
.form-btn.primary { color: #fff; background: #3a84ff; border-color: #3a84ff; }
</style>
```

---

## 扩展新组件类型

1. 创建组件，通过 `data` prop 接收 JSON 数据
2. 在 `CustomMessageRenderer` 中添加 `v-else-if` 判断
3. 更新 AI Prompt 告知新格式

```vue
<!-- CustomMessageRenderer.vue 中添加 -->
<TimelineWidget v-else-if="block.data.type === 'timeline'" :data="block.data" />
<ApprovalWidget v-else-if="block.data.type === 'approval'" :data="block.data" />
```

---

## 组件设计原则

- **Props**：通过 `data` prop 接收 AI 输出的 JSON，定义 TypeScript 接口
- **样式**：使用 `scoped` 样式隔离
- **安全**：iframe 使用 `sandbox` 属性限制权限
- **性能**：复杂图表使用 `shallowRef` 避免不必要的响应式开销

---

## Prompt 指南

在系统 Prompt 中告知 AI 输出格式：

```
当需要展示数据时，使用 custom-component 代码块：

图表：```custom-component\n{"type":"chart","chartType":"bar","title":"标题","data":{"labels":[...],"values":[...]}}\n```
iframe：```custom-component\n{"type":"iframe","src":"URL","height":400}\n```
表单：```custom-component\n{"type":"form","title":"标题","fields":[...],"actions":[...]}\n```

注意：JSON 必须合法，可在一条消息中混合文本和多个组件。
```

---

## 常见问题

| 问题 | 原因 | 解决 |
|------|------|------|
| 组件不渲染 | JSON 解析失败 | 检查 `custom-component` 代码块内 JSON 是否合法 |
| 样式冲突 | 未使用 scoped | 组件添加 `<style scoped>` |
| iframe 无法交互 | sandbox 限制过严 | 按需添加 `allow-*` 权限 |
| 用户消息工具失效 | 未透传 `#message` slot props | 见 SKILL.md `#message 插槽透传` 章节 |
