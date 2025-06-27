<template>
  <div v-if="show" class="loading-overlay">
    <div class="loading-spinner"></div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  show: boolean
}>()
</script>

<style lang="scss" scoped>
.loading-overlay {
  position: absolute;
  top: 0;
  left: 0;
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 100%;
  background: rgba(255, 255, 255, 0.8);
  cursor: not-allowed;

  .loading-spinner {
    width: 40px;
    height: 40px;
    border: 3px solid #f3f3f3;
    border-top: 3px solid #3498db;
    border-radius: 50%;
    animation: spin 1s linear infinite;
  }
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}
</style> 