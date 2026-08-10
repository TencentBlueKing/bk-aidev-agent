<template>
  <!-- svg 源码来自本地内置资源，不含外部输入，v-html 无注入风险 -->
  <span
    class="ai-file-icon"
    v-html="svg"
  />
</template>
<script setup lang="ts">
  import { computed } from 'vue';

  import { getFileIconSvg } from '../../icons/file-icons';

  defineOptions({ name: 'FileIcon' });

  const props = defineProps<{
    // 文件名，fileType 缺省时用于推断扩展名
    fileName?: string;
    // 文件类型：扩展名（如 pdf / py）或无扩展名文件名（如 Dockerfile）
    fileType?: string;
  }>();

  const svg = computed(() => getFileIconSvg(props.fileType, props.fileName));
</script>
<style lang="scss">
  .ai-file-icon {
    display: inline-flex;
    flex-shrink: 0;
    line-height: 1;

    // 图标尺寸跟随外层 font-size，调用方无需关心 svg 自带的宽高属性
    svg {
      width: 1em;
      height: 1em;
    }
  }
</style>
