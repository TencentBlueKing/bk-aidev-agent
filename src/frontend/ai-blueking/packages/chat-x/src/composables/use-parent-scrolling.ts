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

import { type MaybeRef, onMounted, onScopeDispose, shallowRef, toValue } from 'vue';

/**
 * 递归获取滚动父级
 * @param node - 节点
 * @returns 滚动父级
 */
export const getScrollParent = (node: HTMLElement | null | ParentNode): HTMLElement | null => {
  if (!node) {
    return null;
  }
  if (!(node instanceof HTMLElement)) {
    const parent = 'parentElement' in node ? node.parentElement : null;
    return parent ? getScrollParent(parent) : document.body;
  }
  if (node.scrollHeight > node.clientHeight) {
    const overflowY = window.getComputedStyle(node).overflowY;
    // 检查 overflow 属性是否允许滚动
    if (overflowY === 'scroll' || overflowY === 'auto' || overflowY === 'overlay') {
      return node;
    }
  }
  const parent = node.parentElement;
  return parent ? getScrollParent(parent) : document.body;
};
/**
 * 监听父级滚动
 * @param domRef - 节点
 * @returns 是否滚动
 */
export const useParentScrolling = (domRef: MaybeRef<HTMLElement | null>) => {
  const isScrolling = shallowRef(false);
  let timer: null | ReturnType<typeof setTimeout> = null;
  const scrollParent = shallowRef<HTMLElement | null>(null);
  const handleScroll = () => {
    isScrolling.value = true;
    timer && clearTimeout(timer);
    timer = setTimeout(() => {
      isScrolling.value = false;
    }, 300);
  };
  const handleScrollEnd = () => {
    isScrolling.value = false;
  };
  onMounted(() => {
    scrollParent.value = getScrollParent(toValue(domRef));
    scrollParent.value?.removeEventListener('scroll', handleScroll);
    scrollParent.value?.removeEventListener('scrollend', handleScrollEnd);
    scrollParent.value?.addEventListener('scroll', handleScroll);
    scrollParent.value?.addEventListener('scrollend', handleScrollEnd);
  });
  onScopeDispose(() => {
    scrollParent.value?.removeEventListener('scroll', handleScroll);
    scrollParent.value?.removeEventListener('scrollend', handleScrollEnd);
  });
  return { isScrolling, scrollParent };
};
