<template>
  <DemoRecipe
    :id="RECIPE_ID"
    file="AtomicAssemblyDemo.vue"
    instance="none"
    kicker="配方 1"
    lang="vue"
    :source="source"
    title="用 chat-x + chat-helper 拼一个对话区"
    when="适用：对接自有 AG-UI 网关，或产品形态与小鲸差异很大"
  >
    <DemoStage
      app="自建 AI 网关"
      crumbs="原子组件"
    >
      <AtomicAssemblyDemo @trace="(text: string) => runtime.logEvent('event', text, RECIPE_ID)" />
    </DemoStage>
  </DemoRecipe>
</template>

<script setup lang="ts">
  import DemoRecipe from '../../demo-kit/DemoRecipe.vue';
  import DemoStage from '../../demo-kit/DemoStage.vue';
  import { useDemoRuntime } from '../../demo-kit/use-demo-runtime';
  import AtomicAssemblyDemo from './AtomicAssemblyDemo.vue';
  import source from './AtomicAssemblyDemo.vue?raw';

  const RECIPE_ID = 'atomic-assembly';

  const runtime = useDemoRuntime();
</script>
