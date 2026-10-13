<template>
  <span
    v-if="feedback"
    class="demo-feedback"
    :class="`is-${feedback.kind}`"
    role="status"
  >
    {{ feedback.text }}
    <button
      v-if="feedback.goto"
      type="button"
      class="demo-link"
      @click="runtime.openTab(recipeId, feedback.goto)"
    >
      {{ feedback.gotoLabel || '查看' }}
    </button>
  </span>
</template>

<script setup lang="ts">
  import type { FeedbackState } from './types';
  import { useDemoRuntime } from './use-demo-runtime';

  interface DemoFeedbackProps {
    recipeId: string;
    feedback: FeedbackState | null;
  }

  defineProps<DemoFeedbackProps>();

  const runtime = useDemoRuntime();
</script>
