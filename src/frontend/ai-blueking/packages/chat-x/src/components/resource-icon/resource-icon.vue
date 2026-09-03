<template>
  <span class="ai-resource-icon">
    <img
      v-if="renderMode === 'image'"
      alt=""
      :src="icon as string"
      @error="isBroken = true"
    />
    <component
      :is="icon"
      v-else-if="renderMode === 'component'"
    />
    <FileIcon
      v-else-if="type === 'artifact'"
      :file-name="name"
    />
    <component
      :is="fallbackIcon"
      v-else-if="fallbackIcon"
    />
    <ModuleIcon v-else />
  </span>
</template>
<script setup lang="ts">
  import { computed, shallowRef, watch } from 'vue';

  import { FileUploadIcon, KnowledgeBaseIcon, McpIcon, ModuleIcon, ToolIcon } from '../../icons';
  import FileIcon from '../file-icon/file-icon.vue';

  defineOptions({ name: 'ResourceIcon' });

  import type { Component } from 'vue';

  /**
   * 类型默认图标：数据源没给 icon 时按类型兜底。
   * 新增类型只改这一张表，不必再往模板里加分支。
   * artifact 需要按文件后缀推导，单独走 FileIcon。
   */
  const TYPE_FALLBACK_ICONS: Record<string, Component> = {
    file: FileUploadIcon,
    mcp: McpIcon,
    tool: ToolIcon,
    knowledgebase: KnowledgeBaseIcon,
    doc: KnowledgeBaseIcon,
  };

  const props = defineProps<{
    /** 图标：URL 字符串或 Vue 组件；缺省时按 type 回退 */
    icon?: Component | string;
    /** artifact 类型据此推导文件类型图标 */
    name: string;
    type: string;
  }>();

  // 远程图标可能失效，失败后回退到内置图标而不是留一个破图
  const isBroken = shallowRef(false);
  watch(
    () => props.icon,
    () => {
      isBroken.value = false;
    },
  );

  const renderMode = computed<'component' | 'fallback' | 'image'>(() => {
    if (!props.icon) {
      return 'fallback';
    }
    if (typeof props.icon === 'string') {
      return isBroken.value ? 'fallback' : 'image';
    }
    return 'component';
  });

  const fallbackIcon = computed(() => TYPE_FALLBACK_ICONS[props.type]);
</script>
<style lang="scss">
  .ai-resource-icon {
    display: flex;
    flex: 0 0 auto;
    align-items: center;
    justify-content: center;
    width: var(--ai-icon-size, 16px);
    height: var(--ai-icon-size, 16px);
    font-size: var(--ai-icon-size, 16px);

    img {
      width: 100%;
      height: 100%;
      object-fit: contain;
      border-radius: 2px;
    }
  }
</style>
