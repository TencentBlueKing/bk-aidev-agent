<template>
  <DemoRecipe
    :id="RECIPE_ID"
    file="snippets/flow-run.ts"
    instance="embedded"
    kicker="配方 1"
    :source="source"
    title="运行一个流程智能体，查看执行情况"
    when="适用：接入 BKFlow 流程智能体，需要了解默认的执行情况、节点详情与重试 / 跳过"
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
            <span class="demo-step-no">1</span>开始巡检 10.0.0.12
          </bk-button>
          <bk-button
            size="small"
            @click="asideCollapsed = !asideCollapsed"
          >
            {{ asideCollapsed ? '展开侧栏' : '收起侧栏' }}
          </bk-button>
          <label class="fr-switch">
            <input
              v-model="executionTabVisible"
              type="checkbox"
              @change="runtime.selectStep(RECIPE_ID, '③')"
            >
            <code>execution-tab-visible</code>
          </label>
          <DemoFeedback
            :feedback="feedback"
            :recipe-id="RECIPE_ID"
          />
        </template>
        <ChatBot
          :key="embedded.key.value"
          :ref="embedded.bindRef"
          v-model:aside-collapsed="asideCollapsed"
          :execution-tab-visible="executionTabVisible"
          height="100%"
          :request-options="embedded.requestOptions"
          :url="embedded.url.value"
          v-bind="embedded.listeners"
        />
      </DemoEmbedFrame>
    </DemoStage>
  </DemoRecipe>
</template>

<script setup lang="ts">
  import { computed, ref, watch } from 'vue';
  import { ChatBot, type ChatBotExpose } from '@blueking/ai-blueking';

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
  import source from './snippets/flow-run.ts?raw';

  const RECIPE_ID = 'flow-run';

  const runtime = useDemoRuntime();
  const isReal = computed(() => runtime.state.backendMode === 'real');
  const embedded = useEmbeddedInstance(RECIPE_ID, { url: computed(() => `${runtime.apiUrl.value}${isReal.value ? '' : FLOW_AGENT_PATH}`) });
  const asideCollapsed = ref(true);
  const executionTabVisible = ref(true);
  const feedback = ref<FeedbackState | null>(null);

  /** 用户在流程卡片上点「重试 / 跳过」时，代码页签定位到说明 */
  watch(
    () => runtime.recorder.get(RECIPE_ID).requests.at(-1)?.path,
    path => {
      if (path === 'user_operation/') {
        runtime.selectStep(RECIPE_ID, '②');
        feedback.value = { kind: 'info', text: '已提交 user_operation，组件自动续流。', goto: 'requests', gotoLabel: '查看请求' };
      }
    },
  );

  const handleStart = async () => {
    asideCollapsed.value = false;
    const result = await runtime.run<void, ChatBotExpose>(RECIPE_ID, '①', bot => startInspection(bot, '10.0.0.12'));
    feedback.value = resultFeedback(result, () => ({
      kind: 'ok',
      text: '流程已启动：「磁盘检查」会失败，可在对话中的流程卡片上重试或跳过。',
      goto: 'events',
      gotoLabel: '查看事件',
    }));
  };
</script>

<style scoped>
  .fr-switch {
    display: inline-flex;
    gap: 4px;
    align-items: center;
    font-size: 12px;
    color: #63656e;
  }

  .fr-switch code {
    font-size: 11px;
  }
</style>
