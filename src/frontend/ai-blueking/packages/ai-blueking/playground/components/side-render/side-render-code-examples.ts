import type { SideRenderScenarioId } from './side-render-scenarios';

export interface SideRenderCodeBlock {
  title: string;
  desc?: string;
  code: string;
  fileHint?: string;
}

const customTabContentScenario1 = `<!-- CustomTabContent.vue — 场景 1：须保留 locateButton 插槽 -->
<!--
  场景 1 数据流（未传 onCustomTabChange）：
  1. 点击节点「详情」→ ChatBot 更新 tab.data.props
  2. ChatBot 调用内置详情接口，结果写入 props.data
  3. getSideRenderComponent(h, props) 把 props 传给本组件
-->
<template>
  <div class="side-panel-root">
    <header class="side-panel-header">
      <h3>{{ loading ? '加载中…' : (nodeName || '节点详情') }}</h3>
      <div class="side-panel-actions">
        <slot name="locateButton" />
      </div>
    </header>

    <div v-if="loading" class="side-panel-loading">内置接口拉取中…</div>

    <div v-else class="side-panel-body">
      <dl class="side-panel-meta">
        <div><dt>task_id</dt><dd>{{ taskId ?? '—' }}</dd></div>
        <div><dt>node_id</dt><dd>{{ nodeId || '—' }}</dd></div>
      </dl>

      <p class="side-panel-data-label">props.data（内置详情接口返回）</p>
      <pre class="side-panel-data">{{ JSON.stringify(data, null, 2) }}</pre>
    </div>
  </div>
</template>

<script setup lang="ts">
  withDefaults(defineProps<{
    data?: Record<string, unknown>;
    loading?: boolean;
    nodeId?: string;
    nodeName?: string;
    taskId?: number;
    taskName?: string;
  }>(), {
    data: () => ({}),
    nodeId: '',
    nodeName: '',
  });
<\/script>`;

const customTabContentScenario2 = `<!-- CustomTabContent.vue — 场景 2：须保留 locateButton 插槽 -->
<!--
  场景 2 数据流（已传 onCustomTabChange）：
  1. 点击「详情」→ props.loading 为 true
  2. onCustomTabChange 请求详情并 return 对象
  3. return 值写入 props.data，loading 变为 false
  4. getSideRenderComponent(h, props) 传入本组件，直接渲染 props.data
-->
<template>
  <div class="side-panel-root">
    <header class="side-panel-header">
      <h3>{{ loading ? '加载中…' : (nodeName || '节点详情') }}</h3>
      <div class="side-panel-actions">
        <slot name="locateButton" />
      </div>
    </header>

    <div v-if="loading" class="side-panel-loading">onCustomTabChange 拉取中…</div>

    <div v-else class="side-panel-body">
      <dl class="side-panel-meta">
        <div><dt>task_id</dt><dd>{{ taskId ?? '—' }}</dd></div>
        <div><dt>node_id</dt><dd>{{ nodeId || '—' }}</dd></div>
      </dl>

      <p class="side-panel-data-label">props.data（= onCustomTabChange 的 return）</p>
      <pre class="side-panel-data">{{ JSON.stringify(data, null, 2) }}</pre>
    </div>
  </div>
</template>

<script setup lang="ts">
  withDefaults(defineProps<{
    /** onCustomTabChange 的 return 会合并到这里 */
    data?: Record<string, unknown>;
    loading?: boolean;
    nodeId?: string;
    nodeName?: string;
    taskId?: number;
    taskName?: string;
  }>(), {
    data: () => ({}),
    nodeId: '',
    nodeName: '',
  });
<\/script>`;

const handlersShared = `// use-side-render-handlers.ts
import CustomTabContent from './CustomTabContent.vue';
import type { GetSideRenderComponent, GetSideTabRenderComponent } from '@blueking/ai-blueking';

export function useSideRenderHandlers() {
  const getSideRenderComponent: GetSideRenderComponent = (h, props = {}) =>
    h(CustomTabContent, {
      loading: props.loading,
      taskId: props.task_id,
      taskName: props.task_name,
      nodeId: props.node_id,
      nodeName: props.node_name,
      data: props.data,
    });

  const getSideTabRenderComponent: GetSideTabRenderComponent = (h, tab, { removeCustomTab }) => {
    const nodeName = tab.name.split('|')[2] || tab.label;

    return h('span', {}, [
      h('span', {}, nodeName),
      h('button', {
        type: 'button',
        onClick: (e: Event) => {
          e.stopPropagation();
          removeCustomTab(tab.name);
        },
      }, '×'),
    ]);
  };

  return { getSideRenderComponent, getSideTabRenderComponent };
}`;

const customTabChangeModule = `// use-side-render-custom-tab-change.ts — 场景 2：自定义详情拉取
import type { OnCustomTabChange } from '@blueking/ai-blueking';

export const onCustomTabChange: OnCustomTabChange = async tab => {
  const { task_id: taskId, node_id: nodeId } = tab.data?.props ?? {};
  if (taskId == null || !nodeId) return {};

  // 替换为你的节点详情接口，返回值会写入 props.data
  const res = await fetch(\`/flow_agent/\${taskId}/task_node_info/\${nodeId}/\`, {
    credentials: 'include',
  });
  if (!res.ok) throw new Error(\`HTTP \${res.status}\`);

  const { data } = await res.json();
  return data;
};`;

const pageScenario1 = `<!-- YourPage.vue — 场景 1：仅自定义侧栏 UI -->
<template>
  <ChatBot
    height="100%"
    :url="flowAgentApiUrl"
    :get-side-render-component="getSideRenderComponent"
    :get-side-tab-render-component="getSideTabRenderComponent"
    placement="left"
  />
</template>

<script setup lang="ts">
  import { ChatBot } from '@blueking/ai-blueking';
  import { useSideRenderHandlers } from './use-side-render-handlers';

  const flowAgentApiUrl = 'https://your-flow-agent-plugin-api/';
  const { getSideRenderComponent, getSideTabRenderComponent } = useSideRenderHandlers();
  // 未传 onCustomTabChange → 详情由 ChatBot 内置接口拉取
<\/script>`;

const pageScenario2 = `<!-- YourPage.vue — 场景 2：UI + 详情拉取均自定义 -->
<template>
  <ChatBot
    height="100%"
    :url="flowAgentApiUrl"
    :get-side-render-component="getSideRenderComponent"
    :get-side-tab-render-component="getSideTabRenderComponent"
    :on-custom-tab-change="onCustomTabChange"
    placement="left"
  />
</template>

<script setup lang="ts">
  import { ChatBot } from '@blueking/ai-blueking';
  import { onCustomTabChange } from './use-side-render-custom-tab-change';
  import { useSideRenderHandlers } from './use-side-render-handlers';

  const flowAgentApiUrl = 'https://your-flow-agent-plugin-api/';
  const { getSideRenderComponent, getSideTabRenderComponent } = useSideRenderHandlers();
<\/script>`;

const aiBluekingScenario1 = `<!-- 悬浮小鲸 — 场景 1 -->
<template>
  <AIBlueking
    :url="flowAgentApiUrl"
    :get-side-render-component="getSideRenderComponent"
    :get-side-tab-render-component="getSideTabRenderComponent"
  />
</template>

<script setup lang="ts">
  import AIBlueking from '@blueking/ai-blueking';
  import { useSideRenderHandlers } from './use-side-render-handlers';

  const flowAgentApiUrl = 'https://your-flow-agent-plugin-api/';
  const { getSideRenderComponent, getSideTabRenderComponent } = useSideRenderHandlers();
<\/script>`;

const aiBluekingScenario2 = `<!-- 悬浮小鲸 — 场景 2 -->
<template>
  <AIBlueking
    :url="flowAgentApiUrl"
    :get-side-render-component="getSideRenderComponent"
    :get-side-tab-render-component="getSideTabRenderComponent"
    :on-custom-tab-change="onCustomTabChange"
  />
</template>

<script setup lang="ts">
  import AIBlueking from '@blueking/ai-blueking';
  import { onCustomTabChange } from './use-side-render-custom-tab-change';
  import { useSideRenderHandlers } from './use-side-render-handlers';

  const flowAgentApiUrl = 'https://your-flow-agent-plugin-api/';
  const { getSideRenderComponent, getSideTabRenderComponent } = useSideRenderHandlers();
<\/script>`;

const propsReferenceScenario1 = `// 点击「详情」后，getSideRenderComponent 会拿到这些 props
{
  loading: true,
  task_id: number,
  task_name: string,
  node_id: string,
  node_name: string,
  data: {},  // 内置详情接口返回的数据
}

// 节点 Tab name："{task_id}|{node_id}|{node_name}"`;

const propsReferenceScenario2 = `// 点击「详情」后，getSideRenderComponent 会拿到这些 props
{
  loading: true,
  task_id: number,
  node_id: string,
  data: {},        // onCustomTabChange 返回的数据
}

// onCustomTabChange(tab) 可从 tab.data.props 读取 task_id / node_id`;

const SCENARIO_CODE_BLOCKS: Record<SideRenderScenarioId, SideRenderCodeBlock[]> = {
  'default-api': [
    {
      title: '1. ChatBot 接入',
      fileHint: 'YourPage.vue',
      desc: '先接入入口组件，只需要传侧栏渲染方法。',
      code: pageScenario1,
    },
    {
      title: '2. AIBlueking 接入（可选）',
      desc: '悬浮小鲸形态使用同一组 props。',
      code: aiBluekingScenario1,
    },
    {
      title: '3. 侧栏渲染方法',
      fileHint: 'use-side-render-handlers.ts',
      desc: '把 tab.data.props 映射给侧栏组件；也可自定义 Tab 标签。',
      code: handlersShared,
    },
    {
      title: '4. 侧栏内容组件',
      fileHint: 'CustomTabContent.vue',
      desc: 'props.data 由内置详情接口写入，组件内直接读取渲染。',
      code: customTabContentScenario1,
    },
    {
      title: '5. tab.data.props 字段',
      desc: '场景 1：data 来自内置节点详情接口。',
      code: propsReferenceScenario1,
    },
  ],
  'custom-fetch': [
    {
      title: '1. ChatBot 接入',
      fileHint: 'YourPage.vue',
      desc: '在侧栏渲染方法之外，再传入 onCustomTabChange。',
      code: pageScenario2,
    },
    {
      title: '2. AIBlueking 接入（可选）',
      desc: '悬浮小鲸同样传入 on-custom-tab-change。',
      code: aiBluekingScenario2,
    },
    {
      title: '3. 自定义详情拉取',
      fileHint: 'use-side-render-custom-tab-change.ts',
      desc: '实现 onCustomTabChange：取参数、请求详情、return 数据。',
      code: customTabChangeModule,
    },
    {
      title: '4. 侧栏渲染方法',
      fileHint: 'use-side-render-handlers.ts',
      desc: '与场景 1 相同；props.data 会接收 onCustomTabChange 的返回值。',
      code: handlersShared,
    },
    {
      title: '5. 侧栏内容组件',
      fileHint: 'CustomTabContent.vue',
      desc: 'props.data 即 onCustomTabChange 的 return，组件内直接读取渲染。',
      code: customTabContentScenario2,
    },
    {
      title: '6. tab.data.props 字段',
      desc: '场景 2：data 就是 onCustomTabChange 的返回值。',
      code: propsReferenceScenario2,
    },
  ],
};

export function getSideRenderCodeBlocks(scenarioId: SideRenderScenarioId): SideRenderCodeBlock[] {
  return SCENARIO_CODE_BLOCKS[scenarioId];
}
