<!--
  Tencent is pleased to support the open source community by making
  蓝鲸智云PaaS平台 (BlueKing PaaS) available.

  Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.

  蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.

  License for 蓝鲸智云PaaS平台 (BlueKing PaaS):

  ---------------------------------------------------
  Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
  documentation files (the "Software"), to deal in the Software without restriction, including without limitation
  the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and
  to permit persons to whom the Software is furnished to do so, subject to the following conditions:

  The above copyright notice and this permission notice shall be included in all copies or substantial portions of
  the Software.

  THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
  THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
  AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
  CONTRACT, TORT OR OTHERWISE, ARISING FROM OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
  THE SOFTWARE.
-->
<template>
  <div
    class="ai-message-loading"
    :class="attrs.class"
    :style="rootStyle"
    v-bind="restAttrs"
  >
    <div class="ai-message-loading-row">
      <span class="ai-message-loading-icon-wrap">
        <slot name="icon">
          <AIBluekingIcon
            class="ai-message-loading-icon-svg"
            :style="iconStyle"
          />
        </slot>
      </span>
      <span
        v-if="$slots.text"
        class="ai-message-loading-text ai-message-loading-text-custom"
      >
        <slot name="text" />
      </span>
      <span
        v-else
        aria-live="polite"
        class="ai-message-loading-text"
      >
        <span
          v-for="(char, index) in chars"
          :key="`${index}-${char}`"
          class="ai-message-loading-char"
          :style="{ '--char-index': index }"
        >
          {{ char }}
        </span>
      </span>
    </div>
  </div>
</template>

<script setup lang="ts">
  import { computed, useAttrs } from 'vue';

  import { AIBluekingIcon } from '../../icons';

  defineOptions({ name: 'MessageLoading', inheritAttrs: false });

  const props = withDefaults(
    defineProps<{
      /** 单次循环时长（秒），与原版 motion duration 一致 */
      duration?: number;
      /** 图标与文字间距（px） */
      gap?: number;
      /** 图标边长（px），viewBox 24×24 等比缩放 */
      iconSize?: number;
      /** 相邻字符动画延迟（秒） */
      stagger?: number;
      /** 逐字动画的文案；使用插槽 #text 时可不传 */
      text?: string;
    }>(),
    {
      duration: 1.8,
      gap: 8,
      iconSize: 32,
      stagger: 0.135,
      text: '加载中...',
    },
  );

  const attrs = useAttrs();

  const restAttrs = computed(() => {
    const { class: _c, style: _s, ...rest } = attrs as Record<string, unknown>;
    return rest;
  });

  const iconStyle = computed(() => ({
    display: 'block',
    width: `${props.iconSize}px`,
    height: `${props.iconSize}px`,
  }));

  const chars = computed(() => [...props.text]);

  const rootStyle = computed(() => {
    const style = attrs.style as Record<string, number | string> | string | undefined;
    const base: Record<string, number | string> = {
      '--ai-message-loading-duration': `${props.duration}s`,
      '--ai-message-loading-stagger': `${props.stagger}s`,
      '--ai-message-loading-gap': `${props.gap}px`,
    };
    if (style && typeof style === 'object' && !Array.isArray(style)) {
      return { ...base, ...style };
    }
    return base;
  });
</script>

<style lang="scss">
  .ai-message-loading {
    box-sizing: border-box;
    display: inline-flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;

    &-row {
      display: flex;
      gap: var(--ai-message-loading-gap, 8px);
      align-items: center;
      justify-content: center;
    }

    &-icon-wrap {
      position: relative;
      flex-shrink: 0;
      transform: translateY(-2px);
      animation: ai-message-loading-icon ease-in-out infinite;
      animation-duration: var(--ai-message-loading-duration, 1.8s);
    }

    &-text {
      display: inline-flex;
      flex-shrink: 0;
      align-items: center;
      font-size: 14px;
      line-height: 20px;
      color: #63656e;
      white-space: nowrap;
    }

    &-char {
      background: linear-gradient(135deg, #235dfa 0%, #eb8cec 100%);
      background-clip: text;
      animation: ai-message-loading-char ease-in-out infinite;
      animation-duration: var(--ai-message-loading-duration, 1.8s);
      animation-delay: calc(var(--char-index, 0) * var(--ai-message-loading-stagger, 0.135s));
      -webkit-text-fill-color: transparent;
    }

    &-text-custom {
      background: linear-gradient(135deg, #235dfa 0%, #eb8cec 100%);
      background-clip: text;
      -webkit-text-fill-color: transparent;
    }
  }

  @keyframes ai-message-loading-icon {
    0%,
    100% {
      opacity: 0.3;
      filter: brightness(0.8) hue-rotate(0deg);
    }

    33.33%,
    66.66% {
      opacity: 1;
      filter: brightness(1.2) hue-rotate(10deg);
    }
  }

  @keyframes ai-message-loading-char {
    0%,
    100% {
      opacity: 0.3;
    }

    33.33%,
    66.66% {
      opacity: 1;
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .ai-message-loading-icon-wrap {
      opacity: 1;
      filter: none;
      animation: none;
    }

    .ai-message-loading-char {
      opacity: 1;
      animation: none;
    }
  }
</style>
