<template>
  <DemoRecipe
    :id="RECIPE_ID"
    file="EmbeddedWorkbench.vue"
    instance="embedded"
    kicker="配方 2"
    lang="vue"
    :source="source"
    title="搭一个带会话列表的 AI 工作台"
    when="适用：独立的 AI 页面，需要自己的 Header、会话列表和侧栏开关"
  >
    <DemoStage
      app="AI 运维工作台"
      crumbs="对话"
    >
      <EmbeddedWorkbench
        :key="embedded.key.value"
        ref="workbench"
        :request-options="embedded.requestOptions"
        :url="embedded.url.value"
        v-bind="listeners"
      />
    </DemoStage>
  </DemoRecipe>
</template>

<script setup lang="ts">
  import { ref, watch } from 'vue';
  import type { ChatBotExpose } from '@blueking/ai-blueking';

  import DemoRecipe from '../../demo-kit/DemoRecipe.vue';
  import DemoStage from '../../demo-kit/DemoStage.vue';
  import { useDemoRuntime } from '../../demo-kit/use-demo-runtime';
  import { toListenerProps, useEmbeddedInstance } from '../../demo-kit/use-embedded-instance';
  import EmbeddedWorkbench from './EmbeddedWorkbench.vue';
  import source from './EmbeddedWorkbench.vue?raw';

  const RECIPE_ID = 'embedded-workbench';

  const runtime = useDemoRuntime();
  const embedded = useEmbeddedInstance(RECIPE_ID);
  const workbench = ref<{ chatBot: ChatBotExpose | null } | null>(null);

  watch(
    () => workbench.value?.chatBot ?? null,
    expose => embedded.bindRef(expose),
  );

  /** 用户直接在工作台里操作，按事件把代码页签定位到对应步骤 */
  const STEP_BY_EVENT: Record<string, string> = {
    'agent-info-loaded': '①',
    'session-switched': '②',
  };

  const listeners = toListenerProps(
    Object.fromEntries(
      Object.entries(embedded.handlers).map(([name, handler]) => [
        name,
        (payload?: unknown) => {
          handler(payload);
          if (STEP_BY_EVENT[name]) runtime.selectStep(RECIPE_ID, STEP_BY_EVENT[name]);
        },
      ]),
    ),
  );
</script>
