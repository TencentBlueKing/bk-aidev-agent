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
  type MaybeRef,
  computed,
  customRef,
  inject,
  onMounted,
  onScopeDispose,
  provide,
  shallowRef,
  toValue,
  watchEffect,
} from 'vue';

export const CONTAINER_SCROLL_TOKEN = Symbol('CONTAINER_SCROLL_TOKEN');
export const SHOW_SCROLL_BOTTOM_BTN_DISTANCE = 100;
/**
 * 距底部超过该距离时视为大跨度定位（首屏渲染、切换会话、异步内容撑高），
 * 此时直接瞬时贴底；平滑滚动只用于流式输出过程中的小幅跟随。
 */
export const INSTANT_SCROLL_DISTANCE = 600;
export type ContainerScrollData = {
  autoScrollEnabled: boolean;
  isScrollBottom: boolean;
  jumpToBottom: () => void;
  scrollBottomHeight: number;
  toScrollBottom: (behavior?: ScrollBehavior) => void;
  toScrollTop: () => void;
};

export const useContainerScrollProvider = (
  containerRef: MaybeRef<HTMLElement | null>,
  bottomRef: MaybeRef<HTMLElement | null>,
) => {
  // 是否滚动到底部
  const isScrollBottom = shallowRef(false);
  // 底部滚动观察器
  let bottomObserver: IntersectionObserver | null = null;
  const scrollBottomHeight = shallowRef<number>(0);
  // 用户手动向上滚动时禁用自动滚动，回到底部后恢复
  const autoScrollEnabled = shallowRef(true);
  /**
   * 防抖显示"返回底部"按钮
   */
  const debouncedShowScrollBottomBtn = customRef((track: () => void, trigger: () => void) => {
    let timeout: ReturnType<typeof setTimeout> | undefined = undefined;
    let show = false;
    return {
      get() {
        track();
        return show;
      },
      set(newValue: boolean) {
        if (newValue === false) {
          show = false;
          timeout && clearTimeout(timeout);
          trigger();
          return;
        }
        if (timeout) clearTimeout(timeout);
        timeout = setTimeout(() => {
          show = newValue;
          trigger();
        }, 300);
      },
    };
  });

  const provideData = computed(() => ({
    autoScrollEnabled: autoScrollEnabled.value,
    isScrollBottom,
    scrollBottomHeight,
    debouncedShowScrollBottomBtn,
    jumpToBottom,
    toScrollBottom,
    toScrollTop,
  }));

  provide(CONTAINER_SCROLL_TOKEN, provideData);

  /**
   * 当前距离底部的像素距离
   */
  const getDistanceToBottom = () => {
    const container = toValue(containerRef);
    if (!container) return 0;
    return Math.max(0, container.scrollHeight - container.scrollTop - container.clientHeight);
  };

  /**
   * 瞬时贴底，不产生滚动动画
   */
  const jumpToBottom = () => {
    const container = toValue(containerRef);
    if (!container) return;
    autoScrollEnabled.value = true;
    container.scrollTop = container.scrollHeight;
  };

  /**
   * 滚动到底部
   * @param behavior 缺省时按距底部距离自动选择，距离过大则瞬时贴底，避免长距离平滑滚动动画
   */
  const toScrollBottom = (behavior?: ScrollBehavior) => {
    autoScrollEnabled.value = true;
    const resolved = behavior ?? (getDistanceToBottom() > INSTANT_SCROLL_DISTANCE ? 'auto' : 'smooth');
    if (resolved === 'auto') {
      jumpToBottom();
      return;
    }
    toValue(bottomRef)?.scrollIntoView({ behavior: resolved, block: 'end' });
  };

  /**
   * 滚动到顶部
   */
  const toScrollTop = () => {
    toValue(containerRef)?.scrollTo({ top: 0, behavior: 'smooth' });
  };

  /**
   * 计算距离底部的距离
   */
  const calculateScrollBottom = () => {
    const container = toValue(containerRef);
    if (!container) return;
    const { scrollHeight, scrollTop, clientHeight } = container;
    const distance = scrollHeight - scrollTop - clientHeight;
    scrollBottomHeight.value = Math.max(0, distance);
    debouncedShowScrollBottomBtn.value =
      !isScrollBottom.value && scrollBottomHeight.value > SHOW_SCROLL_BOTTOM_BTN_DISTANCE;
  };

  const handleWheel = (event: WheelEvent) => {
    if (event.deltaY < 0) {
      autoScrollEnabled.value = false;
    }
  };

  /**
   * 监听底部滚动
   */
  onMounted(() => {
    watchEffect(() => {
      const container = toValue(containerRef);
      const bottom = toValue(bottomRef);
      if (!container || !bottom) return;

      // 清理旧的观察器和事件监听器
      bottomObserver?.disconnect();
      container.removeEventListener('scroll', calculateScrollBottom);
      container.removeEventListener('wheel', handleWheel);

      // 初始化计算
      calculateScrollBottom();

      // 创建底部观察器
      bottomObserver = new IntersectionObserver(entries => {
        entries.forEach(entry => {
          if (entry.isIntersecting) {
            isScrollBottom.value = true;
            scrollBottomHeight.value = 0;
            autoScrollEnabled.value = true;
            debouncedShowScrollBottomBtn.value = false;
          } else {
            isScrollBottom.value = false;
            calculateScrollBottom();
          }
        });
      });
      bottomObserver.observe(bottom);

      // 监听滚动事件，实时更新距离
      container.addEventListener('scroll', calculateScrollBottom, { passive: true });
      // 监听 wheel 事件，检测用户手动向上滚动
      container.addEventListener('wheel', handleWheel, { passive: true });
    });
  });

  onScopeDispose(() => {
    bottomObserver?.disconnect();
    const container = toValue(containerRef);
    if (container) {
      container.removeEventListener('scroll', calculateScrollBottom);
      container.removeEventListener('wheel', handleWheel);
    }
  });
  return {
    autoScrollEnabled,
    isScrollBottom,
    scrollBottomHeight,
    jumpToBottom,
    toScrollBottom,
    toScrollTop,
    debouncedShowScrollBottomBtn,
  };
};

export const useContainerScrollConsumer = () => {
  return inject<ComputedRef<ContainerScrollData> | undefined>(CONTAINER_SCROLL_TOKEN, undefined);
};
