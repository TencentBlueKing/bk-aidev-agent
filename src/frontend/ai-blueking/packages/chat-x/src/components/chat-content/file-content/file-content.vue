<template>
  <div class="ai-files-content">
    <div
      v-for="(file, index) in files"
      :key="getFileKey(file) || index"
      class="file-content"
      :class="{
        'is-file-object': !isImage(file) || imageErrorMap[getFileKey(file)],
      }"
    >
      <img
        v-if="isImage(file) && !imageErrorMap[getFileKey(file)]"
        :alt="file.filename || file.file?.name"
        class="file-content-image"
        :src="getImageSrc(file)"
        @click="handlePreview(file)"
        @error="handleImageError(file)"
      />
      <div
        v-else-if="isImage(file) && imageErrorMap[getFileKey(file)]"
        class="file-content-image image-error"
        @click="handlePreview(file)"
      >
        <ImageErrorIcon class="file-error-icon" />
      </div>
      <div
        v-else
        class="file-content-object"
        :class="{ 'is-clickable': canOpenFile(file) }"
        @click="handleOpenFile(file)"
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

  const IMAGE_EXT_RE = /\.(png|jpe?g|gif|webp|bmp|svg)(\?|$)/i;

  const isImage = (file: Partial<UploadFile>) => {
    if (isImageFile(file.mimeType || file.file?.type)) return true;
    const name = file.filename || file.file?.name || file.url || '';
    return IMAGE_EXT_RE.test(name);
  };

  const canOpenFile = (file: Partial<UploadFile>) => Boolean(file.url || file.file);

  const handleOpenFile = (file: Partial<UploadFile>) => {
    if (file.url) {
      window.open(file.url, '_blank', 'noopener,noreferrer');
      return;
    }
    if (file.file) {
      const blobUrl = URL.createObjectURL(file.file);
      window.open(blobUrl, '_blank', 'noopener,noreferrer');
    }
  };

  const getFileKey = (file: Partial<UploadFile>) => {
    return file.url || file.file?.name || file.filename || '';
  };

  const imageSrcMap = reactive<Record<string, string>>({});

  const getImageSrc = (file: Partial<UploadFile>) => {
    const key = getFileKey(file);
    if (imageSrcMap[key]) return imageSrcMap[key];
    return file.url || getFilePreviewUrl(file.file);
  };

  const handleImageError = (file: Partial<UploadFile>) => {
    const key = getFileKey(file);
    if (!imageSrcMap[key] && file.file) {
      imageSrcMap[key] = getFilePreviewUrl(file.file);
      return;
    }
    imageErrorMap[key] = true;
  };
  const handleDeleteFile = (file: Partial<UploadFile>) => {
    emit('deleteFile', file);
  };

  const previewVisible = shallowRef(false);
  const previewIndex = shallowRef(0);

  const imageFiles = computed(() => props.files.filter(f => isImage(f)));

  const previewImages = computed<(File | ImageItem | string)[]>(() =>
    imageFiles.value
      .map(f => {
        if (f.file) return f.file;
        if (f.url) return f.url;
        return '';
      })
      .filter(Boolean),
  );

  const handlePreview = (file: Partial<UploadFile>) => {
    const src = file.file || file.url;
    const idx = src ? previewImages.value.findIndex(img => img === src) : -1;
    if (idx >= 0) {
      previewIndex.value = idx;
      previewVisible.value = true;
      return;
    }
    handleOpenFile(file);
  };
</script>
<style lang="scss">
  .ai-files-content {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    align-items: flex-start;
    width: 100%;

    .file-content {
      position: relative;
      height: 60px; // 每一行统一高度
      max-height: 60px;

      .file-delete-icon {
        position: absolute;
        top: 4px;
        right: 4px;
        z-index: 1;
        display: none;
        align-items: center;
        justify-content: center;
        width: 16px;
        height: 16px;
        font-size: 16px;
        color: #4d4f56;
        cursor: pointer;
        background-color: #fff;
        border-radius: 50%;
        box-shadow: 0 1px 4px #00000026;
      }

      &:hover {
        .file-delete-icon {
          display: flex;
        }
      }

      // 图片缩略图：行高固定，宽度按比例自适应并限制最大宽度，contain 尽量看全
      &-image {
        display: block;
        box-sizing: border-box;
        width: auto;
        height: 100%;
        max-width: 240px;
        cursor: zoom-in;
        object-fit: contain;
        vertical-align: top;
        background: #f5f7fa;
        border: 1px solid #dcdee5;
        border-radius: 10px;
        transition:
          border-color 0.15s ease,
          box-shadow 0.15s ease;

        &:hover {
          border-color: #3a84ff;
          box-shadow: 0 2px 8px #00000014;
        }

        &.image-error {
          display: flex;
          align-items: center;
          justify-content: center;
          width: 60px;
          height: 100%;
          cursor: zoom-in;
          background: #fff0f0;
          border-color: #ea3636;

          .file-error-icon {
            width: 24px;
            height: 24px;
            color: #979ba5;
          }
        }
      }

      // 非图片文件卡片
      &-object {
        display: flex;
        flex-direction: column;
        justify-content: center;
        gap: 4px;
        box-sizing: border-box;
        width: 200px;
        max-width: 240px;
        height: 100%;
        padding: 8px 12px;
        font-size: var(--ai-font-size, 12px);
        background: #f5f7fa;
        border: 1px solid #dcdee5;
        border-radius: 8px;
        box-sizing: border-box;
        transition:
          border-color 0.15s ease,
          box-shadow 0.15s ease;

        &.is-clickable {
          cursor: pointer;
        }

        &:hover {
          border-color: #c4c6cc;
          box-shadow: 0 2px 8px #0000000a;
        }

        .file-description {
          display: flex;
          gap: 6px;
          align-items: center;
          width: 100%;
          color: #313238;

          .file-icon {
            flex: 0 0 16px;
            width: 16px;
            height: 16px;
            font-size: 16px;
            color: #979ba5;
          }

          .file-name {
            flex: 1;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
            font-weight: 500;
          }

          .file-type {
            flex-shrink: 0;
            color: #979ba5;
            text-transform: uppercase;
          }
        }

        .file-size {
          margin-left: 22px;
          color: #979ba5;
        }
      }
    }
  }
</style>
