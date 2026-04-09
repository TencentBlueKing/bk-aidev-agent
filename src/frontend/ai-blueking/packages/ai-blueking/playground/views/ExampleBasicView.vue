<template>
  <div class="example-view">
    <div class="view-header">
      <h2>基础用法</h2>
      <p class="view-desc">使用完整的 AIBlueking 组件，包含快捷指令、Nimbus 悬浮球、拖拽功能</p>
      <code class="source-path">src/examples/basic-usage.vue</code>
    </div>
    <BasicUsage />
  </div>
</template>

<script setup lang="ts">
import BasicUsage from '../../src/examples/basic-usage.vue';
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
  margin: 0 0 12px;
  font-size: 13px;
  color: #979ba5;
}

.source-path {
  display: inline-block;
  padding: 2px 8px;
  font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
  font-size: 12px;
  color: #3a84ff;
  background: #f0f5ff;
  border-radius: 2px;
}
</style>
