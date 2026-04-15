<template>
  <span
    v-for="(item, index) in chunks"
    :key="index"
    :style="animationStyle"
  >
    {{ item }}
  </span>
</template>
<script setup lang="ts">
  import { useAnimationText } from '../../composables';
  const props = defineProps<{
    text: string;
  }>();
  const { chunks, animationStyle } = useAnimationText(props.text);
</script>
