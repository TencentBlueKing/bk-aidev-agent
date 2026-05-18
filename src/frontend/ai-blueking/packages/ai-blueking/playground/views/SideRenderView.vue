<template>
  <div class="side-render-view">
    <div class="view-header">
      <h2>侧栏渲染 (side-render / tab-render)</h2>
      <p class="view-desc">
        使用小鲸 <code>ChatBot</code> / <code>AIBlueking</code>，通过 <code>url</code> 连接流程智能体后台。FlowAgent 活动消息由内置
        <code>FlowAgentContent</code> 渲染；点击节点「详情」后，通过
        <code>getSideRenderComponent</code>、<code>getSideTabRenderComponent</code> 自定义侧栏，节点详情由小鲸默认接口
        <code>getFlowAgentTaskNodeInfo</code> 拉取。
      </p>
      <p
        v-if="flowAgentUrl"
        class="view-env"
      >
        本页演示后台（Playground 本地配置）：<code>{{ flowAgentUrl }}</code>
      </p>
    </div>

    <div class="demo-section demo-section--live">
      <div class="demo-title">交互演示（ChatBot + 真实 FlowAgent SSE）</div>
      <p class="demo-desc">
        发送一条会触发流程编排的对话 → 等待 SSE 推送 <code>flow_agent_start</code> /
        <code>flow_agent_result</code> → 展开「执行情况」→ 点击节点「详情」查看自定义侧栏。
      </p>
      <FlowAgentSideRenderDemo />
    </div>

    <div class="usage-section">
      <div class="usage-title">后端 SSE 事件（示例）</div>
      <pre class="guide-code"><code>{{ sseExample }}</code></pre>
    </div>

    <div class="usage-section">
      <div class="usage-title">接入步骤</div>
      <div class="usage-steps">
        <div class="usage-step">
          <span class="step-num">1</span>
          <div class="step-content">
            新建侧栏内容组件（须保留 <code>#locateButton</code> 插槽），处理 <code>loading</code>、<code>task_id</code>、<code>node_id</code>、<code>data</code> 等 props
          </div>
        </div>
        <div class="usage-step">
          <span class="step-num">2</span>
          <div class="step-content">
            实现 <code>getSideRenderComponent</code>，将 <code>tab.data.props</code>（snake_case）映射为组件 camelCase
          </div>
        </div>
        <div class="usage-step">
          <span class="step-num">3</span>
          <div class="step-content">
            可选：<code>getSideTabRenderComponent</code> 自定义节点 Tab 标签；可选：<code>onCustomTabChange</code> 自定义详情拉取（不传则走内置
            <code>getFlowAgentTaskNodeInfo</code>）
          </div>
        </div>
        <div class="usage-step">
          <span class="step-num">4</span>
          <div class="step-content">
            在 <code>ChatBot</code> / <code>AIBlueking</code> 上传入 <code>url</code>（流程智能体 API，来源不限）及上述 handlers，发送对话后点击节点「详情」验证侧栏
          </div>
        </div>
      </div>
      <p class="usage-note">
        不要覆盖 <code>#message</code> 插槽来渲染 FlowAgent；对话区由内置 <code>FlowAgentContent</code> 负责，侧栏只通过上述 Props 定制。
        Playground 完整源码：<code>playground/components/side-render/</code>，详细说明见
        <code>playground/custom-side-render-guide.md</code>。
      </p>
    </div>

    <div class="usage-section">
      <div class="usage-title">数据流</div>
      <div class="usage-steps">
        <div class="usage-step">
          <span class="step-num">1</span>
          <div class="step-content">
            chat-helper 解析 <code>CUSTOM / flow_agent_*</code> → Activity 消息（<code>activityType: flow_agent</code>）
          </div>
        </div>
        <div class="usage-step">
          <span class="step-num">2</span>
          <div class="step-content">
            <strong>FlowAgentContent</strong> 点击「详情」→ <code>addCustomTab</code>（默认挂载
            <code>BkFlowNodeDetail</code>）
          </div>
        </div>
        <div class="usage-step">
          <span class="step-num">3</span>
          <div class="step-content">
            <strong>getSideRenderComponent</strong> 返回自定义 VNode，覆盖侧栏内容组件
          </div>
        </div>
        <div class="usage-step">
          <span class="step-num">4</span>
          <div class="step-content">
            未传 <code>onCustomTabChange</code> 时，<code>ChatBot</code> 调用
            <code>flow_agent/{taskId}/task_node_info/{nodeId}/</code> 填充 <code>props.data</code>
          </div>
        </div>
      </div>
    </div>

    <div class="code-section">
      <div class="code-title">接入代码（可复制到业务项目）</div>
      <p class="code-desc">推荐文件组织：<code>components/flow-side/CustomTabContent.vue</code>、<code>use-side-render-handlers.ts</code>、页面内嵌 <code>ChatBot</code>。</p>

      <div
        v-for="block in codeBlocks"
        :key="block.title"
        class="code-block"
      >
        <div class="code-block-title">{{ block.title }}</div>
        <p
          v-if="block.desc"
          class="code-block-desc"
        >
          {{ block.desc }}
        </p>
        <pre class="guide-code"><code>{{ block.code }}</code></pre>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
  import FlowAgentSideRenderDemo from '../components/side-render/FlowAgentSideRenderDemo.vue';

  const flowAgentUrl = import.meta.env.VITE_FLOW_AGENT_URL || '';

  const sseExample = `data: {"type":"CUSTOM","name":"flow_agent_start","value":{"task_id":"10421"}}
data: {"type":"CUSTOM","name":"flow_agent_result","value":{"task_id":10421,"task_name":"...","task_state":"FINISHED","nodes":{...},"statistics":{...}}}
data: {"type":"CUSTOM","name":"flow_agent_end","value":{"task_id":"10421","task_outputs":[]}}`;

  const customTabContentExample = `<!-- CustomTabContent.vue：侧栏内容 UI，须保留 locateButton 插槽 -->
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
      <!-- props.data 为 getFlowAgentTaskNodeInfo 或 onCustomTabChange 返回值 -->
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

  const handlersExample = `// use-side-render-handlers.ts
import { h } from 'vue';
import CustomTabContent from './CustomTabContent.vue';
import type { GetSideRenderComponent, GetSideTabRenderComponent } from '@blueking/ai-blueking';

/** FlowAgent 节点 Tab 的 name：{task_id}|{node_id}|{node_name} */
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
    return createElement('span', { style: { display: 'inline-flex', gap: '6px', alignItems: 'center' } }, [
      createElement('span', { style: { fontSize: '10px', color: '#3a84ff' } }, '节点'),
      createElement('span', { title: nodeName || tab.label }, nodeName || tab.label),
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

  const chatBotExample = `<!-- YourPage.vue：页面内嵌 ChatBot -->
<template>
  <ChatBot
    height="640px"
    :url="flowAgentApiUrl"
    :get-side-render-component="getSideRenderComponent"
    :get-side-tab-render-component="getSideTabRenderComponent"
    placement="left"
    :resize-props="{ initialDivide: '55%', min: 320, max: 720 }"
  />
</template>

<script setup lang="ts">
  import { ChatBot } from '@blueking/ai-blueking';
  import { useSideRenderHandlers } from './use-side-render-handlers';

  // url 来源不限：字面量、配置中心、父组件 props 等
  const flowAgentApiUrl = 'https://your-flow-agent-plugin-api/';
  const { getSideRenderComponent, getSideTabRenderComponent } = useSideRenderHandlers();
<\/script>`;

  const aiBluekingExample = `<!-- 悬浮小鲸模式：Props 与 ChatBot 相同 -->
<template>
  <AIBlueking
    :url="flowAgentApiUrl"
    :get-side-render-component="getSideRenderComponent"
    :get-side-tab-render-component="getSideTabRenderComponent"
    hello-text="发送消息触发 FlowAgent，点击节点「详情」查看自定义侧栏"
  />
</template>

<script setup lang="ts">
  import AIBlueking from '@blueking/ai-blueking';
  import { useSideRenderHandlers } from './use-side-render-handlers';

  const flowAgentApiUrl = 'https://your-flow-agent-plugin-api/';
  const { getSideRenderComponent, getSideTabRenderComponent } = useSideRenderHandlers();
<\/script>`;

  const onCustomTabChangeExample = `// 可选：自定义节点详情拉取（不传则 ChatBot 内置 getFlowAgentTaskNodeInfo）
import type { OnCustomTabChange } from '@blueking/ai-blueking';

const onCustomTabChange: OnCustomTabChange = async (tab) => {
  const props = tab.data?.props ?? {};
  const taskId = props.task_id;
  const nodeId = props.node_id;
  // 调用自有接口，返回值会合并到 tab.data.props.data
  const res = await fetch(\`/api/flow/\${taskId}/nodes/\${nodeId}\`);
  return res.json();
};

// <ChatBot :on-custom-tab-change="onCustomTabChange" ... />`;

  const propsReference = `// 点击「详情」后 tab.data.props（snake_case）→ getSideRenderComponent(h, props)
{
  loading: true,           // 拉取详情前为 true
  task_id: number,
  task_name: string,
  node_id: string,
  node_name: string,
  data: {},                  // 详情接口返回后写入
  has_confidence?: boolean,
}

// 节点 Tab name："{task_id}|{node_id}|{node_name}"
// 内置「执行情况」Tab name 为 execution，不可被 getSideRenderComponent 替换`;

  const codeBlocks = [
    {
      title: '1. 侧栏内容组件 CustomTabContent.vue',
      desc: '必须保留 #locateButton 插槽，供 ChatContainer 注入「在对话中定位」按钮。',
      code: customTabContentExample,
    },
    {
      title: '2. use-side-render-handlers.ts',
      desc: '将 tab.data.props 映射为组件 props；节点 Tab 可通过 getSideTabRenderComponent 自定义标签栏。',
      code: handlersExample,
    },
    {
      title: '3. 页面接入 ChatBot',
      desc: 'url 为流程智能体插件 API（须能返回 flow_agent_* SSE），可直接写死或由配置/父组件传入；不要覆盖 #message 插槽。',
      code: chatBotExample,
    },
    {
      title: '4. 悬浮小鲸 AIBlueking（可选）',
      code: aiBluekingExample,
    },
    {
      title: '5. 自定义详情拉取 onCustomTabChange（可选）',
      desc: '仅换 UI、仍用默认 flow_agent/.../task_node_info/ 接口时无需配置。',
      code: onCustomTabChangeExample,
    },
    { title: '6. tab.data.props 字段参考', code: propsReference },
  ];
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
  .step-content code,
  .usage-note code,
  .code-desc code,
  .code-block-desc code,
  .guide-code {
    padding: 1px 6px;
    font-size: 12px;
    color: #3a84ff;
    background: #f0f5ff;
    border-radius: 3px;
  }

  .demo-section,
  .usage-section,
  .code-section {
    padding: 16px;
    margin-bottom: 20px;
    background: #fff;
    border: 1px solid #dcdee5;
    border-radius: 8px;
  }

  .demo-section--live {
    padding-bottom: 12px;
  }

  .demo-title,
  .usage-title,
  .code-title {
    margin-bottom: 8px;
    font-size: 14px;
    font-weight: 600;
    color: #313238;
  }

  .demo-desc,
  .code-desc {
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

  .code-block {
    margin-bottom: 16px;
  }

  .code-block:last-child {
    margin-bottom: 0;
  }

  .code-block-title {
    margin-bottom: 4px;
    font-size: 13px;
    font-weight: 600;
    color: #313238;
  }

  .code-block-desc {
    margin: 0 0 8px;
    font-size: 12px;
    line-height: 18px;
    color: #979ba5;
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
</style>
