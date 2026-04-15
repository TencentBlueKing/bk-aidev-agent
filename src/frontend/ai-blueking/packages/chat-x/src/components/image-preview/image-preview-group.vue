<template>
  <div class="ai-image-preview-group">
    <slot />
    <ImagePreview
      v-if="previewVisible"
      v-model:current="activeIndex"
      v-model:visible="previewVisible"
      :images="previewImages"
      :mask-closable="maskClosable"
      :on-download="onDownload"
      :show-info="showInfo"
    >
      <template
        v-if="$slots.extra"
        #extra
      >
        <slot name="extra" />
      </template>
    </ImagePreview>
  </div>
</template>

<script setup lang="ts">
  import { provide, shallowRef } from 'vue';

  import { IMAGE_PREVIEW_GROUP_KEY } from '../../types/image';
  import ImagePreview from './image-preview.vue';

  import type { ImageItem, ImagePreviewGroupContext } from '../../types/image';

  defineOptions({ name: 'ImagePreviewGroup' });

  withDefaults(
    defineProps<{
      maskClosable?: boolean;
      onDownload?: (url: string) => void;
      showInfo?: boolean;
    }>(),
    {
      maskClosable: true,
      showInfo: false,
      onDownload: undefined,
    },
  );

  const registry = new Map<symbol, () => ImageItem>();
  const previewVisible = shallowRef(false);
  const previewImages = shallowRef<ImageItem[]>([]);
  const activeIndex = shallowRef(0);

  const register = (uid: symbol, getItem: () => ImageItem) => {
    registry.set(uid, getItem);
  };

  const unregister = (uid: symbol) => {
    registry.delete(uid);
  };

  const preview = (uid: symbol) => {
    const uids = [...registry.keys()];
    const images = uids.map(id => registry.get(id)!());
    const index = uids.indexOf(uid);

    previewImages.value = images;
    activeIndex.value = index >= 0 ? index : 0;
    previewVisible.value = true;
  };

  provide<ImagePreviewGroupContext>(IMAGE_PREVIEW_GROUP_KEY, {
    register,
    unregister,
    preview,
  });
</script>
