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
  .ai-detail-section {
    $color-title: #313238;
    $color-primary: #3a84ff;

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
      background: $color-primary;
    }

    .section-text {
      font-size: 14px;
      font-weight: bold;
      line-height: 22px;
      color: $color-title;
    }
  }
</style>
