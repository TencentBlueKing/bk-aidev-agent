<template>
  <div class="side-render-view">
    <header class="view-header">
      <h2>侧栏渲染 (side-render / tab-render)</h2>
      <p class="view-desc">
        左侧试跑 Demo，右侧查看接入说明与代码。请勿覆盖 <code>#message</code> 插槽。
        <span
          v-if="flowAgentUrl"
          class="view-env"
        >
          API：<code>{{ flowAgentUrl }}</code>
        </span>
      </p>
    </header>

    <div class="side-render-workbench">
      <aside class="workbench-left">
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

          <div class="scenario-summary scenario-summary--compact">
            <ul class="scenario-summary__try">
              <li
                v-for="(step, index) in activeScenarioMeta.trySteps"
                :key="index"
              >
                {{ step }}
              </li>
            </ul>
          </div>
        </div>

        <div class="demo-panel">
          <p class="demo-panel__hint">
            发送对话 → 展开「执行情况」→ 点击节点「详情」
          </p>
          <SideRenderLiveDemo :active-scenario="activeScenario" />
        </div>
      </aside>

      <div class="workbench-right">
        <section class="doc-panel">
          <h3 class="doc-panel__title">快速接入 · {{ activeScenarioMeta.badge }}</h3>
          <p class="doc-panel__lead">{{ activeScenarioMeta.longDesc }}</p>
          <ul class="doc-panel__props">
            <li
              v-for="prop in activeScenarioMeta.props"
              :key="prop.name"
            >
              <code>{{ prop.name }}</code>
              <span>{{ prop.note }}</span>
            </li>
          </ul>
          <ol class="doc-panel__steps">
            <li
              v-for="(step, index) in integrationSteps"
              :key="index"
              v-html="step"
            />
          </ol>
        </section>

        <section class="doc-panel">
          <h3 class="doc-panel__title">数据流</h3>
          <ol class="doc-panel__steps doc-panel__steps--flow">
            <li
              v-for="(step, index) in dataFlowSteps"
              :key="index"
              v-html="step"
            />
          </ol>
        </section>

        <details class="doc-panel doc-panel--collapsible">
          <summary class="doc-panel__title doc-panel__title--summary">后端 SSE 事件（示例）</summary>
          <pre class="guide-code"><code>{{ sseExample }}</code></pre>
        </details>

        <SideRenderCodeSection
          embedded
          :active-scenario="activeScenario"
        />

        <p class="workbench-footnote">
          Playground：<code>playground/components/side-render/</code> · 主站文档：
          <code>web/docs/guide/core-features/side-render-customization.md</code>
        </p>
      </div>
    </div>
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
      '在 <code>ChatBot</code> / <code>AIBlueking</code> 上传入 <code>getSideRenderComponent</code>',
      '实现 <code>useSideRenderHandlers</code>，把 <code>tab.data.props</code> 映射给侧栏组件',
      '新建 <code>CustomTabContent.vue</code> 展示 <code>loading</code> 与 <code>data</code>',
      '<strong>不传</strong> <code>onCustomTabChange</code>，详情由内置接口写入 <code>props.data</code>',
    ],
    'custom-fetch': [
      '在入口组件上同时传入 <code>getSideRenderComponent</code> 与 <code>onCustomTabChange</code>',
      '在 <code>onCustomTabChange</code> 中取 <code>task_id</code> / <code>node_id</code>，请求详情并 <code>return</code> 数据',
      '侧栏组件直接读取 <code>props.data</code> 展示返回值',
      '发送对话 → 点击「详情」→ 在 Network 与侧栏内核对请求与数据',
    ],
  };

  const dataFlowStepsByScenario: Record<SideRenderScenarioId, string[]> = {
    'default-api': [
      'SSE <code>flow_agent_*</code> → Activity 消息',
      '点击「详情」→ <code>addCustomTab</code>',
      '<code>getSideRenderComponent</code> 渲染侧栏 UI',
      '内置详情接口 → <code>props.data</code>',
    ],
    'custom-fetch': [
      'SSE <code>flow_agent_*</code> → Activity 消息',
      '点击「详情」→ <code>addCustomTab</code>（<code>loading: true</code>）',
      '<code>getSideRenderComponent</code> 展示 loading',
      '<code>onCustomTabChange</code> 返回数据 → <code>props.data</code>，loading 结束',
    ],
  };

  const integrationSteps = computed(() => integrationStepsByScenario[activeScenario.value]);
  const dataFlowSteps = computed(() => dataFlowStepsByScenario[activeScenario.value]);
</script>

<style scoped>
  .side-render-view {
    display: flex;
    flex-direction: column;
    max-width: none;
    height: calc(100vh - 48px);
    max-height: calc(100vh - 48px);
    overflow: hidden;
  }

  .view-header {
    flex-shrink: 0;
    margin-bottom: 12px;
  }

  .view-header h2 {
    margin: 0 0 4px;
    font-size: 18px;
    font-weight: 600;
    color: #313238;
  }

  .view-desc {
    margin: 0;
    font-size: 12px;
    line-height: 20px;
    color: #63656e;
  }

  .view-env {
    margin-left: 8px;
    color: #979ba5;

    code {
      max-width: 280px;
      overflow: hidden;
      text-overflow: ellipsis;
      vertical-align: bottom;
      white-space: nowrap;
      display: inline-block;
    }
  }

  .view-desc code,
  .view-env code,
  .doc-panel__props code,
  .doc-panel__steps :deep(code),
  .workbench-footnote code,
  .demo-panel__hint code,
  .guide-code {
    padding: 1px 6px;
    font-size: 12px;
    color: #3a84ff;
    background: #f0f5ff;
    border-radius: 3px;
  }

  .side-render-workbench {
    display: grid;
    flex: 1;
    grid-template-columns: minmax(400px, 52%) minmax(0, 1fr);
    gap: 16px;
    min-height: 0;
    overflow: hidden;
  }

  .workbench-left {
    display: flex;
    flex-direction: column;
    gap: 10px;
    min-height: 0;
    overflow: hidden;
  }

  .workbench-right {
    display: flex;
    flex-direction: column;
    gap: 16px;
    min-width: 0;
    min-height: 0;
    overflow-y: auto;
  }

  .scenario-switcher {
    flex-shrink: 0;
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
    gap: 2px;
    align-items: flex-start;
    padding: 8px 12px;
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
    font-size: 13px;
    font-weight: 600;
    color: #313238;
  }

  .scenario-tab__desc {
    font-size: 12px;
    line-height: 18px;
    color: #979ba5;
  }

  .scenario-summary--compact {
    padding: 8px 12px;
  }

  .scenario-summary__try {
    padding: 0;
    padding-left: 16px;
    margin: 0;
    font-size: 11px;
    line-height: 18px;
    color: #63656e;
  }

  .demo-panel {
    display: flex;
    flex: 1;
    flex-direction: column;
    min-height: 0;
    padding: 10px 12px;
    background: #fff;
    border: 1px solid #dcdee5;
    border-radius: 8px;
  }

  .demo-panel__hint {
    flex-shrink: 0;
    margin: 0 0 8px;
    font-size: 11px;
    line-height: 18px;
    color: #979ba5;
  }

  .demo-panel :deep(.side-render-live-demo) {
    flex: 1;
    min-height: 0;
  }

  .doc-panel {
    padding: 16px;
    background: #fff;
    border: 1px solid #dcdee5;
    border-radius: 8px;
  }

  .doc-panel--collapsible {
    padding-top: 12px;
    padding-bottom: 12px;
  }

  .doc-panel__title {
    margin: 0 0 10px;
    font-size: 14px;
    font-weight: 600;
    color: #313238;
  }

  .doc-panel__title--summary {
    margin-bottom: 0;
    cursor: pointer;
    list-style: none;

    &::-webkit-details-marker {
      display: none;
    }

    &::before {
      display: inline-block;
      margin-right: 6px;
      content: '▸';
      transition: transform 0.15s ease;
    }
  }

  .doc-panel--collapsible[open] .doc-panel__title--summary::before {
    transform: rotate(90deg);
  }

  .doc-panel--collapsible .guide-code {
    margin-top: 12px;
  }

  .doc-panel__lead {
    margin: 0 0 12px;
    font-size: 13px;
    line-height: 22px;
    color: #63656e;
  }

  .doc-panel__props {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    padding: 0;
    margin: 0 0 14px;
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

  .doc-panel__steps {
    padding-left: 20px;
    margin: 0;
    font-size: 13px;
    line-height: 24px;
    color: #63656e;

    :deep(strong) {
      font-weight: 600;
      color: #313238;
    }
  }

  .doc-panel__steps--flow {
    list-style: decimal;
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

  .workbench-footnote {
    margin: 0;
    font-size: 12px;
    line-height: 20px;
    color: #979ba5;
  }

  @media (max-width: 1100px) {
    .side-render-view {
      height: auto;
      max-height: none;
      overflow: visible;
    }

    .side-render-workbench {
      grid-template-columns: 1fr;
      overflow: visible;
    }

    .workbench-left {
      min-height: 520px;
    }

    .workbench-right {
      overflow: visible;
    }
  }
</style>
