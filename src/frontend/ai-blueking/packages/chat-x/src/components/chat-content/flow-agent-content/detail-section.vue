<template>
  <div class="ai-detail-section">
    <div class="section-heading">
      <span class="section-bar" />
      <span class="section-text">{{ title }}</span>
    </div>
    <slot />
  </div>
</template>

<script setup lang="ts">
  defineProps<{
    title: string;
  }>();
</script>

<style lang="scss">
  @use '../../../styles/variables.scss' as variables;

  .ai-detail-section {
    margin-bottom: 16px;

    .section-heading {
      display: flex;
      gap: 8px;
      align-items: center;
      margin-bottom: 8px;
    }

    .section-bar {
      width: 2px;
      height: 16px;
      background: variables.$color-primary;
    }

    .section-text {
      font-size: 14px;
      font-weight: bold;
      line-height: 22px;
      color: variables.$color-title;
    }
  }
</style>
