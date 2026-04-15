<template>
  <div class="info-message">
    <div
      v-for="(text, index) in Array.isArray(content) ? content : [content]"
      :key="index"
      class="info-message-content"
    >
      {{ text }}
    </div>
  </div>
</template>
<script setup lang="ts">
  // import TextContent from '../chat-content/text-content.vue';

  import type { InfoMessage } from '../../../ag-ui/types/messages';
  defineProps<Partial<InfoMessage>>();
</script>
<style lang="scss">
  .info-message {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    height: 0;
    font-size: 12px;
    border-bottom: 1px dashed #dcdee5;

    &-content {
      display: flex;
      align-items: center;
      justify-content: center;
      width: fit-content;
      max-width: calc(100% - 32px);
      height: fit-content;
      padding: 0 16px;
      background-color: #fff;
    }
  }
</style>
