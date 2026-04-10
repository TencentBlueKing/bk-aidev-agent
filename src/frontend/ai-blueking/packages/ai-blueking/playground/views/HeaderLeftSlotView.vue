<template>
  <div class="slot-demo-view">
    <div class="view-header">
      <h2>headerLeft 插槽</h2>
      <p class="view-desc">演示在 AIBlueking Header 左侧区域插入自定义内容（标签/按钮等）</p>
    </div>
    <AIBlueking :url="apiUrl">
      <template #headerLeft>
        <span class="header-left-tag">Pro</span>
      </template>
    </AIBlueking>
  </div>
</template>

<script setup lang="ts">
  import AIBlueking from '@blueking/ai-blueking';

  const apiUrl = import.meta.env.VITE_API_URL || '';
</script>

<style scoped>
  .view-header {
    margin-bottom: 24px;
  }

  .view-header h2 {
    margin: 0 0 8px;
    font-size: 20px;
    font-weight: 600;
    color: #313238;
  }

  .view-desc {
    margin: 0;
    font-size: 13px;
    color: #979ba5;
  }

  .header-left-tag {
    display: inline-flex;
    align-items: center;
    height: 18px;
    padding: 0 6px;
    font-size: 10px;
    font-weight: 600;
    line-height: 1;
    color: #fff;
    background: linear-gradient(135deg, #3a84ff, #699df4);
    border-radius: 2px;
  }
</style>
