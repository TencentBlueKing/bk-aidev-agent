<template>
  <div class="slot-demo-view">
    <div class="view-header">
      <h2>自定义消息渲染 (message slot)</h2>
      <p class="view-desc">
        通过 <code>#message</code> 插槽接管消息渲染，支持在 AI 回复中嵌入自定义 Vue 组件（图表、iframe、交互表单等）
      </p>
    </div>

    <!-- Prompt 说明 -->
    <div class="prompt-guide">
      <div class="guide-title">Prompt 指南</div>
      <div class="guide-desc">
        让大模型在回复中使用 <code>```custom-component</code> 代码块包裹 JSON 数据，组件会自动识别并渲染：
      </div>
      <pre class="guide-code"><code>{{ promptExample }}</code></pre>
    </div>

    <!-- 效果预览 -->
    <div class="demo-section">
      <div class="demo-title">效果预览</div>
      <div class="demo-desc">点击按钮查看不同类型自定义组件的渲染效果</div>
      <div class="demo-actions">
        <button
          v-for="(_, key) in demoMessages"
          :key="key"
          class="demo-btn"
          :class="{ active: activeDemo === key }"
          @click="activeDemo = key as string"
        >
          {{ demoLabels[key as string] }}
        </button>
      </div>

      <!-- 渲染区域 -->
      <div class="demo-render-area">
        <CustomMessageRenderer :message="activeMessage" />
      </div>
    </div>

    <!-- 使用说明 -->
    <div class="usage-section">
      <div class="usage-title">接入步骤</div>
      <div class="usage-steps">
        <div class="usage-step">
          <span class="step-num">1</span>
          <div class="step-content">
            <strong>配置 Prompt</strong> — 告诉 AI 使用 <code>```custom-component</code> 代码块输出结构化 JSON 数据
          </div>
        </div>
        <div class="usage-step">
          <span class="step-num">2</span>
          <div class="step-content">
            <strong>解析消息</strong> — 使用 <code>parseCustomBlocks()</code> 将消息拆分为普通文本和自定义组件片段
          </div>
        </div>
        <div class="usage-step">
          <span class="step-num">3</span>
          <div class="step-content">
            <strong>渲染组件</strong> — 在 <code>#message</code> 插槽中，普通文本用
            <code>MessageRender</code> 渲染，自定义块用对应的 Vue 组件渲染
          </div>
        </div>
      </div>
    </div>

    <!-- 代码示例 -->
    <div class="code-section">
      <div class="code-title">使用示例</div>
      <div class="code-block">
        <pre class="guide-code"><code>{{ codeExample }}</code></pre>
      </div>
    </div>

    <!-- AIBlueking 集成模式示例 — 点击右下角悬浮球测试 -->
    <AIBlueking
      :hello-text="'你好！请按照页面上方的 Prompt 指南，让我输出图表、iframe 或表单内容来测试自定义渲染。'"
      :title="'自定义渲染 Demo'"
      :url="apiUrl"
    >
      <template #message="{ message }">
        <CustomMessageRenderer :message="message" />
      </template>
    </AIBlueking>
  </div>
</template>

<script setup lang="ts">
  import { computed, ref } from 'vue';

  import AIBlueking from '@blueking/ai-blueking';
  import { MessageRole, MessageStatus } from '@blueking/chat-helper';

  import CustomMessageRenderer from '../components/custom-widgets/CustomMessageRenderer.vue';

  import type { Message } from '@blueking/chat-x';

  const apiUrl = import.meta.env.VITE_API_URL || '';
  const activeDemo = ref('chart');

  const demoLabels: Record<string, string> = {
    chart: '图表',
    iframe: 'iframe 嵌入',
    form: '交互表单',
    mixed: '混合内容',
  };

  const promptExample = `你是一个数据分析助手。当需要展示图表数据时，请使用以下格式：

\`\`\`custom-component
{"type": "chart", "chartType": "bar", "title": "销售数据", "data": {"labels": ["Q1","Q2","Q3","Q4"], "values": [120,200,150,180]}}
\`\`\`

当需要嵌入外部页面时：

\`\`\`custom-component
{"type": "iframe", "src": "https://example.com/dashboard", "height": 400}
\`\`\`

当需要用户交互确认时：

\`\`\`custom-component
{"type": "form", "title": "确认操作", "fields": [{"label": "环境", "type": "select", "options": ["dev","prod"]}], "actions": ["确认","取消"]}
\`\`\``;

  const demoMessages: Record<string, string> = {
    chart: `根据你的数据，以下是各季度的销售趋势分析：

\`\`\`custom-component
{"type": "chart", "chartType": "bar", "title": "2024 年季度销售额（万元）", "data": {"labels": ["Q1", "Q2", "Q3", "Q4"], "values": [120, 200, 150, 180]}}
\`\`\`

可以看到 Q2 表现最好，Q3 有所回落，Q4 回升。建议重点关注 Q3 的下滑原因。`,

    iframe: `已为你打开监控面板，可以实时查看系统状态：

\`\`\`custom-component
{"type": "iframe", "src": "https://www.example.com", "height": 350, "title": "系统监控面板"}
\`\`\`

面板每 30 秒自动刷新，如需调整告警阈值请告诉我。`,

    form: `请确认以下部署配置：

\`\`\`custom-component
{"type": "form", "title": "部署确认", "fields": [{"label": "环境", "type": "select", "options": ["开发环境", "测试环境", "生产环境"]}, {"label": "版本号", "type": "text", "placeholder": "v1.2.3"}], "actions": ["确认部署", "取消"]}
\`\`\`

确认后将自动执行部署流程。`,

    mixed: `以下是本次分析报告：

## 数据概览
本次分析覆盖了 4 个季度的销售数据，整体呈上升趋势。

### 季度对比图表
\`\`\`custom-component
{"type": "chart", "chartType": "bar", "title": "各季度销售额对比", "data": {"labels": ["Q1", "Q2", "Q3", "Q4"], "values": [85, 120, 95, 140]}}
\`\`\`

### 详细报告
如需查看完整数据报告，可以访问：
\`\`\`custom-component
{"type": "iframe", "src": "https://www.example.com", "height": 300, "title": "详细数据报告"}
\`\`\`

### 操作确认
\`\`\`custom-component
{"type": "form", "title": "是否导出报告？", "fields": [{"label": "格式", "type": "select", "options": ["PDF", "Excel", "CSV"]}], "actions": ["导出", "取消"]}
\`\`\`

以上就是本次分析的完整结果。`,
  };

  // 构造模拟的 Message 对象用于渲染预览
  const activeMessage = computed<Message>(
    () =>
      ({
        id: 'demo',
        messageId: 'demo',
        role: MessageRole.Assistant,
        content: demoMessages[activeDemo.value] || '',
        status: MessageStatus.Complete,
      }) as unknown as Message,
  );

  const codeExample = `<template>
  <ChatBot :url="apiUrl">
    <!-- 使用 #message 插槽自定义消息渲染 -->
    <template #message="{ message }">
      <CustomMessageRenderer :message="message" />
    </template>
  </ChatBot>
</template>

<script setup>
import { ChatBot } from '@blueking/ai-blueking';
import CustomMessageRenderer from '../components/CustomMessageRenderer.vue';
<\/script>

<!-- CustomMessageRenderer.vue 核心逻辑 -->
<script setup>
import { computed } from 'vue';
import { MessageRender } from '@blueking/chat-x';
import { parseCustomBlocks } from './parse-custom-blocks';
import ChartWidget from './ChartWidget.vue';
import IframeWidget from '../components/IframeWidget.vue';
import FormWidget from '../components/FormWidget.vue';

const props = defineProps({ message: Object });
const blocks = computed(() => parseCustomBlocks(props.message.content || ''));
<\/script>

<template>
  <template v-for="(block, i) in blocks" :key="i">
    <!-- 普通文本用 MessageRender 渲染 -->
    <MessageRender
      v-if="block.type === 'text'"
      :message="{ ...message, content: block.content }"
    />
    <!-- 自定义组件分发渲染 -->
    <ChartWidget v-else-if="block.data.type === 'chart'" :data="block.data" />
    <IframeWidget v-else-if="block.data.type === 'iframe'" :data="block.data" />
    <FormWidget v-else-if="block.data.type === 'form'" :data="block.data" />
  </template>
</template>`;
</script>

<style scoped>
  .slot-demo-view {
    max-width: 900px;
  }

  .view-header {
    margin-bottom: 24px;
  }

  .view-header h2 {
    margin: 0 0 8px;
    font-size: 20px;
    font-weight: 600;
    color: #313238;
  }

  .view-desc {
    margin: 0;
    font-size: 13px;
    line-height: 20px;
    color: #63656e;
  }

  .view-desc code {
    padding: 1px 6px;
    font-size: 12px;
    color: #3a84ff;
    background: #f0f5ff;
    border-radius: 3px;
  }

  /* Prompt Guide */
  .prompt-guide {
    padding: 16px;
    margin-bottom: 20px;
    background: #fff;
    border: 1px solid #dcdee5;
    border-radius: 8px;
  }

  .guide-title {
    margin-bottom: 8px;
    font-size: 14px;
    font-weight: 600;
    color: #313238;
  }

  .guide-desc {
    margin-bottom: 12px;
    font-size: 13px;
    color: #63656e;
  }

  .guide-desc code {
    padding: 1px 6px;
    font-size: 12px;
    color: #3a84ff;
    background: #f0f5ff;
    border-radius: 3px;
  }

  .guide-code {
    padding: 12px 16px;
    overflow-x: auto;
    font-size: 12px;
    line-height: 18px;
    color: #313238;
    background: #f5f7fa;
    border-radius: 4px;
  }

  /* Demo Section */
  .demo-section {
    padding: 16px;
    margin-bottom: 20px;
    background: #fff;
    border: 1px solid #dcdee5;
    border-radius: 8px;
  }

  .demo-title {
    margin-bottom: 4px;
    font-size: 14px;
    font-weight: 600;
    color: #313238;
  }

  .demo-desc {
    margin-bottom: 12px;
    font-size: 13px;
    color: #63656e;
  }

  .demo-actions {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-bottom: 16px;
  }

  .demo-btn {
    height: 32px;
    padding: 0 16px;
    font-size: 13px;
    color: #3a84ff;
    cursor: pointer;
    background: #f0f5ff;
    border: 1px solid #d4e8ff;
    border-radius: 4px;
    transition: all 0.15s;
  }

  .demo-btn:hover,
  .demo-btn.active {
    color: #fff;
    background: #3a84ff;
    border-color: #3a84ff;
  }

  .demo-render-area {
    padding: 16px;
    background: #fafbfd;
    border: 1px solid #f0f1f5;
    border-radius: 6px;
  }

  /* Usage Section */
  .usage-section {
    padding: 16px;
    margin-bottom: 20px;
    background: #fff;
    border: 1px solid #dcdee5;
    border-radius: 8px;
  }

  .usage-title {
    margin-bottom: 12px;
    font-size: 14px;
    font-weight: 600;
    color: #313238;
  }

  .usage-steps {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .usage-step {
    display: flex;
    gap: 12px;
    align-items: flex-start;
  }

  .step-num {
    display: flex;
    flex-shrink: 0;
    align-items: center;
    justify-content: center;
    width: 24px;
    height: 24px;
    font-size: 12px;
    font-weight: 600;
    color: #fff;
    background: #3a84ff;
    border-radius: 50%;
  }

  .step-content {
    font-size: 13px;
    line-height: 22px;
    color: #63656e;
  }

  .step-content strong {
    color: #313238;
  }

  .step-content code {
    padding: 1px 6px;
    font-size: 12px;
    color: #3a84ff;
    background: #f0f5ff;
    border-radius: 3px;
  }

  /* Code Section */
  .code-section {
    padding: 16px;
    background: #fff;
    border: 1px solid #dcdee5;
    border-radius: 8px;
  }

  .code-title {
    margin-bottom: 12px;
    font-size: 14px;
    font-weight: 600;
    color: #313238;
  }

  .code-block {
    overflow: hidden;
    border-radius: 6px;
  }
</style>
