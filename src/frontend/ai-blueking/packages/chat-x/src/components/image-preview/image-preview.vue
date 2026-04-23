<template>
  <Teleport to="body">
    <transition name="ai-image-preview-fade">
      <div
        v-if="visible"
        class="ai-image-preview"
        @wheel.prevent="handleWheel"
      >
        <div
          class="ai-image-preview-close"
          @click="handleClose"
        >
          <PreviewCloseIcon class="ai-image-preview-close-icon" />
        </div>

        <template v-if="isMultiple">
          <div
            class="ai-image-preview-arrow ai-image-preview-arrow-left"
            @click="handlePrev"
          >
            <ArrowLeftIcon class="ai-image-preview-arrow-icon" />
          </div>
          <div
            class="ai-image-preview-arrow ai-image-preview-arrow-right"
            @click="handleNext"
          >
            <ArrowRightPreviewIcon class="ai-image-preview-arrow-icon" />
          </div>
        </template>

        <div
          class="ai-image-preview-body"
          @click.self="handleMaskClick"
          @mousedown="handleDragStart"
        >
          <img
            v-if="currentStatus !== 'error'"
            class="ai-image-preview-img"
            draggable="false"
            :src="currentImage.url"
            :style="imageStyle"
            @error="handleImageError"
            @load="handleImageLoad"
          />
          <div
            v-if="currentStatus === 'error'"
            class="ai-image-preview-error"
          >
            <ImageBrokenIcon class="ai-image-preview-error-icon" />
            <p class="ai-image-preview-error-text">
              {{ t('抱歉，图片加载失败，可尝试重新加载') }}
            </p>
          </div>
          <div
            v-if="currentStatus === 'loading'"
            class="ai-image-preview-loading"
          >
            <img
              v-if="currentImage.thumbnailUrl"
              class="ai-image-preview-img ai-image-preview-img--blur"
              draggable="false"
              :src="currentImage.thumbnailUrl"
              :style="imageStyle"
            />
          </div>
        </div>

        <PreviewToolbar
          :active-index="activeIndex"
          :current-image-info="currentImageInfo"
          :is-multiple="isMultiple"
          :show-info="showInfo"
          :total="normalizedImages.length"
          @download="handleDownload"
          @reset="resetTransform"
          @rotate="rotateCW"
          @zoom-in="zoomIn"
          @zoom-out="zoomOut"
        >
          <template
            v-if="$slots.extra"
            #extra
          >
            <slot name="extra" />
          </template>
        </PreviewToolbar>
      </div>
    </transition>
  </Teleport>
</template>

<script setup lang="ts">
  import { computed, onBeforeUnmount, shallowRef } from 'vue';

  import { ArrowLeftIcon, ArrowRightPreviewIcon, ImageBrokenIcon, PreviewCloseIcon } from '../../icons/image-preview';
  import { t } from '../../lang/lang';
  import PreviewToolbar from './preview-toolbar.vue';
  import { useImageTransform } from './use-image-transform';
  import { usePreviewKeyboard } from './use-preview-keyboard';

  import type { ImageItem, ImageLoadingStatus } from '../../types/image';

  defineOptions({ name: 'ImagePreview' });

  const props = withDefaults(
    defineProps<{
      images?: (File | ImageItem | string)[];
      maskClosable?: boolean;
      onDownload?: (url: string) => void;
      showInfo?: boolean;
    }>(),
    {
      images: () => [],
      showInfo: false,
      maskClosable: true,
      onDownload: undefined,
    },
  );

  const visible = defineModel<boolean>('visible', { required: true });
  const activeIndex = defineModel<number>('current', { default: 0 });

  const { imageStyle, resetTransform, zoomIn, zoomOut, rotateCW, handleWheel, handleDragStart } = useImageTransform();

  const currentStatus = shallowRef<ImageLoadingStatus>('loading');

  const objectUrls: string[] = [];

  const revokeObjectUrls = () => {
    objectUrls.forEach(url => URL.revokeObjectURL(url));
    objectUrls.length = 0;
  };

  const fileToImageItem = (file: File): ImageItem => {
    const url = URL.createObjectURL(file);
    objectUrls.push(url);
    return { url, name: file.name, file };
  };

  // visible 必须参与计算：关闭时会 revoke blob URL，若仅依赖 props.images，
  // computed 缓存仍指向已失效的 url，再次打开预览会加载失败。
  const normalizedImages = computed<ImageItem[]>(() => {
    if (!visible.value) {
      revokeObjectUrls();
      return [];
    }
    revokeObjectUrls();
    return props.images.map(img => {
      if (img instanceof File) return fileToImageItem(img);
      if (typeof img === 'string') return { url: img };
      if (img.file && !img.url) return { ...img, url: fileToImageItem(img.file).url };
      return img;
    });
  });

  onBeforeUnmount(revokeObjectUrls);

  const currentImage = computed(() => normalizedImages.value[activeIndex.value] ?? { url: '' });
  const isMultiple = computed(() => normalizedImages.value.length > 1);

  const currentImageInfo = computed(() => {
    const img = currentImage.value;
    if (!img.width && !img.resolution) return null;
    return { width: img.width, resolution: img.resolution };
  });

  const handleClose = () => {
    visible.value = false;
  };

  const handleMaskClick = () => {
    if (props.maskClosable) handleClose();
  };

  const switchImage = (index: number) => {
    activeIndex.value = index;
    resetTransform();
    currentStatus.value = 'loading';
  };

  const handlePrev = () => {
    const next = activeIndex.value > 0 ? activeIndex.value - 1 : normalizedImages.value.length - 1;
    switchImage(next);
  };

  const handleNext = () => {
    const next = activeIndex.value < normalizedImages.value.length - 1 ? activeIndex.value + 1 : 0;
    switchImage(next);
  };

  const handleDownload = () => {
    const img = currentImage.value;
    const url = img.downloadUrl || img.url;
    if (props.onDownload) {
      props.onDownload(url);
      return;
    }
    const link = document.createElement('a');
    link.href = url;
    link.download = img.name || url.split('/').pop() || 'image';
    link.target = '_blank';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const handleImageLoad = () => {
    currentStatus.value = 'loaded';
  };

  const handleImageError = () => {
    currentStatus.value = 'error';
  };

  usePreviewKeyboard({
    visible,
    onClose: handleClose,
    onPrev: () => isMultiple.value && handlePrev(),
    onNext: () => isMultiple.value && handleNext(),
  });
</script>

<style lang="scss">
  .ai-image-preview {
    position: fixed;
    inset: 0;
    z-index: 10000;
    display: flex;
    align-items: center;
    justify-content: center;
    user-select: none;
    background: rgb(0 0 0 / 60%);

    &-close {
      position: absolute;
      top: 24px;
      right: 24px;
      z-index: 2;
      display: flex;
      align-items: center;
      justify-content: center;
      width: 40px;
      height: 40px;
      cursor: pointer;
      background: rgb(0 0 0 / 20%);
      border-radius: 50%;
      transition: background 0.2s;

      &:hover {
        background: rgb(0 0 0 / 30%);
      }

      &-icon {
        width: 20px;
        height: 20px;
        color: #fff;
      }
    }

    &-arrow {
      position: absolute;
      z-index: 2;
      display: flex;
      align-items: center;
      justify-content: center;
      width: 40px;
      height: 40px;
      cursor: pointer;
      background: rgb(0 0 0 / 20%);
      border-radius: 50%;
      transition: background 0.2s;

      &:hover {
        background: rgb(0 0 0 / 30%);
      }

      &-left {
        left: 64px;
      }

      &-right {
        right: 64px;
      }

      &-icon {
        width: 20px;
        height: 20px;
        color: #fff;
      }
    }

    &-body {
      position: relative;
      display: flex;
      align-items: center;
      justify-content: center;
      width: 100%;
      height: 100%;
      overflow: hidden;
    }

    &-img {
      max-width: 80%;
      max-height: 80%;
      object-fit: contain;
      transform-origin: center center;

      &--blur {
        opacity: 0.6;
        filter: blur(10px);
      }
    }

    &-loading {
      position: absolute;
      display: flex;
      align-items: center;
      justify-content: center;
    }

    &-error {
      display: flex;
      flex-direction: column;
      gap: 16px;
      align-items: center;
      justify-content: center;

      &-icon {
        width: 97px;
        height: 86px;
        color: #979ba5;
      }

      &-text {
        margin: 0;
        font-size: 14px;
        line-height: 22px;
        color: #979ba5;
      }
    }
  }

  .ai-image-preview-fade-enter-active,
  .ai-image-preview-fade-leave-active {
    transition: opacity 0.3s ease;
  }

  .ai-image-preview-fade-enter-from,
  .ai-image-preview-fade-leave-to {
    opacity: 0;
  }
</style>
