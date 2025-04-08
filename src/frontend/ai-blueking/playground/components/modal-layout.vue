<template>
  <div class="modal-layout">
    <div class="modal-content">
      <div class="modal-header">
        <h2>{{ title }}</h2>
        <button
          class="close-btn"
          @click="$emit('close')"
        >
          ×
        </button>
      </div>
      <div class="modal-body">
        <slot></slot>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
  defineProps<{
    title: string;
  }>();

  defineEmits(['close']);

  defineOptions({
    name: 'ModalLayout',
  });
</script>

<style lang="scss" scoped>
  .modal-layout {
    position: fixed;
    top: 0;
    left: 0;
    z-index: 1000;
    display: flex;
    align-items: center;
    justify-content: center;
    width: 100%;
    height: 100%;
    background: rgba(0, 0, 0, 0.5);
  }

  .modal-content {
    width: 80%;
    max-width: 1200px;
    max-height: 90vh;
    background: #fff;
    border-radius: 8px;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  }

  .modal-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 16px 24px;
    border-bottom: 1px solid #eee;

    h2 {
      margin: 0;
      font-size: 20px;
      color: #333;
    }
  }

  .close-btn {
    padding: 4px 8px;
    font-size: 24px;
    color: #999;
    cursor: pointer;
    background: transparent;
    border: none;

    &:hover {
      color: #666;
    }
  }

  .modal-body {
    max-height: calc(90vh - 70px);
    padding: 32px;
    overflow-y: auto;
  }
</style>
