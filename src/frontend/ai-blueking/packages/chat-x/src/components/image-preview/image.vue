<template>
  <div
    ref="containerRef"
    class="ai-image"
    :class="{
      'ai-image--error': status === 'error',
      'ai-image--preview': preview && status === 'loaded',
    }"
    :style="containerStyle"
    @click="handleImageClick"
  >
    <img
      v-if="status !== 'error' && actualSrc"
      :alt="alt"
      class="ai-image-inner"
      :src="actualSrc"
      :style="innerStyle"
      @error="handleError"
      @load="handleLoad"
    />
    <div
      v-if="status === 'error'"
      class="ai-image-error"
    >
      <ImageErrorIcon class="ai-image-error-icon" />
    </div>

    <div
      v-if="status === 'error'"
      class="ai-image-error-overlay"
      @click="handleReload"
    >
      <ReloadIcon class="ai-image-reload-icon" />
      <span>{{ t('重新加载') }}</span>
    </div>

    <slot />

    <ImagePreview
      v-if="!groupContext && preview && previewVisible"
      v-model:visible="previewVisible"
      :images="standalonePreviewImages"
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
  import { computed, inject, onBeforeUnmount, onMounted, ref, shallowRef } from 'vue';
  import type { CSSProperties } from 'vue';

  import { ImageErrorIcon } from '../../icons/content';
  import { ReloadIcon } from '../../icons/image-preview';
  import { t } from '../../lang/lang';
  import { IMAGE_PREVIEW_GROUP_KEY } from '../../types/image';
  import ImagePreview from './image-preview.vue';

  import type { ImageItem, ImagePreviewConfig } from '../../types/image';

  defineOptions({ name: 'AiImage' });

  const props = withDefaults(
    defineProps<{
      alt?: string;
      height?: number | string;
      lazy?: boolean;
      onDownload?: (url: string) => void;
      preview?: boolean;
      previewProps?: ImagePreviewConfig;
      showInfo?: boolean;
      src: string;
      width?: number | string;
    }>(),
    {
      alt: '',
      width: undefined,
      height: undefined,
      lazy: false,
      preview: true,
      previewProps: undefined,
      showInfo: false,
    },
  );

  const emit = defineEmits<{
    (e: 'load', ev: Event): void;
    (e: 'error', ev: Event): void;
    (e: 'preview'): void;
  }>();

  const uid = Symbol();
  const groupContext = inject(IMAGE_PREVIEW_GROUP_KEY, null);

  const containerRef = ref<HTMLElement>();
  const status = shallowRef<'error' | 'loaded' | 'loading'>('loading');
  const previewVisible = shallowRef(false);
  const isInView = shallowRef(!props.lazy);

  let observer: IntersectionObserver | null = null;

  const previewSrc = computed(() => props.previewProps?.src || props.src);

  const getPreviewItem = (): ImageItem => {
    const pp = props.previewProps;
    return {
      url: previewSrc.value,
      name: pp?.name,
      width: pp?.width,
      height: pp?.height,
      resolution: pp?.resolution,
      downloadUrl: pp?.downloadUrl,
    };
  };

  const reloadToken = shallowRef(0);

  const actualSrc = computed(() => {
    if (!props.lazy || isInView.value) {
      const base = props.src;
      if (reloadToken.value === 0) return base;
      return `${base}${base.includes('?') ? '&' : '?'}_t=${reloadToken.value}`;
    }
    return '';
  });

  const standalonePreviewImages = computed<ImageItem[]>(() => [getPreviewItem()]);

  const containerStyle = computed<CSSProperties>(() => {
    const style: CSSProperties = {};
    if (props.width) style.width = typeof props.width === 'number' ? `${props.width}px` : props.width;
    if (props.height) style.height = typeof props.height === 'number' ? `${props.height}px` : props.height;
    return style;
  });

  const innerStyle: CSSProperties = {
    width: '100%',
    height: '100%',
    objectFit: 'cover',
  };

  const handleLoad = (ev: Event) => {
    status.value = 'loaded';
    emit('load', ev);
  };

  const handleError = (ev: Event) => {
    status.value = 'error';
    emit('error', ev);
  };

  const handleReload = () => {
    status.value = 'loading';
    reloadToken.value = Date.now();
  };

  const handleImageClick = () => {
    if (!props.preview || status.value !== 'loaded') return;
    if (groupContext) {
      groupContext.preview(uid);
    } else {
      previewVisible.value = true;
    }
    emit('preview');
  };

  const initObserver = () => {
    if (!props.lazy || !containerRef.value) return;
    observer = new IntersectionObserver(
      entries => {
        if (entries[0]?.isIntersecting) {
          isInView.value = true;
          observer?.disconnect();
          observer = null;
        }
      },
      { rootMargin: '200px' },
    );
    observer.observe(containerRef.value);
  };

  const destroyObserver = () => {
    observer?.disconnect();
    observer = null;
  };

  onMounted(() => {
    initObserver();
    groupContext?.register(uid, getPreviewItem);
  });

  onBeforeUnmount(() => {
    destroyObserver();
    groupContext?.unregister(uid);
  });

  defineExpose({ previewVisible });
</script>

<style lang="scss">
  .ai-image {
    position: relative;
    display: inline-block;
    overflow: hidden;
    vertical-align: top;
    border-radius: 4px;

    &--error {
      background: #f5f7fa;
      border: 1px solid #eaebf0;
    }

    &-inner {
      display: block;
    }

    &-error {
      display: flex;
      align-items: center;
      justify-content: center;
      width: 100%;
      height: 100%;

      &-icon {
        width: 24px;
        height: 24px;
        color: #c4c6cc;
      }
    }

    &-error-overlay {
      position: absolute;
      inset: 0;
      z-index: 1;
      display: flex;
      gap: 4px;
      align-items: center;
      justify-content: center;
      font-size: var(--ai-font-size, 12px);
      color: #fff;
      cursor: pointer;
      background: rgb(0 0 0 / 60%);
      opacity: 0;
      transition: opacity 0.2s;
    }

    &-reload-icon {
      width: 16px;
      height: 16px;
    }

    &--preview {
      cursor: zoom-in;
    }

    &:hover {
      .ai-image-error-overlay {
        opacity: 1;
      }
    }
  }
</style>
