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
import {
  type ComputedRef,
  type ShallowRef,
  type TemplateRef,
  nextTick,
  onMounted,
  onScopeDispose,
  shallowRef,
  watch,
} from 'vue';

import type { ShortcutBtn } from '../components';

export const useObserverVisibleList = <T>(
  containerRef: TemplateRef<HTMLElement>,
  itemRefs: ShallowRef<(HTMLElement | null)[]>,
  params: {
    gap: number;
    items: ComputedRef<T[]>;
    moreItemRef?: TemplateRef<InstanceType<typeof ShortcutBtn>>;
  },
) => {
  const visibleItems = shallowRef<T[]>([]);

  /**
   * 计算哪些按钮可以显示
   */
  const calculateVisibleMenuItems = async () => {
    if (!containerRef.value || itemRefs.value.length === 0) return;
    await nextTick();
    const containerWidth = containerRef.value.offsetWidth;
    const list = new Set<T>();
    let totalWidth = 0;
    // 遍历计算哪些可以显示
    for (let i = 0; i < params.items.value.length; i++) {
      const itemRef = itemRefs.value[i];
      if (!itemRef) continue;

      const buttonWidth = itemRef.offsetWidth;
      const neededWidth = totalWidth + buttonWidth + (list.size > 0 ? params.gap : 0);

      // 如果加上 more 按钮的宽度后还能放下当前按钮，就显示它
      // 否则需要显示 more 按钮
      const shortcut = params.items.value[i];
      const moreItemWidth = params.moreItemRef?.value?.$el?.offsetWidth ?? 0;
      if (shortcut && neededWidth + params.gap + moreItemWidth <= containerWidth) {
        list.add(shortcut);
        totalWidth = neededWidth;
      } else {
        break;
      }
    }
    visibleItems.value = Array.from(list);
  };

  let resizeObserver: null | ResizeObserver = null;

  watch([itemRefs, params.moreItemRef], () => {
    nextTick(() => {
      calculateVisibleMenuItems();
    });
  });

  onMounted(() => {
    if (containerRef.value) {
      resizeObserver = new ResizeObserver(() => {
        calculateVisibleMenuItems();
      });
      resizeObserver.observe(containerRef.value);
    }
    nextTick(() => {
      calculateVisibleMenuItems();
    });
  });

  onScopeDispose(() => {
    resizeObserver?.disconnect();
  });

  return {
    visibleItems,
    calculateVisibleMenuItems,
  };
};
