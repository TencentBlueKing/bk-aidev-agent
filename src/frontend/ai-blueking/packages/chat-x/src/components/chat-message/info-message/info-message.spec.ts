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

import { type VueWrapper, mount } from '@vue/test-utils';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import InfoMessage from './info-message.vue';

describe('InfoMessage', () => {
  let wrapper: VueWrapper;

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    wrapper?.unmount();
  });

  describe('渲染测试', () => {
    it('应该正确渲染组件', () => {
      wrapper = mount(InfoMessage, {
        props: {
          content: '信息消息',
        },
      });

      expect(wrapper.find('.ai-info-message').exists()).toBe(true);
    });

    it('应该正确渲染字符串 content', () => {
      const content = '这是一条信息消息';

      wrapper = mount(InfoMessage, {
        props: { content },
      });

      expect(wrapper.find('.ai-info-message-content').text()).toBe(content);
    });

    it('应该正确渲染数组 content', () => {
      const content = ['消息1', '消息2', '消息3'];

      wrapper = mount(InfoMessage, {
        props: { content },
      });

      const items = wrapper.findAll('.ai-info-message-content');
      expect(items.length).toBe(3);
      expect(items[0].text()).toBe('消息1');
      expect(items[1].text()).toBe('消息2');
      expect(items[2].text()).toBe('消息3');
    });

    it('content 节点应位于 body 容器内', () => {
      wrapper = mount(InfoMessage, {
        props: {
          content: ['消息1', '消息2'],
        },
      });

      const body = wrapper.find('.ai-info-message-body');
      expect(body.exists()).toBe(true);
      expect(body.findAll('.ai-info-message-content').length).toBe(2);
    });
  });

  describe('Props 测试', () => {
    it('应该正确接收 content 属性', () => {
      const content = '测试内容';

      wrapper = mount(InfoMessage, {
        props: { content },
      });

      expect((wrapper.props() as { content: string }).content).toBe(content);
    });
  });

  describe('边界情况测试', () => {
    it('应该处理空字符串 content', () => {
      wrapper = mount(InfoMessage, {
        props: {
          content: '',
        },
      });

      expect(wrapper.find('.ai-info-message').exists()).toBe(true);
    });

    it('应该处理空数组 content', () => {
      wrapper = mount(InfoMessage, {
        props: {
          content: [],
        },
      });

      expect(wrapper.find('.ai-info-message').exists()).toBe(true);
      expect(wrapper.findAll('.ai-info-message-content').length).toBe(0);
    });

    it('应该处理 undefined content', () => {
      wrapper = mount(InfoMessage, {
        props: {},
      });

      expect(wrapper.find('.ai-info-message').exists()).toBe(true);
    });

    it('应该处理单元素数组 content', () => {
      wrapper = mount(InfoMessage, {
        props: {
          content: ['单条消息'],
        },
      });

      expect(wrapper.findAll('.ai-info-message-content').length).toBe(1);
      expect(wrapper.find('.ai-info-message-content').text()).toBe('单条消息');
    });

    it('应该处理特殊字符的 content', () => {
      const content = '<script>alert("xss")</script>';

      wrapper = mount(InfoMessage, {
        props: { content },
      });

      expect(wrapper.find('.ai-info-message-content').text()).toBe(content);
      expect(wrapper.find('script').exists()).toBe(false);
    });
  });

  describe('分叉点分隔线测试', () => {
    const forkInfo = { source_session_code: 'a1b2c3d4', source_content_id: 1052, last_copied_content_id: 1053 };

    it('存在 fork_info 时应渲染图标与「从其他会话中继续」文案，不渲染后端 content', () => {
      wrapper = mount(InfoMessage, {
        props: { content: '其他会话中继续', property: { fork_info: forkInfo } },
      });

      expect(wrapper.find('.ai-info-message').classes()).toContain('is-fork');
      expect(wrapper.find('.ai-info-message-fork-icon').exists()).toBe(true);
      expect(wrapper.find('.ai-info-message-fork-text').text()).toBe('从其他会话中继续');
      expect(wrapper.find('.ai-info-message-content').exists()).toBe(false);
    });

    it('点击分隔线应以 fork_info 调用 onForkSourceClick', async () => {
      const onForkSourceClick = vi.fn();
      wrapper = mount(InfoMessage, {
        props: { content: '其他会话中继续', property: { fork_info: forkInfo }, onForkSourceClick },
      });

      await wrapper.find('.ai-info-message-fork').trigger('click');
      expect(onForkSourceClick).toHaveBeenCalledWith(forkInfo);
    });

    it('键盘回车应同样触发 onForkSourceClick', async () => {
      const onForkSourceClick = vi.fn();
      wrapper = mount(InfoMessage, {
        props: { content: '其他会话中继续', property: { fork_info: forkInfo }, onForkSourceClick },
      });

      await wrapper.find('.ai-info-message-fork').trigger('keydown', { key: 'Enter' });
      expect(onForkSourceClick).toHaveBeenCalledTimes(1);
    });

    it('没有 fork_info 时保持普通提示渲染', () => {
      wrapper = mount(InfoMessage, {
        props: { content: '普通提示', property: {} },
      });

      expect(wrapper.find('.ai-info-message').classes()).not.toContain('is-fork');
      expect(wrapper.find('.ai-info-message-fork').exists()).toBe(false);
      expect(wrapper.find('.ai-info-message-content').text()).toBe('普通提示');
    });
  });

  describe('样式测试', () => {
    it('应该具有正确的类名结构', () => {
      wrapper = mount(InfoMessage, {
        props: {
          content: '消息',
        },
      });

      expect(wrapper.find('.ai-info-message').exists()).toBe(true);
      expect(wrapper.find('.ai-info-message-body').exists()).toBe(true);
      expect(wrapper.find('.ai-info-message-content').exists()).toBe(true);
    });
  });
});
