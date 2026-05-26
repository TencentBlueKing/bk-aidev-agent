<template>
  <div class="side-render-view">
    <div class="view-header">
      <h2>侧栏渲染 (side-render / tab-render)</h2>
      <p class="view-desc">
        可交互文档：在真实 FlowAgent SSE 下对比两种接入——<strong>仅自定义侧栏 UI</strong>（默认详情接口），或
        <strong>UI + 详情拉取均自定义</strong>（<code>onCustomTabChange</code>）。对话区仍由内置
        <code>FlowAgentContent</code> 负责，请勿覆盖 <code>#message</code> 插槽。
      </p>
      <p
        v-if="flowAgentUrl"
        class="view-env"
      >
        本页演示后台（Playground 本地配置）：<code>{{ flowAgentUrl }}</code>
      </p>
    </div>

    <div class="scenario-switcher">
      <div
        class="scenario-tabs"
        role="tablist"
        aria-label="侧栏渲染接入场景"
      >
        <button
          v-for="item in scenarios"
          :key="item.id"
          type="button"
          role="tab"
          class="scenario-tab"
          :class="{ 'is-active': activeScenario === item.id }"
          :aria-selected="activeScenario === item.id"
          @click="activeScenario = item.id"
        >
          <span class="scenario-tab__badge">{{ item.badge }}</span>
          <span class="scenario-tab__title">{{ item.title }}</span>
          <span class="scenario-tab__desc">{{ item.shortDesc }}</span>
        </button>
      </div>

      <div class="scenario-summary">
        <div class="scenario-summary__header">
          <span class="scenario-summary__badge">{{ activeScenarioMeta.badge }}</span>
          <h3>{{ activeScenarioMeta.title }}</h3>
        </div>
        <p>{{ activeScenarioMeta.longDesc }}</p>
        <ul class="scenario-summary__props">
          <li
            v-for="prop in activeScenarioMeta.props"
            :key="prop.name"
          >
            <code>{{ prop.name }}</code>
            <span>{{ prop.note }}</span>
          </li>
        </ul>
      </div>
    </div>

    <div class="demo-section demo-section--live">
      <div class="demo-title">交互演示</div>
      <p class="demo-desc">
        当前为 <strong>{{ activeScenarioMeta.badge }}</strong>。操作 <code>ChatBot</code>（切换场景会重建实例）：发送对话 →
        <code>flow_agent_result</code> → 展开「执行情况」→ 点击节点「详情」。下方「接入代码」会随场景同步切换。
      </p>
      <SideRenderLiveDemo :active-scenario="activeScenario" />
    </div>

    <div class="usage-section">
      <div class="usage-title">后端 SSE 事件（示例）</div>
      <pre class="guide-code"><code>{{ sseExample }}</code></pre>
    </div>

    <div class="usage-section">
      <div class="usage-title">接入步骤 · {{ activeScenarioMeta.badge }}</div>
      <div class="usage-steps">
        <div
          v-for="(step, index) in integrationSteps"
          :key="index"
          class="usage-step"
        >
          <span class="step-num">{{ index + 1 }}</span>
          <div
            class="step-content"
            v-html="step"
          />
        </div>
      </div>
      <p class="usage-note">
        不要覆盖 <code>#message</code> 插槽来渲染 FlowAgent。Playground 源码：
        <code>playground/components/side-render/</code>；主站文档见
        <code>web/docs/guide/core-features/side-render-customization.md</code>。
      </p>
    </div>

    <div class="usage-section">
      <div class="usage-title">数据流 · {{ activeScenarioMeta.badge }}</div>
      <div class="usage-steps">
        <div
          v-for="(step, index) in dataFlowSteps"
          :key="index"
          class="usage-step"
        >
          <span class="step-num">{{ index + 1 }}</span>
          <div
            class="step-content"
            v-html="step"
          />
        </div>
      </div>
    </div>

    <SideRenderCodeSection :active-scenario="activeScenario" />
  </div>
</template>

<script setup lang="ts">
  import { computed, ref } from 'vue';

  import SideRenderCodeSection from '../components/side-render/SideRenderCodeSection.vue';
  import SideRenderLiveDemo from '../components/side-render/SideRenderLiveDemo.vue';
  import {
    getSideRenderScenarioById,
    SIDE_RENDER_SCENARIOS,
    type SideRenderScenarioId,
  } from '../components/side-render/side-render-scenarios';

  const flowAgentUrl = import.meta.env.VITE_FLOW_AGENT_URL || '';
  const scenarios = SIDE_RENDER_SCENARIOS;
  const activeScenario = ref<SideRenderScenarioId>('default-api');

  const activeScenarioMeta = computed(() => getSideRenderScenarioById(activeScenario.value));

  const sseExample = `data: {"type":"CUSTOM","name":"flow_agent_start","value":{"task_id":"10421"}}
data: {"type":"CUSTOM","name":"flow_agent_result","value":{"task_id":10421,"task_name":"...","task_state":"FINISHED","nodes":{...},"statistics":{...}}}
data: {"type":"CUSTOM","name":"flow_agent_end","value":{"task_id":"10421","task_outputs":[]}}`;

  const integrationStepsByScenario: Record<SideRenderScenarioId, string[]> = {
    'default-api': [
      '新建 <code>CustomTabContent.vue</code>（保留 <code>#locateButton</code>），根据 <code>loading</code>、<code>data</code> 等 props 渲染',
      '实现 <code>useSideRenderHandlers</code>，提供 <code>getSideRenderComponent</code>（+ 可选 <code>getSideTabRenderComponent</code>）',
      '页面挂载 <code>ChatBot</code>，传入 <code>url</code> 与上述 handlers，<strong>不要传</strong> <code>onCustomTabChange</code>',
      '发送对话 → 点击节点「详情」→ 详情由 ChatBot 内置 <code>getFlowAgentTaskNodeInfo</code> 写入 <code>props.data</code>',
    ],
    'custom-fetch': [
      '侧栏内容组件与场景 1 相同（<code>CustomTabContent.vue</code>）',
      '实现 <code>useSideRenderHandlers</code>（侧栏 UI 映射）',
      '新增 <code>createOnCustomTabChange</code>（或等价逻辑），在回调中 <code>fetch</code> 自有详情接口并 <code>return</code> 结果',
      '页面挂载 <code>ChatBot</code>，同时传入 <code>getSideRenderComponent</code> 与 <code>on-custom-tab-change</code>（内置拉取不再执行）',
      '发送对话 → 点击「详情」→ 在 Network 与侧栏内核对自定义请求与 <code>props.data</code>',
    ],
  };

  const dataFlowStepsByScenario: Record<SideRenderScenarioId, string[]> = {
    'default-api': [
      'chat-helper 解析 <code>flow_agent_*</code> → Activity 消息',
      '<strong>FlowAgentContent</strong> 点击「详情」→ <code>addCustomTab</code>',
      '<strong>getSideRenderComponent</strong> 渲染自定义侧栏 UI',
      '<strong>ChatBot</strong> 内置 <code>GET flow_agent/{taskId}/task_node_info/{nodeId}/</code> → <code>props.data</code>',
    ],
    'custom-fetch': [
      'chat-helper 解析 <code>flow_agent_*</code> → Activity 消息',
      '<strong>FlowAgentContent</strong> 点击「详情」→ <code>addCustomTab</code>（<code>loading: true</code>）',
      '<strong>getSideRenderComponent</strong> 渲染自定义侧栏 UI（展示 loading）',
      '<strong>onCustomTabChange(tab)</strong> 业务方请求详情 → 返回值合并为 <code>props.data</code>，<code>loading: false</code>',
    ],
  };

  const integrationSteps = computed(() => integrationStepsByScenario[activeScenario.value]);
  const dataFlowSteps = computed(() => dataFlowStepsByScenario[activeScenario.value]);
</script>

<style scoped>
  .side-render-view {
    max-width: 960px;
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

  .view-desc,
  .view-env {
    margin: 0 0 8px;
    font-size: 13px;
    line-height: 22px;
    color: #63656e;
  }

  .view-desc code,
  .view-env code,
  .scenario-summary__props code,
  :deep(.step-content code),
  .usage-note code,
  .demo-desc code,
  .guide-code {
    padding: 1px 6px;
    font-size: 12px;
    color: #3a84ff;
    background: #f0f5ff;
    border-radius: 3px;
  }

  .scenario-switcher {
    margin-bottom: 20px;
    overflow: hidden;
    background: #fff;
    border: 1px solid #dcdee5;
    border-radius: 8px;
  }

  .scenario-tabs {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    border-bottom: 1px solid #dcdee5;
  }

  .scenario-tab {
    display: flex;
    flex-direction: column;
    gap: 4px;
    align-items: flex-start;
    padding: 14px 16px;
    text-align: left;
    cursor: pointer;
    background: #f5f7fa;
    border: none;
    border-right: 1px solid #dcdee5;
    transition: background 0.15s ease;

    &:last-child {
      border-right: none;
    }

    &:hover {
      background: #eef2f8;
    }

    &.is-active {
      background: #fff;
      box-shadow: inset 0 3px 0 #3a84ff;
    }
  }

  .scenario-tab__badge {
    font-size: 11px;
    font-weight: 600;
    color: #3a84ff;
  }

  .scenario-tab__title {
    font-size: 14px;
    font-weight: 600;
    color: #313238;
  }

  .scenario-tab__desc {
    font-size: 12px;
    line-height: 18px;
    color: #979ba5;
  }

  .scenario-summary {
    padding: 16px;
  }

  .scenario-summary__header {
    display: flex;
    gap: 10px;
    align-items: center;
    margin-bottom: 8px;

    h3 {
      margin: 0;
      font-size: 15px;
      font-weight: 600;
      color: #313238;
    }
  }

  .scenario-summary__badge {
    padding: 2px 8px;
    font-size: 11px;
    font-weight: 600;
    color: #3a84ff;
    background: #e1ecff;
    border-radius: 10px;
  }

  .scenario-summary p {
    margin: 0 0 12px;
    font-size: 13px;
    line-height: 22px;
    color: #63656e;
  }

  .scenario-summary__props {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    padding: 0;
    margin: 0;
    list-style: none;

    li {
      display: inline-flex;
      gap: 6px;
      align-items: center;
      padding: 4px 10px;
      font-size: 12px;
      color: #63656e;
      background: #f5f7fa;
      border-radius: 4px;
    }
  }

  .demo-section,
  .usage-section {
    padding: 16px;
    margin-bottom: 20px;
    background: #fff;
    border: 1px solid #dcdee5;
    border-radius: 8px;
  }

  .demo-section--live {
    padding-bottom: 16px;
  }

  .view-desc strong,
  :deep(.step-content strong) {
    font-weight: 600;
    color: #313238;
  }

  .demo-title,
  .usage-title {
    margin-bottom: 8px;
    font-size: 14px;
    font-weight: 600;
    color: #313238;
  }

  .demo-desc {
    margin-bottom: 12px;
    font-size: 13px;
    color: #63656e;
  }

  .usage-note {
    margin: 12px 0 0;
    font-size: 12px;
    line-height: 20px;
    color: #979ba5;
  }

  .guide-code {
    display: block;
    padding: 12px 16px;
    overflow-x: auto;
    font-size: 12px;
    line-height: 18px;
    color: #313238;
    background: #f5f7fa;
    border-radius: 4px;
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

  :deep(.step-content) {
    font-size: 13px;
    line-height: 22px;
    color: #63656e;
  }
</style>
