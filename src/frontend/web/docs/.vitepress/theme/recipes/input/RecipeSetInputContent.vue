<template>
  <DemoRecipe
    :id="RECIPE_ID"
    file="snippets/set-input-content.ts"
    instance="embedded"
    kicker="配方"
    :source="source"
    title="把自定义标签写进输入框"
    when="适用：业务页已经选中了主机、工单等对象，要替用户放进输入框，由用户确认后再发送"
  >
    <DemoStage
      app="蓝鲸配置平台"
      crumbs="主机 / 10.0.0.12"
    >
      <DemoEmbedFrame
        :height="560"
        :nav="['主机', '10.0.0.12', '监控']"
      >
        <template #toolbar>
          <bk-button
            size="small"
            theme="primary"
            @click="handleWriteDoc"
          >
            <span class="demo-step-no">1</span>写入标签
          </bk-button>
          <bk-button
            size="small"
            @click="handleWriteText"
          >
            <span class="demo-step-no">2</span>写入纯文本
          </bk-button>
          <bk-button
            size="small"
            @click="handleClear"
          >
            <span class="demo-step-no">3</span>清空
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
  import { clearInput, writeHostDoc, writePlainText } from './snippets/set-input-content';
  import source from './snippets/set-input-content.ts?raw';

  const RECIPE_ID = 'set-input-content';

  const runtime = useDemoRuntime();
  const embedded = useEmbeddedInstance(RECIPE_ID);
  const feedback = ref<FeedbackState | null>(null);

  const handleWriteDoc = async () => {
    const result = await runtime.run<void, ChatBotExpose>(RECIPE_ID, '①', bot => {
      writeHostDoc(bot);
    });
    feedback.value = resultFeedback(result, () => ({
      kind: 'ok',
      text: '输入框已写入「帮我分析」和「生产服务器」芯片。悬停可看到「上海机房」。尚未发送。',
    }));
  };

  const handleWriteText = async () => {
    const result = await runtime.run<void, ChatBotExpose>(RECIPE_ID, '②', bot => {
      writePlainText(bot);
    });
    feedback.value = resultFeedback(result, () => ({ kind: 'ok', text: '输入框已换成纯文本，没有标签芯片。' }));
  };

  const handleClear = async () => {
    const result = await runtime.run<void, ChatBotExpose>(RECIPE_ID, '③', bot => {
      clearInput(bot);
    });
    feedback.value = resultFeedback(result, () => ({ kind: 'ok', text: '输入框已清空。' }));
  };
</script>
