/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台 (BlueKing PaaS):
 *
 * ---------------------------------------------------
 * Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
 * documentation files (the "Software"), to deal in the Software without restriction, including without limitation
 * the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and
 * to permit persons to whom the Software is furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all copies or substantial portions of
 * the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
 * THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
 * CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
 * IN THE SOFTWARE.
 */

import { type MaybeRef, computed, ref, toValue, watch } from 'vue';

export interface AnimationConfig {
  easing?: string;
  fadeDuration?: number;
}

export interface UseAnimationTextOptions {
  animationConfig?: AnimationConfig;
  text: string;
}

export const useAnimationText = (text: MaybeRef<string>, options?: AnimationConfig) => {
  const { easing = 'ease-in-out', fadeDuration = 200 } = options || {};

  const chunks = ref<string[]>([]);
  const prevTextRef = ref('');

  watch(
    () => text,
    newValue => {
      const newText = toValue(newValue);
      if (newText === prevTextRef.value) return;

      if (!(prevTextRef.value && newText.indexOf(prevTextRef.value) === 0)) {
        chunks.value = [newText];
        prevTextRef.value = newText;
        return;
      }

      const newTextChunk = newText.slice(prevTextRef.value.length);
      if (!newTextChunk) return;

      chunks.value = [...chunks.value, newTextChunk];
      prevTextRef.value = newText;
    },
    { immediate: true },
  );

  const animationStyle = computed(() => ({
    animation: `ai-markdown-fade-in ${fadeDuration}ms ${easing} forwards`,
    color: 'inherit',
  }));

  return {
    chunks,
    animationStyle,
  };
};
