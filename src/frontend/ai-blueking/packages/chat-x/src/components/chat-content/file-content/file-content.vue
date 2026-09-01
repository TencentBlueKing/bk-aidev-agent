<template>
  <div
    class="ai-files-content"
    :class="`is-${variant}`"
  >
    <!-- 设计稿：图片始终排在文件前方，两类各自成行 -->
    <div
      v-if="imageItems.length"
      class="ai-files-content-row is-images"
    >
      <UploadImageItem
        v-for="item in imageItems"
        :key="item.key"
        :has-error="item.hasError"
        :name="item.name"
        :readonly="readonly"
        :src="item.src"
        :variant="variant"
        @delete="handleDeleteFile(item.file)"
        @error="handleImageError(item.key)"
        @preview="handlePreview(item.key)"
      />
    </div>
    <div
      v-if="fileItems.length"
      class="ai-files-content-row is-files"
    >
      <UploadFileItem
        v-for="item in fileItems"
        :key="item.key"
        :file="item.file"
        :readonly="readonly"
        @delete="handleDeleteFile(item.file)"
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
  import { computed, onBeforeUnmount, shallowReactive, shallowRef, watch } from 'vue';

  import { type UploadFile, type UploadFileVariant } from '../../../types';
  import { getUploadFileKey, getUploadFileName, splitUploadFiles } from '../../../utils';
  import ImagePreview from '../../image-preview/image-preview.vue';
  import UploadFileItem from './upload-file-item.vue';
  import UploadImageItem from './upload-image-item.vue';

  import type { ImageItem } from '../../../types/image';

  const emit = defineEmits<{
    (e: 'deleteFile', file: Partial<UploadFile>): void;
  }>();
  const props = withDefaults(
    defineProps<{
      files: Partial<UploadFile>[];
      readonly?: boolean;
      variant?: UploadFileVariant;
    }>(),
    {
      variant: 'input',
    },
  );

  // 图片加载失败：key -> true，失败项降级为错误占位且不进入预览列表
  const imageErrorMap = shallowReactive<Record<string, boolean>>({});

  // 本地 File 的 blob URL 按 key 缓存，避免每次渲染都新建；文件移除 / 组件卸载时回收
  const objectUrlMap = new Map<string, string>();

  const resolveImageSrc = (key: string, file: Partial<UploadFile>): string => {
    if (file.url) return file.url;
    if (!file.file) return '';
    const cached = objectUrlMap.get(key);
    if (cached) return cached;
    const objectUrl = URL.createObjectURL(file.file);
    objectUrlMap.set(key, objectUrl);
    return objectUrl;
  };

  const revokeObjectUrls = (keepKeys?: Set<string>) => {
    for (const [key, objectUrl] of objectUrlMap) {
      if (keepKeys?.has(key)) continue;
      URL.revokeObjectURL(objectUrl);
      objectUrlMap.delete(key);
    }
  };

  const groups = computed(() => splitUploadFiles(props.files));

  const imageItems = computed(() =>
    groups.value.imageFiles.map(file => {
      const key = getUploadFileKey(file);
      return {
        file,
        hasError: !!imageErrorMap[key],
        key,
        name: getUploadFileName(file),
        src: resolveImageSrc(key, file),
      };
    }),
  );

  const fileItems = computed(() =>
    groups.value.otherFiles.map(file => ({
      file,
      key: getUploadFileKey(file),
    })),
  );

  // post 刷新：等 DOM 用上新 src 后再回收旧 blob，避免 img 指向已失效地址触发 error
  watch(imageItems, items => revokeObjectUrls(new Set(items.map(item => item.key))), { flush: 'post' });
  onBeforeUnmount(() => revokeObjectUrls());

  const previewVisible = shallowRef(false);
  const previewIndex = shallowRef(0);

  // 仅加载成功的图片可预览，下标需与 previewImages 对齐
  const previewItems = computed(() => imageItems.value.filter(item => !item.hasError && item.src));
  const previewImages = computed<ImageItem[]>(() =>
    previewItems.value.map(item => ({ name: item.name, url: item.src })),
  );

  const handleImageError = (key: string) => {
    imageErrorMap[key] = true;
  };
  const handleDeleteFile = (file: Partial<UploadFile>) => {
    emit('deleteFile', file);
  };
  const handlePreview = (key: string) => {
    const index = previewItems.value.findIndex(item => item.key === key);
    if (index < 0) return;
    previewIndex.value = index;
    previewVisible.value = true;
  };
</script>

<style lang="scss">
  .ai-files-content {
    display: flex;
    flex-direction: column;
    gap: 8px;
    width: 100%;

    &-row {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }

    // 消息已发送态：整体右对齐，图片间距按设计稿 10px
    &.is-message {
      .ai-files-content-row {
        justify-content: flex-end;
      }

      .ai-files-content-row.is-images {
        gap: 10px;
      }
    }
  }
</style>
