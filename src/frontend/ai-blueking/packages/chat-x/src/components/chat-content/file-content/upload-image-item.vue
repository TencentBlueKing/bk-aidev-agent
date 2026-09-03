<template>
  <div
    class="ai-upload-image-item"
    :class="{ 'is-pending': isPending }"
  >
    <img
      v-if="!showError"
      :alt="name"
      class="ai-upload-image-item-thumb"
      :class="`is-${variant}`"
      :src="src"
      @click="handlePreview"
      @error="emit('error')"
    />
    <div
      v-else
      class="ai-upload-image-item-thumb is-error"
      :class="`is-${variant}`"
    >
      <ImageErrorIcon class="ai-upload-image-item-error-icon" />
    </div>
    <div
      v-if="isPending"
      class="ai-upload-image-item-overlay"
    >
      <UploadSpinner />
    </div>
    <span
      v-if="!readonly"
      class="ai-upload-image-item-delete"
      @click.stop="emit('delete')"
    >
      <CloseIcon />
    </span>
  </div>
</template>
<script setup lang="ts">
  import { computed } from 'vue';

  import { CloseIcon, ImageErrorIcon } from '../../../icons';
  import { UploadStatus } from '../../../types';
  import UploadSpinner from './upload-spinner.vue';

  import type { UploadFileVariant } from '../../../types';

  defineOptions({ name: 'UploadImageItem' });

  const props = withDefaults(
    defineProps<{
      // 图片加载失败：由容器统一记录，失败项不进入预览列表
      hasError?: boolean;
      name?: string;
      readonly?: boolean;
      src?: string;
      status?: UploadStatus;
      variant?: UploadFileVariant;
    }>(),
    {
      variant: 'input',
    },
  );
  const emit = defineEmits<{
    (e: 'delete' | 'error' | 'preview'): void;
  }>();

  const isPending = computed(() => props.status === UploadStatus.Pending);
  const showError = computed(() => !!props.hasError || props.status === UploadStatus.Error);

  const handlePreview = () => {
    if (isPending.value) {
      return;
    }
    emit('preview');
  };
</script>
<style lang="scss">
  @use '../../../styles/attachment.scss' as attachment;
  @use '../../../styles/variables.scss' as variables;

  .ai-upload-image-item {
    position: relative;
    flex: 0 0 auto;

    &-thumb {
      display: flex;
      align-items: center;
      justify-content: center;

      // 定高，宽度随原图比例；两端夹取避免竖图过窄、长图撑破容器
      width: auto;
      min-width: 48px;
      max-width: 120px;
      height: 48px;
      cursor: zoom-in;
      object-fit: cover;

      // 输入框待发送态
      &.is-input {
        border: 1px solid variables.$color-bg-tab;
        border-radius: 8px;
      }

      // 消息已发送态
      &.is-message {
        border: 1px solid variables.$color-border-light;
        border-radius: 4px;
      }

      &.is-error {
        cursor: default;
        background: #fff0f0;
        border-color: #ea3636;
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
      background: rgb(0 0 0 / 50%);
      border-radius: 8px;
    }

    &-error-icon {
      width: 18px;
      height: 18px;
      color: variables.$color-text-secondary;
    }

    &-delete {
      @include attachment.delete-badge('.ai-upload-image-item');
    }
  }
</style>
