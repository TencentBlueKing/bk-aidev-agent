<template>
  <div class="ai-loading-message">
    <AiLoading :size="18" />
    <slot>
      {{ t('请求中...') }}
    </slot>
  </div>
</template>
<script setup lang="ts">
  import { t } from '../../../lang/lang';
  import AiLoading from '../../ai-loading/ai-loading.vue';
</script>
<style lang="scss">
  .ai-loading-message {
    display: flex;
    gap: 8px;
    align-items: center;
    font-size: 12px;
  }
</style>
