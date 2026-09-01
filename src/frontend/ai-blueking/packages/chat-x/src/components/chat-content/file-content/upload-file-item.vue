<template>
  <div
    class="ai-upload-file-item"
    :class="{
      'is-readonly': readonly,
      'is-pending': isPending,
      'is-error': isError,
    }"
  >
    <span class="ai-upload-file-item-icon">
      <!-- 与文件产物侧栏共用一套扩展名 → 图标映射，解除类型限制后各类文件都有对应图标 -->
      <FileIcon :file-name="name" />
    </span>
    <div class="ai-upload-file-item-meta">
      <span
        v-overflow-tips="{
          ...commonTippyOptions,
          text: name,
          placement: 'top' as const,
        }"
        class="ai-upload-file-item-name"
      >
        {{ name }}
      </span>
      <span
        v-if="isError || sizeText"
        class="ai-upload-file-item-size"
        :class="{ 'is-error': isError }"
      >
        {{ isError ? t('上传失败') : sizeText }}
      </span>
    </div>
    <div
      v-if="isPending"
      class="ai-upload-file-item-overlay"
    >
      <UploadSpinner />
    </div>
    <span
      v-if="!readonly"
      class="ai-upload-file-item-delete"
      @click.stop="emit('delete')"
    >
      <CloseIcon />
    </span>
  </div>
</template>
<script setup lang="ts">
  import { computed } from 'vue';

  import { useCommonTippyInject } from '../../../composables/use-common';
  import { OverflowTips as vOverflowTips } from '../../../directives/overflow-tips';
  import { CloseIcon } from '../../../icons';
  import { t } from '../../../lang/lang';
  import { UploadStatus } from '../../../types';
  import { formatUploadFileSize, getUploadFileName } from '../../../utils';
  import FileIcon from '../../file-icon/file-icon.vue';
  import UploadSpinner from './upload-spinner.vue';

  import type { UploadFile } from '../../../types';

  defineOptions({ name: 'UploadFileItem' });

  const props = defineProps<{
    file: Partial<UploadFile>;
    readonly?: boolean;
  }>();
  const emit = defineEmits<{
    (e: 'delete'): void;
  }>();

  const commonTippyOptions = useCommonTippyInject();

  const name = computed(() => getUploadFileName(props.file));
  const sizeText = computed(() => formatUploadFileSize(props.file));
  const isPending = computed(() => props.file.status === UploadStatus.Pending);
  const isError = computed(() => props.file.status === UploadStatus.Error);
</script>
<style lang="scss">
  @use '../../../styles/attachment.scss' as attachment;
  @use '../../../styles/variables.scss' as variables;

  .ai-upload-file-item {
    position: relative;
    box-sizing: border-box;
    display: flex;
    flex: 0 0 auto;
    gap: 8px;
    align-items: center;
    width: 180px; // 设计稿标注：文件宽度固定 180px
    max-width: 100%; // 输入框收窄时不溢出
    height: 48px;
    padding: 4px 8px;
    font-size: var(--ai-font-size, 12px);
    line-height: var(--ai-line-height, 20px);
    background: variables.$color-bg-tab;
    border-radius: 8px;
    transition: background-color 0.2s;

    &:not(.is-readonly):not(.is-pending):not(.is-error):hover {
      background: variables.$color-border;
    }

    &.is-error {
      background: #fff0f0;
      border: 1px solid #ea3636;
    }

    &-icon {
      display: flex;
      flex: 0 0 32px;
      align-items: center;
      justify-content: center;
      width: 32px;
      height: 32px;
      font-size: 16px; // 图标尺寸固定，不随 size 主题缩放
      background: #fff;
      border-radius: 8px;
    }

    &-meta {
      display: flex;
      flex: 1;
      flex-direction: column;
      justify-content: center;
      min-width: 0; // 让文件名可以正常省略
    }

    &-name {
      overflow: hidden;
      text-overflow: ellipsis;
      color: variables.$color-text;
      white-space: nowrap;
    }

    &-size {
      color: variables.$color-text-secondary;

      &.is-error {
        color: #ea3636;
      }
    }

    &-overlay {
      position: absolute;
      inset: 0;
      z-index: 1;
      display: flex;
      align-items: center;
      justify-content: center;
      pointer-events: none;
      background: rgb(0 0 0 / 30%);
      border-radius: 8px;
    }

    &-delete {
      @include attachment.delete-badge('.ai-upload-file-item');
    }
  }
</style>
