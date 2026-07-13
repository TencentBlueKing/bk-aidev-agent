<template>
  <div class="ai-tool-message">
    <DescPanel
      :desc="content || (typeof error === 'string' ? error : undefined)"
      :title="t('返回内容')"
    />
  </div>
</template>
<script setup lang="ts">
  import { t } from '../../../lang/lang';
  import DescPanel from '../../tool-call/desc-panel/desc-panel.vue';

  import type { ToolMessage } from '../../../ag-ui/types/messages';
  defineProps<Partial<ToolMessage>>();
</script>
<style lang="scss">
  .ai-tool-message {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    width: 100%;

    // margin-top: -32px;
    font-size: var(--ai-font-size, 12px);
    line-height: var(--ai-line-height-compact, 20px);
    color: #313238;
    background: #f5f7fa;
    border-radius: 2px;
  }
</style>
