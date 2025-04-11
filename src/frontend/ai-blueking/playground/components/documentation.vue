<template>
  <ModalLayout
    title="AI 小鲸使用文档"
    @close="$emit('close')"
  >
    <MarkdownViewer :content="readme" />
  </ModalLayout>
</template>

<script setup lang="ts">
  import readme from '../README.MD?raw';
  import MarkdownViewer from './markdown-viewer.vue';
  import ModalLayout from './modal-layout.vue';

  defineEmits(['close']);

  // 定义组件名
  defineOptions({
    name: 'DocumentationViewer',
  });
</script>
