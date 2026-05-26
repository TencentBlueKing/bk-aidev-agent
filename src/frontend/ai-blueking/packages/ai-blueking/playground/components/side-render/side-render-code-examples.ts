import type { SideRenderScenarioId } from './side-render-scenarios';

export interface SideRenderCodeBlock {
  title: string;
  desc?: string;
  code: string;
  fileHint?: string;
}

const customTabContentShared = `<!-- CustomTabContent.vue：侧栏内容 UI，须保留 locateButton 插槽 -->
<template>
  <div class="side-panel-root">
    <header class="side-panel-header">
      <h3>{{ loading ? '加载中…' : (nodeName || '节点详情') }}</h3>
      <div class="side-panel-actions">
        <slot name="locateButton" />
      </div>
    </header>
    <div v-if="loading" class="side-panel-loading">加载节点详情…</div>
    <div v-else class="side-panel-body">
      <pre>{{ JSON.stringify(data, null, 2) }}</pre>
    </div>
  </div>
</template>

<script setup lang="ts">
  withDefaults(
    defineProps<{
      data?: Record<string, unknown>;
      loading?: boolean;
      nodeId?: string;
      nodeName?: string;
      taskId?: number;
      taskName?: string;
    }>(),
    { data: () => ({}), loading: false, nodeId: '', nodeName: '', taskName: '' },
  );
<\/script>`;

const handlersScenario1 = `// use-side-render-handlers.ts — 场景 1：不传 onCustomTabChange
import CustomTabContent from './CustomTabContent.vue';
import type { GetSideRenderComponent, GetSideTabRenderComponent } from '@blueking/ai-blueking';

function isFlowNodeTab(tab: { name: string }) {
  return tab.name.includes('|');
}

export function useSideRenderHandlers() {
  const getSideRenderComponent: GetSideRenderComponent = (createElement, props) => {
    const raw = props ?? {};
    const taskIdRaw = raw.task_id;
    const taskId =
      typeof taskIdRaw === 'number'
        ? taskIdRaw
        : typeof taskIdRaw === 'string' && taskIdRaw !== ''
          ? Number(taskIdRaw)
          : undefined;

    return createElement(CustomTabContent, {
      loading: Boolean(raw.loading),
      nodeId: typeof raw.node_id === 'string' ? raw.node_id : '',
      nodeName: typeof raw.node_name === 'string' ? raw.node_name : '',
      taskId: Number.isFinite(taskId as number) ? (taskId as number) : undefined,
      taskName: typeof raw.task_name === 'string' ? raw.task_name : '',
      data:
        typeof raw.data === 'object' && raw.data !== null && !Array.isArray(raw.data)
          ? (raw.data as Record<string, unknown>)
          : {},
    });
  };

  const getSideTabRenderComponent: GetSideTabRenderComponent = (createElement, tab, { removeCustomTab }) => {
    if (!isFlowNodeTab(tab)) return undefined;
    const [, , nodeName = ''] = tab.name.split('|');
    return createElement('span', {}, [
      createElement('span', {}, nodeName || tab.label),
      createElement('button', {
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

const handlersScenario2 = `// use-side-render-handlers.ts — 场景 2：映射 props，侧栏可区分数据来源
import CustomTabContent from './CustomTabContent.vue';
import type { GetSideRenderComponent, GetSideTabRenderComponent } from '@blueking/ai-blueking';

export function useSideRenderHandlers() {
  const getSideRenderComponent: GetSideRenderComponent = (createElement, props) => {
    const raw = props ?? {};
    return createElement(CustomTabContent, {
      loading: Boolean(raw.loading),
      nodeId: typeof raw.node_id === 'string' ? raw.node_id : '',
      nodeName: typeof raw.node_name === 'string' ? raw.node_name : '',
      taskId: typeof raw.task_id === 'number' ? raw.task_id : undefined,
      taskName: typeof raw.task_name === 'string' ? raw.task_name : '',
      data: typeof raw.data === 'object' && raw.data !== null ? (raw.data as Record<string, unknown>) : {},
    });
  };

  const getSideTabRenderComponent: GetSideTabRenderComponent = (createElement, tab, ctx) => {
    // 与场景 1 相同，可按需自定义 Tab 标签
    return undefined;
  };

  return { getSideRenderComponent, getSideTabRenderComponent };
}`;

const customTabChangeModule = `// use-side-render-custom-tab-change.ts — 场景 2 专用
import type { OnCustomTabChange } from '@blueking/ai-blueking';

export function createOnCustomTabChange(apiBaseUrl: string): OnCustomTabChange {
  return async tab => {
    const tabProps = tab.data?.props ?? {};
    const taskId = tabProps.task_id;
    const nodeId = tabProps.node_id;
    if (taskId == null || !nodeId) return {};

    const base = apiBaseUrl.endsWith('/') ? apiBaseUrl : \`\${apiBaseUrl}/\`;
    const requestUrl = \`\${base}flow_agent/\${taskId}/task_node_info/\${nodeId}/\`;

    const res = await fetch(requestUrl, { credentials: 'include' });
    if (!res.ok) throw new Error(\`HTTP \${res.status}\`);

    const payload = await res.json();
    return typeof payload === 'object' && payload !== null && 'data' in payload
      ? (payload as { data: unknown }).data
      : payload;
  };
}`;

const pageScenario1 = `<!-- YourPage.vue — 场景 1：仅自定义侧栏 UI -->
<template>
  <ChatBot
    height="640px"
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
  // 未传 onCustomTabChange → ChatBot 内置 getFlowAgentTaskNodeInfo
<\/script>`;

const pageScenario2 = `<!-- YourPage.vue — 场景 2：UI + 详情拉取均自定义 -->
<template>
  <ChatBot
    height="640px"
    :url="flowAgentApiUrl"
    :get-side-render-component="getSideRenderComponent"
    :get-side-tab-render-component="getSideTabRenderComponent"
    :on-custom-tab-change="onCustomTabChange"
    placement="left"
  />
</template>

<script setup lang="ts">
  import { ChatBot } from '@blueking/ai-blueking';
  import { createOnCustomTabChange } from './use-side-render-custom-tab-change';
  import { useSideRenderHandlers } from './use-side-render-handlers';

  const flowAgentApiUrl = 'https://your-flow-agent-plugin-api/';
  const { getSideRenderComponent, getSideTabRenderComponent } = useSideRenderHandlers();
  const onCustomTabChange = createOnCustomTabChange(flowAgentApiUrl);
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
  import { createOnCustomTabChange } from './use-side-render-custom-tab-change';
  import { useSideRenderHandlers } from './use-side-render-handlers';

  const flowAgentApiUrl = 'https://your-flow-agent-plugin-api/';
  const { getSideRenderComponent, getSideTabRenderComponent } = useSideRenderHandlers();
  const onCustomTabChange = createOnCustomTabChange(flowAgentApiUrl);
<\/script>`;

const propsReferenceScenario1 = `// 点击「详情」后 tab.data.props → getSideRenderComponent(h, props)
{
  loading: true,
  task_id: number,
  task_name: string,
  node_id: string,
  node_name: string,
  data: {},  // 场景 1：由 ChatBot 内置 GET flow_agent/{taskId}/task_node_info/{nodeId}/ 写入
}

// 节点 Tab name："{task_id}|{node_id}|{node_name}"`;

const propsReferenceScenario2 = `// 点击「详情」后 tab.data.props → getSideRenderComponent(h, props)
{
  loading: true,   // onTabChange 开始时为 true
  task_id: number,
  node_id: string,
  data: {},        // 场景 2：由 onCustomTabChange 返回值写入，loading 随后置 false
}

// onCustomTabChange(tab) 的 tab 即当前自定义 Tab，可从 tab.data.props 读取 task_id / node_id`;

const SCENARIO_CODE_BLOCKS: Record<SideRenderScenarioId, SideRenderCodeBlock[]> = {
  'default-api': [
    {
      title: '1. 侧栏内容组件',
      fileHint: 'CustomTabContent.vue',
      desc: '两种场景共用；须保留 #locateButton 插槽。',
      code: customTabContentShared,
    },
    {
      title: '2. 渲染 handlers',
      fileHint: 'use-side-render-handlers.ts',
      desc: '映射 tab.data.props；无需 onCustomTabChange。',
      code: handlersScenario1,
    },
    {
      title: '3. 页面接入 ChatBot',
      fileHint: 'YourPage.vue',
      desc: '不传 on-custom-tab-change，详情走内置 getFlowAgentTaskNodeInfo。',
      code: pageScenario1,
    },
    {
      title: '4. 悬浮小鲸 AIBlueking（可选）',
      desc: 'Props 与 ChatBot 一致，同样无需 onCustomTabChange。',
      code: aiBluekingScenario1,
    },
    {
      title: '5. tab.data.props 字段',
      desc: '场景 1 详情来源：ChatBot → chatHelper.message.getFlowAgentTaskNodeInfo。',
      code: propsReferenceScenario1,
    },
  ],
  'custom-fetch': [
    {
      title: '1. 侧栏内容组件',
      fileHint: 'CustomTabContent.vue',
      desc: '与场景 1 相同；根据 props.data 展示 onCustomTabChange 的返回。',
      code: customTabContentShared,
    },
    {
      title: '2. 渲染 handlers',
      fileHint: 'use-side-render-handlers.ts',
      desc: '负责 getSideRenderComponent / getSideTabRenderComponent。',
      code: handlersScenario2,
    },
    {
      title: '3. 自定义详情拉取',
      fileHint: 'use-side-render-custom-tab-change.ts',
      desc: '实现 OnCustomTabChange；传入后内置 getFlowAgentTaskNodeInfo 不再执行。',
      code: customTabChangeModule,
    },
    {
      title: '4. 页面接入 ChatBot',
      fileHint: 'YourPage.vue',
      desc: '与上方交互演示一致：同时传入 getSideRenderComponent 与 onCustomTabChange。',
      code: pageScenario2,
    },
    {
      title: '5. 悬浮小鲸 AIBlueking（可选）',
      desc: '同样传入 on-custom-tab-change。',
      code: aiBluekingScenario2,
    },
    {
      title: '6. tab.data.props 字段',
      desc: '场景 2 详情来源：onCustomTabChange 返回值 → props.data。',
      code: propsReferenceScenario2,
    },
  ],
};

export function getSideRenderCodeBlocks(scenarioId: SideRenderScenarioId): SideRenderCodeBlock[] {
  return SCENARIO_CODE_BLOCKS[scenarioId];
}
