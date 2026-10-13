<template>
  <DemoRecipe
    :id="RECIPE_ID"
    file="CustomMessageRenderer.vue"
    instance="embedded"
    kicker="配方 1"
    lang="vue"
    :source="source"
    title="在回复里渲染图表、表单和嵌入页面"
    when="适用：智能体需要返回结构化结果（数据图表、确认表单、业务面板），而不只是文字"
  >
    <DemoStage
      app="AI 运维工作台"
      crumbs="对话"
    >
      <DemoEmbedFrame :nav="['对话', '报表', '设置']">
        <template #toolbar>
          <bk-button
            v-for="prompt in PROMPTS"
            :key="prompt.label"
            size="small"
            @click="handleAsk(prompt.text)"
          >
            {{ prompt.label }}
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
        >
          <template #message="{ message }">
            <CustomMessageRenderer
              :message="message"
              @form-submit="handleFormSubmit"
            />
          </template>
        </ChatBot>
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
  import CustomMessageRenderer from './CustomMessageRenderer.vue';
  import source from './CustomMessageRenderer.vue?raw';
  import type { FormSubmit } from './widgets/types';

  const RECIPE_ID = 'custom-message';
  /** Mock 按关键词返回带 custom-component 块的回复，见 src/mock-fixtures.ts */
  const PROMPTS = [
    { label: '要一张图表', text: '用图表展示近 7 天的告警量' },
    { label: '要一个确认表单', text: '扩容前给我一个确认表单' },
    { label: '嵌入一个面板', text: '嵌入主机实时监控面板' },
    { label: '混合内容', text: '给我一份混合内容的发布报告' },
  ];

  const runtime = useDemoRuntime();
  const embedded = useEmbeddedInstance(RECIPE_ID);
  const feedback = ref<FeedbackState | null>(null);

  const handleAsk = async (text: string) => {
    const result = await runtime.run<void, ChatBotExpose>(RECIPE_ID, '①', bot => bot.sendMessage(text));
    feedback.value = resultFeedback(result, () => ({ kind: 'ok', text: '已发送，回复完成后自定义块会渲染成组件。' }));
  };

  const handleFormSubmit = async (payload: FormSubmit) => {
    const detail = Object.entries(payload.values)
      .map(([k, v]) => `${k}=${v}`)
      .join('，');
    const result = await runtime.run<void, ChatBotExpose>(RECIPE_ID, '③', bot =>
      bot.sendMessage(`【${payload.title}】${payload.action}${detail ? `（${detail}）` : ''}`),
    );
    feedback.value = resultFeedback(result, () => ({ kind: 'ok', text: `已把表单结果「${payload.action}」回传给智能体。` }));
  };
</script>
