<template>
  <div class="ai-image-preview-toolbar">
    <div class="ai-image-preview-toolbar-inner">
      <span
        v-if="isMultiple"
        class="ai-image-preview-toolbar-pages"
      >
        {{ activeIndex + 1 }} / {{ total }}
      </span>
      <span
          v-if="isMultiple"
        class="ai-image-preview-toolbar-divider"
      />
      <div
        class="ai-image-preview-toolbar-btn"
        :data-tooltip="t('缩小')"
        @click="emit('zoomOut')"
      >
        <ZoomOutIcon />
      </div>
      <div
        class="ai-image-preview-toolbar-btn"
        :data-tooltip="t('放大')"
        @click="emit('zoomIn')"
      >
        <ZoomInIcon />
      </div>
      <div
        class="ai-image-preview-toolbar-btn"
        :data-tooltip="t('旋转')"
        @click="emit('rotate')"
      >
        <RotateIcon />
      </div>
      <div
        class="ai-image-preview-toolbar-btn"
        :data-tooltip="t('重置')"
        @click="emit('reset')"
      >
        <FitScreenIcon />
      </div>
      <div
        class="ai-image-preview-toolbar-btn"
        :data-tooltip="t('下载')"
        @click="emit('download')"
      >
        <DownloadIcon />
      </div>
      <template v-if="$slots.extra">
        <span class="ai-image-preview-toolbar-divider" />
        <slot name="extra" />
      </template>

      <template v-if="showInfo && currentImageInfo">
        <span class="ai-image-preview-toolbar-divider" />
        <div class="ai-image-preview-toolbar-info">
          <ImageSizeIcon class="ai-image-preview-toolbar-info-icon" />
          <span>{{ currentImageInfo.width }} px {{ t('宽') }}</span>
          <template v-if="currentImageInfo.resolution">
            <span class="ai-image-preview-toolbar-info-dot" />
            <ImageSizeIcon class="ai-image-preview-toolbar-info-icon" />
            <span>{{ currentImageInfo.resolution }}</span>
          </template>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
  import {
    DownloadIcon,
    FitScreenIcon,
    ImageSizeIcon,
    RotateIcon,
    ZoomInIcon,
    ZoomOutIcon,
  } from '../../icons/image-preview';
  import { t } from '../../lang/lang';

  defineOptions({ name: 'PreviewToolbar' });

  defineProps<{
    activeIndex: number;
    currentImageInfo?: null | { resolution?: string; width?: number };
    isMultiple: boolean;
    showInfo: boolean;
    total: number;
  }>();

  const emit = defineEmits<{
    (e: 'zoomIn'): void;
    (e: 'zoomOut'): void;
    (e: 'rotate'): void;
    (e: 'reset'): void;
    (e: 'download'): void;
  }>();
</script>

<style lang="scss">
  .ai-image-preview-toolbar {
    position: absolute;
    bottom: 48px;
    left: 50%;
    z-index: 2;
    transform: translateX(-50%);

    &-inner {
      display: flex;
      gap: 4px;
      align-items: center;
      height: 36px;
      padding: 0 12px;
      background: rgb(0 0 0 / 50%);
      border-radius: 18px;
    }

    &-btn {
      position: relative;
      display: flex;
      align-items: center;
      justify-content: center;
      width: 28px;
      height: 28px;
      color: #dcdee5;
      cursor: pointer;
      border-radius: 4px;
      transition: all 0.2s;

      &:hover {
        color: #fff;
        background: rgb(255 255 255 / 20%);
      }

      &[data-tooltip]::before {
        position: absolute;
        bottom: calc(100% + 8px);
        left: 50%;
        padding: 4px 8px;
        font-size: 12px;
        line-height: 16px;
        color: #fff;
        white-space: nowrap;
        pointer-events: none;
        content: attr(data-tooltip);
        background: #4d4f56;
        border-radius: 4px;
        opacity: 0;
        transform: translateX(-50%);
        transition: opacity 0.2s;
      }

      &[data-tooltip]::after {
        position: absolute;
        bottom: calc(100% + 4px);
        left: 50%;
        pointer-events: none;
        content: '';
        border-color: #4d4f56 transparent transparent;
        border-style: solid;
        border-width: 4px;
        opacity: 0;
        transform: translateX(-50%);
        transition: opacity 0.2s;
      }

      &[data-tooltip]:hover::before,
      &[data-tooltip]:hover::after {
        opacity: 1;
      }

      .ai-common-icon {
        width: 16px;
        height: 16px;
      }
    }

    &-pages {
      padding: 0 8px;
      font-size: var(--ai-font-size, 12px);
      line-height: 28px;
      color: #dcdee5;
      white-space: nowrap;
    }

    &-divider {
      width: 1px;
      height: 16px;
      margin: 0 4px;
      background: rgb(255 255 255 / 20%);
    }

    &-info {
      display: flex;
      gap: 4px;
      align-items: center;
      font-size: var(--ai-font-size, 12px);
      color: #dcdee5;
      white-space: nowrap;

      &-icon {
        width: 14px;
        height: 14px;
      }

      &-dot {
        width: 4px;
        height: 4px;
        background: #dcdee5;
        border-radius: 50%;
      }
    }
  }
</style>
