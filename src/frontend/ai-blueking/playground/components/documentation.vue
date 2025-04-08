<template>
  <ModalLayout
    title="AI 小鲸使用文档"
    @close="$emit('close')"
  >
    <MarkdownViewer :content="readme" />
  </ModalLayout>
</template>

<script setup lang="ts">
  import readme from '../../README.md?raw';
  import MarkdownViewer from './markdown-viewer.vue';
  import ModalLayout from './modal-layout.vue';

  defineEmits(['close']);

  // 定义组件名
  defineOptions({
    name: 'DocumentationViewer',
  });
</script>

<style lang="scss" scoped>
  .documentation-modal {
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
