<template>
  <div
    class="demo-status"
    aria-live="polite"
  >
    <span
      v-if="kind === 'floating'"
      class="demo-pill"
      :class="{ 'is-ok': instance.panelOpen }"
    ><i />面板 {{ instance.panelOpen ? '已打开' : '已关闭' }}</span>
    <span
      class="demo-pill"
      :class="{ 'is-ok': instance.session === 'ready', 'is-busy': instance.session === 'loading' }"
      :title="instance.sessionName"
    ><i />{{ sessionText }}</span>
    <span
      class="demo-pill"
      :class="{ 'is-busy': instance.generating }"
    ><i />{{ instance.generating ? '生成中' : '空闲' }}</span>
  </div>
</template>

<script setup lang="ts">
  import { computed } from 'vue';

  import type { InstanceKind } from './types';
  import { useDemoRuntime } from './use-demo-runtime';

  interface DemoStatusBarProps {
    instanceId: string;
    kind: InstanceKind;
  }

  const props = defineProps<DemoStatusBarProps>();
  const runtime = useDemoRuntime();
  const instance = computed(() => runtime.instanceState(props.instanceId));

  const sessionText = computed(() => {
    const s = instance.value;
    if (s.session === 'loading') return '会话 初始化中';
    if (s.session === 'ready') return `会话 就绪${s.sessionName ? `「${s.sessionName}」` : ''}`;
    return '会话 未初始化';
  });
</script>
