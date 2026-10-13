<template>
  <DemoRecipe
    :id="RECIPE_ID"
    file="snippets/minimal-embed.ts"
    instance="embedded"
    kicker="配方 1"
    :source="source"
    title="把聊天区嵌进业务页面"
    when="适用：详情页、工作台里需要一块常驻的 AI 对话区"
  >
    <DemoStage
      app="蓝鲸监控"
      crumbs="故障分析"
    >
      <DemoEmbedFrame :nav="['故障分析', '告警中心', '仪表盘']">
        <template #toolbar>
          <bk-button
            size="small"
            theme="primary"
            @click="handleAsk"
          >
            <span class="demo-step-no">1</span>等就绪后提问
          </bk-button>
          <bk-button
            :disabled="runtime.state.backendMode === 'real'"
            size="small"
            :title="runtime.state.backendMode === 'real' ? '预置会话仅存在于 Mock 中' : ''"
            @click="handleOpenSession"
          >
            <span class="demo-step-no">2</span>打开「上周容量评估」
          </bk-button>
          <DemoFeedback
            :feedback="feedback"
            :recipe-id="RECIPE_ID"
          />
        </template>
        <ChatBot
          :key="embedded.key.value"
          :ref="embedded.bindRef"
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
  import { ref } from 'vue';
  import { ChatBot, type ChatBotExpose } from '@blueking/ai-blueking';

  import DemoEmbedFrame from '../../demo-kit/DemoEmbedFrame.vue';
  import DemoFeedback from '../../demo-kit/DemoFeedback.vue';
  import DemoRecipe from '../../demo-kit/DemoRecipe.vue';
  import DemoStage from '../../demo-kit/DemoStage.vue';
  import { resultFeedback } from '../../demo-kit/feedback';
  import type { FeedbackState } from '../../demo-kit/types';
  import { useDemoRuntime } from '../../demo-kit/use-demo-runtime';
  import { useEmbeddedInstance } from '../../demo-kit/use-embedded-instance';
  import { askWhenReady, openSession } from './snippets/minimal-embed';
  import source from './snippets/minimal-embed.ts?raw';

  const RECIPE_ID = 'minimal-embed';
  /** Mock 预置的历史会话，见 src/mock-fixtures.ts */
  const SEED_SESSION_CODE = 'demo_capacity_review';

  const runtime = useDemoRuntime();
  const embedded = useEmbeddedInstance(RECIPE_ID);
  const feedback = ref<FeedbackState | null>(null);

  const handleAsk = async () => {
    const result = await runtime.run<void, ChatBotExpose>(RECIPE_ID, '①', bot =>
      askWhenReady(bot, '最近 15 分钟 10.0.0.12 的 CPU 为什么这么高？'),
    );
    feedback.value = resultFeedback(result, () => ({ kind: 'ok', text: '已发送。', goto: 'events', gotoLabel: '看 whenReady 时序' }));
  };

  const handleOpenSession = async () => {
    const result = await runtime.run<void, ChatBotExpose>(RECIPE_ID, '②', bot => openSession(bot, SEED_SESSION_CODE));
    feedback.value = resultFeedback(result, () => ({ kind: 'ok', text: '已切换到历史会话。' }));
  };
</script>

