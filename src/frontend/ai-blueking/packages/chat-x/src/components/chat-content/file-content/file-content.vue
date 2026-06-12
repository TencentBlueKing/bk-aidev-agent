<template>
  <div class="ai-files-content">
    <div
      v-for="file in files"
      :key="file.file?.name"
      class="file-content"
      :class="{
        'is-file-object': !isImage(file) || imageErrorMap[getFileKey(file)],
      }"
    >
      <img
        v-if="isImage(file) && !imageErrorMap[getFileKey(file)]"
        :alt="file.filename || file.file?.name"
        class="file-content-image"
        :src="file.url || getFilePreviewUrl(file.file)"
        @click="handlePreview(file)"
        @error="handleImageError(file)"
      />
      <div
        v-else-if="isImage(file) && imageErrorMap[getFileKey(file)]"
        class="file-content-image image-error"
      >
        <ImageErrorIcon class="file-error-icon" />
      </div>
      <div
        v-else
        class="file-content-object"
      >
        <div class="file-description">
          <DocumentIcon class="file-icon" />
          <span class="file-name">
            {{ file.filename || file.file?.name }}
          </span>
          <span class="file-type">
            {{
              file.file
                ? getFileExtension(file.file)
                : file.filename?.split('.').pop() || file.mimeType?.split('/').pop()
            }}
          </span>
        </div>
        <div class="file-size">
          {{ formatFileSize(file.file) }}
        </div>
      </div>
      <DeleteCircleIcon
        v-if="!readonly"
        class="file-delete-icon"
        @click="handleDeleteFile(file)"
      />
    </div>
    <ImagePreview
      v-model:current="previewIndex"
      v-model:visible="previewVisible"
      :images="previewImages"
    />
  </div>
</template>

<script lang="ts" setup>
  import { computed, reactive, shallowRef } from 'vue';

  import { DeleteCircleIcon, DocumentIcon, ImageErrorIcon } from '../../../icons';
  import { type UploadFile } from '../../../types';
  import { formatFileSize, getFileExtension, getFilePreviewUrl, isImageFile } from '../../../utils';
  import ImagePreview from '../../image-preview/image-preview.vue';

  import type { ImageItem } from '../../../types/image';

  const emit = defineEmits<{
    (e: 'deleteFile', file: Partial<UploadFile>): void;
  }>();
  const props = defineProps<{
    files: Partial<UploadFile>[];
    readonly?: boolean;
  }>();

  // 记录图片加载错误状态
  const imageErrorMap = reactive<Record<string, boolean>>({});

  const isImage = (file: Partial<UploadFile>) => {
    if (file.url) {
      return true;
    }
    return isImageFile(file.mimeType || file.file?.type);
  };

  const getFileKey = (file: Partial<UploadFile>) => {
    return file.url || file.file?.name || '';
  };
  const handleImageError = (file: Partial<UploadFile>) => {
    imageErrorMap[getFileKey(file)] = true;
  };
  const handleDeleteFile = (file: Partial<UploadFile>) => {
    emit('deleteFile', file);
  };

  const previewVisible = shallowRef(false);
  const previewIndex = shallowRef(0);

  const imageFiles = computed(() => props.files.filter(f => isImage(f) && !imageErrorMap[getFileKey(f)]));

  const previewImages = computed<(File | ImageItem | string)[]>(() =>
    imageFiles.value
      .map(f => {
        if (f.url) return f.url;
        if (f.file) return f.file;
        return '';
      })
      .filter(Boolean),
  );

  const handlePreview = (file: Partial<UploadFile>) => {
    const idx = imageFiles.value.indexOf(file);
    if (idx < 0) return;
    previewIndex.value = idx;
    previewVisible.value = true;
  };
</script>
<style lang="scss">
  .ai-files-content {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    width: 100%;

    .file-content {
      position: relative;

      .file-delete-icon {
        position: absolute;
        top: -8px;
        right: -8px;
        display: none;
        width: 16px;
        height: 16px;
        font-size: 16px;
        color: #4d4f56;
        cursor: pointer;
        outline: 1px solid transparent;
        background-color: #fff;
        border-radius: 50%;
      }

      &:hover {
        .file-delete-icon {
          display: flex;
          cursor: pointer;
        }
      }

      &-image {
        display: flex;
        flex: 0 0 48px;
        align-items: center;
        justify-content: center;
        width: 48px;
        height: 48px;
        cursor: zoom-in;
        object-fit: contain;
        border-radius: 4px;

        &.image-error {
          background: #fff0f0;
          border: 1px solid #ea3636;
          border-radius: 4px;

          .file-error-icon {
            width: 18px;
            height: 18px;
            color: #979ba5;
          }
        }
      }

      &-object {
        display: flex;
        flex: 1;
        flex-direction: column;
        justify-content: center;
        max-width: 170px;
        height: 48px;
        padding: 4px 8px;
        font-size: var(--ai-font-size, 12px);
        background: #eaebf0;
        border-radius: 4px;

        .file-description {
          display: flex;
          gap: 4px;
          align-items: center;
          width: 100%;
          height: 20px;
          color: #4d4f56;

          .file-icon {
            flex: 0 0 12px;
            width: 12px;
            height: 12px;
            font-size: 12px; // 图标尺寸固定，不随 size 主题缩放
          }

          .file-name {
            flex: 1;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
          }

          .file-type {
            font-size: var(--ai-font-size, 12px);
            color: #4d4f56;
          }
        }

        .file-size {
          margin-left: 16px;
          color: #979ba5;
        }
      }
    }
  }
</style>
