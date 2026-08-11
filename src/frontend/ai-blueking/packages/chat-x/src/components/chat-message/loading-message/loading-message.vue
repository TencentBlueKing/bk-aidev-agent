<template>
  <div class="ai-loading-message">
    <AiLoading :size="18" />
    <slot>
      {{ t('请求中...') }}
    </slot>
  </div>
</template>
<script setup lang="ts">
  import { onMounted } from 'vue';

  import { useContainerScrollConsumer } from '../../../composables';
  import { t } from '../../../lang/lang';
  import AiLoading from '../../ai-loading/ai-loading.vue';

  const containerScrollConsumer = useContainerScrollConsumer();

  // 本组件仅在用户刚发出消息、等待回复时出现，其挂载即「新一轮对话开始」的信号。
  // 此时无条件贴底并恢复自动跟随（jumpToBottom 内部会重置 autoScrollEnabled），
  // 保证用户此前手动上滑翻历史后再发消息也能看到新内容。
  onMounted(() => {
    containerScrollConsumer?.value?.jumpToBottom?.();
  });
</script>
<style lang="scss">
  .ai-loading-message {
    display: flex;
    gap: 8px;
    align-items: center;
    font-size: var(--ai-font-size, 12px);
  }
</style>
