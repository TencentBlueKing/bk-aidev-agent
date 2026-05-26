<template>
  <div class="flow-side-render-demo">
    <div
      v-if="!flowAgentUrl"
      class="flow-side-render-demo__empty"
    >
      请在 <code>packages/ai-blueking/.env.local</code> 中配置
      <code>VITE_FLOW_AGENT_URL</code>（流程智能体插件 API 地址）
    </div>
    <template v-else>
      <div
        v-if="mode === 'custom-fetch'"
        class="flow-side-render-demo__trace"
      >
        <div class="flow-side-render-demo__trace-title">自定义拉取观测</div>
        <p class="flow-side-render-demo__trace-desc">
          点击节点「详情」后，<code>onCustomTabChange</code> 会发起请求；侧栏内也会展示本次 URL。打开 DevTools → Network 可对照。
        </p>
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
      </div>

      <ChatBot
        :key="chatBotKey"
        height="640px"
        :url="flowAgentUrl"
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
    </template>
  </div>
</template>

<script setup lang="ts">
  import { computed } from 'vue';

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

  const builtinHandlers = useSideRenderHandlers({ detailSource: 'builtin' });
  const customHandlers = useSideRenderHandlers({ detailSource: 'custom' });

  const getSideRenderComponent: GetSideRenderComponent = (createElement, tabProps) => {
    const handler =
      props.mode === 'custom-fetch' ? customHandlers.getSideRenderComponent : builtinHandlers.getSideRenderComponent;
    return handler(createElement, tabProps);
  };

  const getSideTabRenderComponent = builtinHandlers.getSideTabRenderComponent;

  const customFetch = useSideRenderCustomTabChange(flowAgentUrl);

  const onCustomTabChange = computed(() =>
    props.mode === 'custom-fetch' ? customFetch.onCustomTabChange : undefined,
  );

  const lastRequestUrl = computed(() =>
    props.mode === 'custom-fetch' ? customFetch.lastRequestUrl.value : null,
  );
  const lastFetchedAt = computed(() =>
    props.mode === 'custom-fetch' ? customFetch.lastFetchedAt.value : null,
  );
  const lastError = computed(() => (props.mode === 'custom-fetch' ? customFetch.lastError.value : null));

  const chatBotKey = computed(() => `side-render-${props.mode}`);

  const helloText = computed(() => {
    if (props.mode === 'custom-fetch') {
      return '【场景 2】侧栏 UI 与详情拉取均由业务配置：getSideRenderComponent + onCustomTabChange。发送消息后点击节点「详情」，观察上方「自定义拉取观测」与侧栏内请求 URL。';
    }
    return '【场景 1】仅自定义侧栏 UI（getSideRenderComponent / getSideTabRenderComponent），节点详情走 ChatBot 内置 getFlowAgentTaskNodeInfo。发送消息后点击节点「详情」验证。';
  });

  const handleError = (error: Error) => {
    console.error('[SideRender Demo]', props.mode, error);
  };
</script>

<style scoped>
  .flow-side-render-demo {
    overflow: hidden;
    border: 1px solid #dcdee5;
    border-radius: 8px;
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
    padding: 12px 16px;
    background: #fff9f0;
    border-bottom: 1px solid #ffe8c3;
  }

  .flow-side-render-demo__trace-title {
    margin-bottom: 6px;
    font-size: 13px;
    font-weight: 600;
    color: #313238;
  }

  .flow-side-render-demo__trace-desc {
    margin: 0 0 10px;
    font-size: 12px;
    line-height: 20px;
    color: #63656e;
  }

  .flow-side-render-demo__trace-desc code {
    padding: 0 4px;
    font-size: 11px;
    color: #ff9c01;
    background: #fff3e0;
    border-radius: 2px;
  }

  .flow-side-render-demo__trace-meta {
    margin: 0;
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
