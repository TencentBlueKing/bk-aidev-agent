<template>
  <div class="side-render-live-demo">
    <FlowAgentSideRenderDemo :mode="activeScenarioMeta.demoMode" />
  </div>
</template>

<script setup lang="ts">
  import { computed } from 'vue';

  import FlowAgentSideRenderDemo from './FlowAgentSideRenderDemo.vue';
  import { getSideRenderScenarioById, type SideRenderScenarioId } from './side-render-scenarios';

  const props = defineProps<{
    activeScenario: SideRenderScenarioId;
  }>();

  const activeScenarioMeta = computed(() => getSideRenderScenarioById(props.activeScenario));
</script>

<style scoped>
  .side-render-live-demo {
    display: flex;
    flex: 1;
    flex-direction: column;
    min-height: 0;
  }
</style>
