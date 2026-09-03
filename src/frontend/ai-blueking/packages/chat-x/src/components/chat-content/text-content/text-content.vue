<template>
  <div class="ai-text-content">
    {{ content }}
  </div>
</template>
<script setup lang="ts">
  defineProps<{
    content: string;
  }>();
</script>
<style lang="scss">
  .ai-text-content {
    display: flex;
    width: fit-content;
    padding: 8px 12px;

    // 内容来自输入框，多行文本以 \n 承载；不保留空白会让换行与空行被折叠成空格
    word-break: break-all;
    white-space: pre-wrap;
    background-color: #e1ecff;
    border-radius: 4px;
  }
</style>
