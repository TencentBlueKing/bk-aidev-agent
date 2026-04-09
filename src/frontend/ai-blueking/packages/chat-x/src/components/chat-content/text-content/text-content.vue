<template>
  <div class="text-content">
    {{ content }}
  </div>
</template>
<script setup lang="ts">
  defineProps<{
    content: string;
  }>();
</script>
<style lang="scss">
  .text-content {
    display: flex;
    width: fit-content;
    padding: 8px 12px;
    word-break: break-all;
    background-color: #e1ecff;
    border-radius: 4px;
  }
</style>
