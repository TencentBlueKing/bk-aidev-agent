<template>
  <div class="ai-mention-popover">
    <div class="ai-mention-popover-title">{{ title }}</div>
    <div
      v-if="description"
      class="ai-mention-popover-desc"
    >
      {{ description }}
    </div>
  </div>
</template>
<script setup lang="ts">
  defineProps<{
    description?: string;
    /** 形如「工具：knowlege-base」，由类型名与条目名拼成 */
    title: string;
  }>();
</script>
<style lang="scss">
  @use '../../styles/variables.scss' as variables;

  .tippy-box[data-theme~='ai-mention-popover-theme'] {
    border-radius: 4px;
    box-shadow: 0 0 20px 0 rgb(0 0 0 / 16%);

    &[data-theme~='light'] {
      background: #fff;
    }

    .tippy-content {
      padding: 12px 16px;
    }
  }

  .ai-mention-popover {
    display: flex;
    flex-direction: column;
    gap: 4px;
    max-width: 240px;
    text-align: left;

    &-title {
      font-size: 14px;
      font-weight: 700;
      line-height: 22px;
      color: variables.$color-title;
    }

    &-desc {
      font-size: var(--ai-font-size, 12px);
      line-height: var(--ai-line-height-compact, 20px);
      color: variables.$color-text;
      word-break: break-word;
    }
  }
</style>
