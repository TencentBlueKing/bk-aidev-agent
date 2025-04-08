<template>
  <ModalLayout
    title="更新日志"
    @close="$emit('close')"
  >
    <MarkdownViewer :content="changelog" />
  </ModalLayout>
</template>

<script setup lang="ts">
  import changelog from '../../CHANGELOG.md?raw';
  import MarkdownViewer from './markdown-viewer.vue';
  import ModalLayout from './modal-layout.vue';

  defineEmits(['close']);

  defineOptions({
    name: 'ChangelogViewer',
  });
</script>

<style lang="scss" scoped>
  .changelog-viewer {
    background: #fff;
    border-radius: 8px;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
  }

  .changelog-header {
    padding: 16px 24px;
    border-bottom: 1px solid #eee;

    h2 {
      margin: 0;
      font-size: 20px;
      color: #333;
    }
  }

  .changelog-body {
    max-height: 80vh;
    padding: 32px;
    overflow-y: auto;
  }
</style>
