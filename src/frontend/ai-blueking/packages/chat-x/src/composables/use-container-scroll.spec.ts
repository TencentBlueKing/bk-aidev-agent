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
import { defineComponent, h } from 'vue';

import { mount } from '@vue/test-utils';
import { beforeAll, describe, expect, it, vi } from 'vitest';

import { INSTANT_SCROLL_DISTANCE, useContainerScrollProvider } from './use-container-scroll';

beforeAll(() => {
  vi.stubGlobal(
    'IntersectionObserver',
    class {
      disconnect = vi.fn();
      observe = vi.fn();
      unobserve = vi.fn();
    },
  );
});

/**
 * jsdom 不提供真实布局，这里用可控的 scrollHeight / clientHeight / scrollTop 模拟滚动容器
 */
const createContainer = (options: { clientHeight: number; scrollHeight: number; scrollTop: number }) => {
  const el = document.createElement('div');
  let scrollTop = options.scrollTop;
  Object.defineProperty(el, 'scrollHeight', { configurable: true, value: options.scrollHeight });
  Object.defineProperty(el, 'clientHeight', { configurable: true, value: options.clientHeight });
  Object.defineProperty(el, 'scrollTop', {
    configurable: true,
    get: () => scrollTop,
    set: (value: number) => {
      scrollTop = value;
    },
  });
  return el;
};

const setup = (options: { clientHeight: number; scrollHeight: number; scrollTop: number }) => {
  const container = createContainer(options);
  const bottom = document.createElement('div');
  const scrollIntoView = vi.fn();
  bottom.scrollIntoView = scrollIntoView;

  let api: ReturnType<typeof useContainerScrollProvider>;
  const wrapper = mount(
    defineComponent({
      setup() {
        api = useContainerScrollProvider(container, bottom);
        return () => h('div');
      },
    }),
  );

  return { api: api!, container, scrollIntoView, wrapper };
};

describe('useContainerScrollProvider', () => {
  describe('toScrollBottom', () => {
    it('距底部超过阈值时瞬时贴底，不触发平滑滚动动画', () => {
      const { api, container, scrollIntoView } = setup({
        scrollHeight: 5000,
        clientHeight: 500,
        scrollTop: 0,
      });

      api.toScrollBottom();

      expect(scrollIntoView).not.toHaveBeenCalled();
      expect(container.scrollTop).toBe(5000);
    });

    it('距底部在阈值内时使用平滑滚动', () => {
      const { api, scrollIntoView } = setup({
        scrollHeight: 1000,
        clientHeight: 500,
        scrollTop: 480,
      });

      api.toScrollBottom();

      expect(scrollIntoView).toHaveBeenCalledWith({ behavior: 'smooth', block: 'end' });
    });

    it('显式指定 smooth 时即使距底部很远也保持平滑滚动', () => {
      const { api, container, scrollIntoView } = setup({
        scrollHeight: 5000,
        clientHeight: 500,
        scrollTop: 0,
      });

      api.toScrollBottom('smooth');

      expect(scrollIntoView).toHaveBeenCalledWith({ behavior: 'smooth', block: 'end' });
      expect(container.scrollTop).toBe(0);
    });

    it('恰好等于阈值时仍使用平滑滚动', () => {
      const { api, scrollIntoView } = setup({
        scrollHeight: 500 + INSTANT_SCROLL_DISTANCE,
        clientHeight: 500,
        scrollTop: 0,
      });

      api.toScrollBottom();

      expect(scrollIntoView).toHaveBeenCalledWith({ behavior: 'smooth', block: 'end' });
    });
  });

  describe('jumpToBottom', () => {
    it('瞬时贴底并恢复自动滚动', () => {
      const { api, container, scrollIntoView } = setup({
        scrollHeight: 5000,
        clientHeight: 500,
        scrollTop: 0,
      });
      api.autoScrollEnabled.value = false;

      api.jumpToBottom();

      expect(container.scrollTop).toBe(5000);
      expect(api.autoScrollEnabled.value).toBe(true);
      expect(scrollIntoView).not.toHaveBeenCalled();
    });
  });
});
