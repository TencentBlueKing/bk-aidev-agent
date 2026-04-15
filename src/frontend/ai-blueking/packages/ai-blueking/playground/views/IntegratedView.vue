<template>
  <div class="integrated-view">
    <div class="view-header">
      <h2>集成模式</h2>
      <p class="view-desc">完整的 AIBlueking 组件，包含 Nimbus 悬浮球、拖拽窗口、划词选择等功能</p>
    </div>
    <AIBlueking
      :enable-popup="true"
      :url="apiUrl"
      @close="handleClose"
      @show="handleShow"
    />
  </div>
</template>

<script setup lang="ts">
  import { ref } from 'vue';

  import AIBlueking from '@blueking/ai-blueking';

  const apiUrl = ref(import.meta.env.VITE_API_URL || '');

  const handleShow = () => {
    console.log('[Integrated] AIBlueking shown');
  };

  const handleClose = () => {
    console.log('[Integrated] AIBlueking closed');
  };
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
</style>
