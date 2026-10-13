<template>
  <DemoRecipe
    :id="RECIPE_ID"
    file="CodeToEditor.vue"
    instance="embedded"
    kicker="配方 2"
    lang="vue"
    :source="source"
    title="把回复里的代码插入编辑器"
    when="适用：IDE、脚本编辑器、作业平台等场景，给代码块加「插入 / 应用」按钮"
  >
    <DemoStage
      app="作业平台"
      crumbs="脚本编辑"
    >
      <div class="ch-toolbar">
        <bk-button
          size="small"
          theme="primary"
          @click="handleAsk"
        >
          让小鲸写一段代码
        </bk-button>
        <DemoFeedback
          :feedback="feedback"
          :recipe-id="RECIPE_ID"
        />
      </div>
      <CodeToEditor
        :key="embedded.key.value"
        ref="editor"
        :request-options="embedded.requestOptions"
        :url="embedded.url.value"
        v-bind="embedded.listeners"
        @insert="handleInsert"
      />
    </DemoStage>
  </DemoRecipe>
</template>

<script setup lang="ts">
  import { ref, watch } from 'vue';
  import type { ChatBotExpose } from '@blueking/ai-blueking';

  import DemoFeedback from '../../demo-kit/DemoFeedback.vue';
  import DemoRecipe from '../../demo-kit/DemoRecipe.vue';
  import DemoStage from '../../demo-kit/DemoStage.vue';
  import { resultFeedback } from '../../demo-kit/feedback';
  import type { FeedbackState } from '../../demo-kit/types';
  import { useDemoRuntime } from '../../demo-kit/use-demo-runtime';
  import { useEmbeddedInstance } from '../../demo-kit/use-embedded-instance';
  import CodeToEditor from './CodeToEditor.vue';
  import source from './CodeToEditor.vue?raw';

  const RECIPE_ID = 'code-header';

  const runtime = useDemoRuntime();
  const embedded = useEmbeddedInstance(RECIPE_ID);
  const editor = ref<{ chatBot: ChatBotExpose | null } | null>(null);
  const feedback = ref<FeedbackState | null>(null);

  watch(
    () => editor.value?.chatBot ?? null,
    expose => embedded.bindRef(expose),
  );

  const handleAsk = async () => {
    const result = await runtime.run<void, ChatBotExpose>(RECIPE_ID, '①', bot =>
      bot.sendMessage('给我一段带超时的请求封装代码'),
    );
    feedback.value = resultFeedback(result, () => ({ kind: 'ok', text: '已发送，回复完成后代码块头部会出现「插入到编辑器」。' }));
  };

  const handleInsert = (language: string) => {
    runtime.selectStep(RECIPE_ID, '②');
    runtime.logEvent('event', `#codeHeader「插入到编辑器」（language=${language}）`, RECIPE_ID);
    feedback.value = { kind: 'ok', text: '已插入到左侧编辑器。' };
  };
</script>

<style scoped>
  .ch-toolbar {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    align-items: center;
    margin-bottom: 10px;
  }
</style>
