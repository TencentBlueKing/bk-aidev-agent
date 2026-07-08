<template>
  <div class="flow-side-render-demo">
    <div
      v-if="!flowAgentUrl"
      class="flow-side-render-demo__empty"
    >
      请在 <code>packages/ai-blueking/.env.local</code> 中配置 <code>VITE_FLOW_AGENT_URL</code>（流程智能体插件 API
      地址）
    </div>
    <template v-else>
      <details
        v-if="mode === 'custom-fetch'"
        class="flow-side-render-demo__trace"
      >
        <summary class="flow-side-render-demo__trace-summary">自定义拉取观测</summary>
        <dl class="flow-side-render-demo__trace-meta">
          <div class="flow-side-render-demo__trace-row">
            <dt>最近请求</dt>
            <dd>
              <code v-if="lastRequestUrl">{{ lastRequestUrl }}</code>
              <span
                v-else
                class="flow-side-render-demo__trace-placeholder"
              >
                尚未触发（请先打开节点详情 Tab）
              </span>
            </dd>
          </div>
          <div
            v-if="lastFetchedAt"
            class="flow-side-render-demo__trace-row"
          >
            <dt>完成时间</dt>
            <dd>{{ lastFetchedAt }}</dd>
          </div>
          <div
            v-if="lastError"
            class="flow-side-render-demo__trace-row is-error"
          >
            <dt>错误</dt>
            <dd>{{ lastError }}</dd>
          </div>
        </dl>
      </details>

      <label class="flow-side-render-demo__toggle">
        <input
          v-model="executionTabVisible"
          type="checkbox"
        />
        <span>展示「执行情况」Tab（<code>executionTabVisible</code>）</span>
      </label>

      <div class="flow-side-render-demo__chat">
        <ChatBot
          :key="chatBotKey"
          height="100%"
          :url="flowAgentUrl"
          :execution-tab-visible="executionTabVisible"
          :get-side-render-component="getSideRenderComponent"
          :get-side-tab-render-component="getSideTabRenderComponent"
          :on-custom-tab-change="onCustomTabChange"
          :hello-text="helloText"
          :placeholder="'输入消息，触发流程智能体（FlowAgent）…'"
          placement="left"
          :resize-props="{
            initialDivide: '55%',
            min: 320,
            max: 720,
          }"
          @error="handleError"
        />
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
  import { computed, ref } from 'vue';

  import { ChatBot, type GetSideRenderComponent } from '@blueking/ai-blueking';

  import { useSideRenderCustomTabChange } from './use-side-render-custom-tab-change';
  import { useSideRenderHandlers } from './use-side-render-handlers';
  import type { FlowSideRenderDemoMode } from './side-render-scenarios';

  export type { FlowSideRenderDemoMode } from './side-render-scenarios';

  const props = withDefaults(
    defineProps<{
      mode?: FlowSideRenderDemoMode;
    }>(),
    {
      mode: 'default-api',
    },
  );

  const flowAgentUrl = import.meta.env.VITE_FLOW_AGENT_URL || '';

  // 「执行情况」Tab 显隐开关：缺省 true；置 false 后从 Tab 栏隐藏（该 Tab order 固定 0 且不可关闭）
  const executionTabVisible = ref(true);

  const builtinHandlers = useSideRenderHandlers({ detailSource: 'builtin' });
  const customHandlers = useSideRenderHandlers({ detailSource: 'custom' });

  const getSideRenderComponent: GetSideRenderComponent = (createElement, tabProps) => {
    const handler =
      props.mode === 'custom-fetch' ? customHandlers.getSideRenderComponent : builtinHandlers.getSideRenderComponent;
    return handler(createElement, tabProps);
  };

  const getSideTabRenderComponent = builtinHandlers.getSideTabRenderComponent;

  const customFetch = useSideRenderCustomTabChange(flowAgentUrl);

  const onCustomTabChange = computed(() => (props.mode === 'custom-fetch' ? customFetch.onCustomTabChange : undefined));

  const lastRequestUrl = computed(() => (props.mode === 'custom-fetch' ? customFetch.lastRequestUrl.value : null));
  const lastFetchedAt = computed(() => (props.mode === 'custom-fetch' ? customFetch.lastFetchedAt.value : null));
  const lastError = computed(() => (props.mode === 'custom-fetch' ? customFetch.lastError.value : null));

  const chatBotKey = computed(() => `side-render-${props.mode}`);

  const helloText = computed(() => {
    if (props.mode === 'custom-fetch') {
      return '【场景 2】传入 onCustomTabChange 自定义详情拉取。发送消息后点击节点「详情」验证。';
    }
    return '【场景 1】仅自定义侧栏 UI，详情走内置接口。发送消息后点击节点「详情」验证。';
  });

  const handleError = (error: Error) => {
    console.error('[SideRender Demo]', props.mode, error);
  };
</script>

<style scoped>
  .flow-side-render-demo {
    display: flex;
    flex: 1;
    flex-direction: column;
    min-height: 0;
    overflow: hidden;
    border: 1px solid #dcdee5;
    border-radius: 8px;
  }

  .flow-side-render-demo__toggle {
    display: flex;
    flex-shrink: 0;
    gap: 6px;
    align-items: center;
    padding: 8px 10px;
    font-size: 12px;
    line-height: 18px;
    color: #63656e;
    cursor: pointer;
    background: #f5f7fa;
    border-bottom: 1px solid #dcdee5;

    input {
      cursor: pointer;
    }

    code {
      padding: 1px 5px;
      font-size: 11px;
      color: #3a84ff;
      background: #f0f5ff;
      border-radius: 3px;
    }
  }

  .flow-side-render-demo__chat {
    flex: 1;
    min-height: 0;
  }

  .flow-side-render-demo__chat :deep(.ai-chatbot) {
    height: 100%;
  }

  .flow-side-render-demo__empty {
    padding: 24px;
    font-size: 13px;
    line-height: 22px;
    color: #63656e;
    background: #fffbf0;
  }

  .flow-side-render-demo__empty code {
    padding: 1px 6px;
    font-size: 12px;
    color: #3a84ff;
    background: #f0f5ff;
    border-radius: 3px;
  }

  .flow-side-render-demo__trace {
    flex-shrink: 0;
    padding: 6px 10px;
    background: #fff9f0;
    border-bottom: 1px solid #ffe8c3;
  }

  .flow-side-render-demo__trace-summary {
    font-size: 12px;
    font-weight: 600;
    color: #313238;
    cursor: pointer;
    list-style: none;

    &::-webkit-details-marker {
      display: none;
    }

    &::before {
      display: inline-block;
      margin-right: 4px;
      content: '▸';
    }
  }

  .flow-side-render-demo__trace[open] .flow-side-render-demo__trace-summary::before {
    transform: rotate(90deg);
  }

  .flow-side-render-demo__trace-meta {
    margin: 8px 0 0;
  }

  .flow-side-render-demo__trace-row {
    display: grid;
    grid-template-columns: 72px 1fr;
    gap: 8px;
    padding: 4px 0;
    font-size: 12px;
    line-height: 20px;

    dt {
      margin: 0;
      font-weight: 500;
      color: #979ba5;
    }

    dd {
      margin: 0;
      color: #313238;
      word-break: break-all;
    }

    code {
      font-family: monospace;
      font-size: 11px;
      color: #3a84ff;
    }

    &.is-error dd {
      color: #ea3636;
    }
  }

  .flow-side-render-demo__trace-placeholder {
    color: #c4c6cc;
  }
</style>
