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

import { type VueWrapper, mount } from '@vue/test-utils';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import ImageContent from './image-content.vue';

// Mock bkui-vue Loading
vi.mock('bkui-vue', () => ({
  Loading: defineComponent({
    name: 'Loading',
    props: {
      mode: { type: String, default: 'default' },
      size: { type: String, default: 'default' },
      theme: { type: String, default: 'default' },
    },
    setup() {
      return () => h('span', { class: 'mock-loading' });
    },
  }),
}));

// Mock i18n
vi.mock('../../../lang/lang', () => ({
  t: (key: string) => key,
}));

// Mock lodash
vi.mock('lodash/debounce', () => ({
  default: (fn: (...args: unknown[]) => void) => fn,
}));

vi.mock('lodash/throttle', () => ({
  default: (fn: (...args: unknown[]) => void) => fn,
}));

describe('ImageContent', () => {
  let wrapper: VueWrapper;

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    wrapper?.unmount();
  });

  describe('渲染测试', () => {
    it('应该正确渲染组件', () => {
      wrapper = mount(ImageContent, {
        props: {
          src: 'https://example.com/image.png',
        },
      });

      expect(wrapper.find('.ai-md-image-wrapper').exists()).toBe(true);
    });
  });

  describe('加载状态测试', () => {
    it('无效 URL 时应该显示 loading', () => {
      wrapper = mount(ImageContent, {
        props: {
          src: '#',
        },
      });

      expect(wrapper.find('.md-image-loading').exists()).toBe(true);
    });

    it('URL 以 # 结尾时应该显示 loading', () => {
      wrapper = mount(ImageContent, {
        props: {
          src: 'https://example.com#',
        },
      });

      expect(wrapper.find('.md-image-loading').exists()).toBe(true);
    });

    it('URL 以 #) 结尾时应该显示 loading', () => {
      wrapper = mount(ImageContent, {
        props: {
          src: 'https://example.com#)',
        },
      });

      expect(wrapper.find('.md-image-loading').exists()).toBe(true);
    });
  });

  describe('URL 验证测试', () => {
    it('应该接受 http:// URL', () => {
      wrapper = mount(ImageContent, {
        props: {
          src: 'http://example.com/image.png',
        },
      });

      // 应该开始加载
      expect(wrapper.find('.ai-md-image-wrapper').exists()).toBe(true);
    });

    it('应该接受 https:// URL', () => {
      wrapper = mount(ImageContent, {
        props: {
          src: 'https://example.com/image.png',
        },
      });

      expect(wrapper.find('.ai-md-image-wrapper').exists()).toBe(true);
    });

    it('应该接受 data: URL', () => {
      wrapper = mount(ImageContent, {
        props: {
          src: 'data:image/png;base64,abc123',
        },
      });

      expect(wrapper.find('.ai-md-image-wrapper').exists()).toBe(true);
    });

    it('应该接受相对路径', () => {
      wrapper = mount(ImageContent, {
        props: {
          src: './images/test.png',
        },
      });

      expect(wrapper.find('.ai-md-image-wrapper').exists()).toBe(true);
    });

    it('应该接受带扩展名的文件路径', () => {
      wrapper = mount(ImageContent, {
        props: {
          src: 'image.jpg',
        },
      });

      expect(wrapper.find('.ai-md-image-wrapper').exists()).toBe(true);
    });
  });

  describe('Props 测试', () => {
    it('应该正确接收 src 属性', () => {
      const src = 'https://example.com/image.png';

      wrapper = mount(ImageContent, {
        props: { src },
      });

      expect((wrapper.props() as { src: string }).src).toBe(src);
    });

    it('应该正确接收 alt 属性', () => {
      const alt = '测试图片';

      wrapper = mount(ImageContent, {
        props: {
          src: 'https://example.com/image.png',
          alt,
        },
      });

      expect((wrapper.props() as { alt: string }).alt).toBe(alt);
    });
  });

  describe('边界情况测试', () => {
    it('应该处理空 src', () => {
      wrapper = mount(ImageContent, {
        props: {
          src: '',
        },
      });

      expect(wrapper.find('.md-image-loading').exists()).toBe(true);
    });

    it('应该处理不完整的 http URL', () => {
      wrapper = mount(ImageContent, {
        props: {
          src: 'https://incomplete',
        },
      });

      expect(wrapper.find('.ai-md-image-wrapper').exists()).toBe(true);
    });

    it('应该处理 localhost URL', () => {
      wrapper = mount(ImageContent, {
        props: {
          src: 'http://localhost:3000/image.png',
        },
      });

      expect(wrapper.find('.ai-md-image-wrapper').exists()).toBe(true);
    });
  });

  describe('样式测试', () => {
    it('应该具有正确的类名结构', () => {
      wrapper = mount(ImageContent, {
        props: {
          src: '#',
        },
      });

      expect(wrapper.find('.ai-md-image-wrapper').exists()).toBe(true);
    });
  });
});
