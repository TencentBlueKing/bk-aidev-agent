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
import { type ShallowRef, nextTick, onMounted, onScopeDispose, shallowRef } from 'vue';

export const useMenuKeydown = <T>(props: {
  items: ShallowRef<T[]>;
  menuRef: Readonly<ShallowRef<HTMLElement | null>>;
  onSelect: (item: T) => void;
}) => {
  const activeIndex = shallowRef(0);
  onMounted(() => {
    window.addEventListener('keydown', handleKeydown, true);
  });

  onScopeDispose(() => {
    window.removeEventListener('keydown', handleKeydown, true);
  });

  const handleSelect = (item: T) => {
    props.onSelect?.(item);
  };
  const scrollToActive = () => {
    nextTick(() => {
      const activeEl = props.menuRef.value?.querySelector('.is-active');
      if (activeEl) {
        activeEl.scrollIntoView({ block: 'nearest' });
      }
    });
  };
  const handleKeydown = (e: KeyboardEvent) => {
    // 检查组件是否可见
    if (!props.menuRef.value?.offsetParent) return;
    if (!props.items.value?.length) return;

    if (e.key === 'ArrowUp') {
      e.preventDefault();
      e.stopPropagation();
      activeIndex.value = (activeIndex.value - 1 + props.items.value?.length) % props.items.value?.length;
      scrollToActive();
    } else if (e.key === 'ArrowDown') {
      e.preventDefault();
      e.stopPropagation();
      activeIndex.value = (activeIndex.value + 1) % props.items.value?.length;
      scrollToActive();
    } else if (e.key === 'Enter' || e.key === 'NumpadEnter') {
      e.preventDefault();
      e.stopPropagation();
      const item = props.items.value?.[activeIndex.value];
      if (item) handleSelect(item);
    }
  };
  return {
    activeIndex,
  };
};
