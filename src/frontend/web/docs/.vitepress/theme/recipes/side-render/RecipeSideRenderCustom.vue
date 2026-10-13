<template>
  <DemoRecipe
    :id="RECIPE_ID"
    file="snippets/side-render.ts"
    instance="embedded"
    kicker="配方 2"
    :source="source"
    title="自定义节点详情与 Tab 标签"
    when="适用：节点详情要展示业务信息（负责人、处理手册），或详情数据来自业务自己的接口"
  >
    <DemoStage
      app="蓝鲸监控"
      crumbs="自动巡检"
    >
      <DemoEmbedFrame
        :aside-width="0"
        :height="620"
      >
        <template #toolbar>
          <bk-button
            :disabled="isReal"
            size="small"
            theme="primary"
            :title="isReal ? REAL_TIP : ''"
            @click="handleStart"
          >
            开始巡检 10.0.0.12
          </bk-button>
          <span class="sr-tip">流程结束后，点击流程卡片中节点的「详情」</span>
          <DemoFeedback
            :feedback="feedback"
            :recipe-id="RECIPE_ID"
          />
        </template>
        <ChatBot
          :key="embedded.key.value"
          :ref="embedded.bindRef"
          v-model:aside-collapsed="asideCollapsed"
          :get-side-render-component="getSideRenderComponent"
          :get-side-tab-render-component="getSideTabRenderComponent"
          height="100%"
          :on-custom-tab-change="onCustomTabChange"
          :request-options="embedded.requestOptions"
          :url="embedded.url.value"
          v-bind="embedded.listeners"
        />
      </DemoEmbedFrame>
    </DemoStage>
  </DemoRecipe>
</template>

<script setup lang="ts">
  import { computed, ref } from 'vue';
  import { ChatBot, type ChatBotExpose, type OnCustomTabChange } from '@blueking/ai-blueking';

  import DemoEmbedFrame from '../../demo-kit/DemoEmbedFrame.vue';
  import DemoFeedback from '../../demo-kit/DemoFeedback.vue';
  import DemoRecipe from '../../demo-kit/DemoRecipe.vue';
  import DemoStage from '../../demo-kit/DemoStage.vue';
  import { resultFeedback } from '../../demo-kit/feedback';
  import type { FeedbackState } from '../../demo-kit/types';
  import { useDemoRuntime } from '../../demo-kit/use-demo-runtime';
  import { useEmbeddedInstance } from '../../demo-kit/use-embedded-instance';
  import { FLOW_AGENT_PATH, REAL_TIP } from './flow-agent';
  import { startInspection } from './snippets/flow-run';
  import { createTabChangeHandler, getSideRenderComponent, getSideTabRenderComponent } from './snippets/side-render';
  import source from './snippets/side-render.ts?raw';

  const RECIPE_ID = 'side-render-custom';

  const runtime = useDemoRuntime();
  const isReal = computed(() => runtime.state.backendMode === 'real');
  const agentUrl = computed(() => `${runtime.apiUrl.value}${isReal.value ? '' : FLOW_AGENT_PATH}`);
  const embedded = useEmbeddedInstance(RECIPE_ID, { url: agentUrl });
  const asideCollapsed = ref(true);
  const feedback = ref<FeedbackState | null>(null);

  const fetchDetail = computed(() => createTabChangeHandler(agentUrl.value, embedded.requestOptions.headers));

  const onCustomTabChange: OnCustomTabChange = async tab => {
    runtime.markActive(RECIPE_ID);
    runtime.selectStep(RECIPE_ID, '③');
    runtime.logEvent('event', `onCustomTabChange「${tab.label}」`, RECIPE_ID);
    const data: unknown = await fetchDetail.value(tab);
    feedback.value = { kind: 'ok', text: '详情由 onCustomTabChange 拉取，并补充了负责人与处理手册。', goto: 'requests', gotoLabel: '查看请求' };
    return data;
  };

  const handleStart = async () => {
    const result = await runtime.run<void, ChatBotExpose>(RECIPE_ID, '①', bot => startInspection(bot, '10.0.0.12'));
    feedback.value = resultFeedback(result, () => ({ kind: 'ok', text: '流程已启动，结束后点击节点的「详情」。' }));
  };
</script>

<style scoped>
  .sr-tip {
    font-size: 12px;
    color: #979ba5;
  }
</style>

<style>
  /* Tab 标签由 getSideTabRenderComponent 渲染，处于 ChatBot 内部，不能用 scoped */
  .node-tab {
    display: inline-flex;
    gap: 6px;
    align-items: center;
  }

  .node-tab__dot {
    width: 6px;
    height: 6px;
    background: #7c3aed;
    border-radius: 50%;
  }

  .node-tab__close {
    padding: 0 2px;
    font-size: 14px;
    line-height: 1;
    color: #979ba5;
    cursor: pointer;
    background: none;
    border: 0;
  }

  .node-tab__close:hover {
    color: #ea3636;
  }
</style>
