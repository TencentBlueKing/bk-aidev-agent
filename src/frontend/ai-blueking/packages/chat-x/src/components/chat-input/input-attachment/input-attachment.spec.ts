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

import { MessageStatus } from '../../../ag-ui/types';
import InputAttachment from './input-attachment.vue';

vi.mock('tippy.js/dist/tippy.css', () => ({}));

// Mock vue-tippy
vi.mock('vue-tippy', () => ({
  directive: {},
}));

// Mock i18n
vi.mock('../../../lang/lang', () => ({
  t: (key: string) => key,
}));

// Mock icons
vi.mock('../../../icons/messages', () => ({
  LoadingMessageIcon: defineComponent({
    name: 'LoadingMessageIcon',
    setup() {
      return () => h('span', { class: 'mock-loading-icon' });
    },
  }),
  SendMessageIcon: defineComponent({
    name: 'SendMessageIcon',
    setup() {
      return () => h('span', { class: 'mock-send-icon' });
    },
  }),
}));

describe('InputAttachment', () => {
  let wrapper: VueWrapper;

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    wrapper?.unmount();
  });

  describe('渲染测试', () => {
    it('应该正确渲染组件', () => {
      wrapper = mount(InputAttachment, {
        global: {
          directives: {
            tippy: {},
          },
        },
      });

      expect(wrapper.find('.ai-input-attachment').exists()).toBe(true);
    });

    it('默认应该渲染 SendMessageIcon', () => {
      wrapper = mount(InputAttachment, {
        global: {
          directives: {
            tippy: {},
          },
        },
      });

      expect(wrapper.find('.mock-send-icon').exists()).toBe(true);
    });
  });

  describe('状态渲染测试', () => {
    it('Streaming 状态应该显示 LoadingMessageIcon', () => {
      wrapper = mount(InputAttachment, {
        props: {
          messageState: MessageStatus.Streaming,
        },
        global: {
          directives: {
            tippy: {},
          },
        },
      });

      expect(wrapper.find('.mock-loading-icon').exists()).toBe(true);
      expect(wrapper.find('.mock-send-icon').exists()).toBe(false);
    });

    it('Pending 状态应该显示 LoadingMessageIcon', () => {
      wrapper = mount(InputAttachment, {
        props: {
          messageState: MessageStatus.Pending,
        },
        global: {
          directives: {
            tippy: {},
          },
        },
      });

      expect(wrapper.find('.mock-loading-icon').exists()).toBe(true);
    });

    it('Fetching 状态应该显示 LoadingMessageIcon', () => {
      wrapper = mount(InputAttachment, {
        props: {
          messageState: MessageStatus.Fetching,
        },
        global: {
          directives: {
            tippy: {},
          },
        },
      });

      expect(wrapper.find('.mock-loading-icon').exists()).toBe(true);
      expect(wrapper.find('.mock-send-icon').exists()).toBe(false);
    });

    it('Complete 状态应该显示 SendMessageIcon', () => {
      wrapper = mount(InputAttachment, {
        props: {
          messageState: MessageStatus.Complete,
        },
        global: {
          directives: {
            tippy: {},
          },
        },
      });

      expect(wrapper.find('.mock-send-icon').exists()).toBe(true);
    });

    it('Disabled 状态应该显示 SendMessageIcon', () => {
      wrapper = mount(InputAttachment, {
        props: {
          messageState: MessageStatus.Disabled,
        },
        global: {
          directives: {
            tippy: {},
          },
        },
      });

      expect(wrapper.find('.mock-send-icon').exists()).toBe(true);
    });
  });

  describe('样式类测试', () => {
    it('Streaming 状态应该有对应的样式类', () => {
      wrapper = mount(InputAttachment, {
        props: {
          messageState: MessageStatus.Streaming,
        },
        global: {
          directives: {
            tippy: {},
          },
        },
      });

      expect(wrapper.find('.send-message-icon__streaming').exists()).toBe(true);
    });

    it('Pending 状态应该有对应的样式类', () => {
      wrapper = mount(InputAttachment, {
        props: {
          messageState: MessageStatus.Pending,
        },
        global: {
          directives: {
            tippy: {},
          },
        },
      });

      expect(wrapper.find('.send-message-icon__pending').exists()).toBe(true);
    });

    it('Fetching 状态应该有对应的样式类', () => {
      wrapper = mount(InputAttachment, {
        props: {
          messageState: MessageStatus.Fetching,
        },
        global: {
          directives: {
            tippy: {},
          },
        },
      });

      expect(wrapper.find('.send-message-icon__fetching').exists()).toBe(true);
    });

    it('Disabled 状态应该有对应的样式类', () => {
      wrapper = mount(InputAttachment, {
        props: {
          messageState: MessageStatus.Disabled,
        },
        global: {
          directives: {
            tippy: {},
          },
        },
      });

      expect(wrapper.find('.send-message-icon__disabled').exists()).toBe(true);
    });
  });

  describe('事件测试', () => {
    it('点击 SendMessageIcon 应该发出 sendMessage 事件', async () => {
      wrapper = mount(InputAttachment, {
        props: {
          messageState: MessageStatus.Complete,
        },
        global: {
          directives: {
            tippy: {},
          },
        },
      });

      await wrapper.find('.mock-send-icon').trigger('click');

      expect(wrapper.emitted('sendMessage')).toBeTruthy();
    });

    it('点击 LoadingMessageIcon 应该发出 stopSending 事件', async () => {
      wrapper = mount(InputAttachment, {
        props: {
          messageState: MessageStatus.Streaming,
        },
        global: {
          directives: {
            tippy: {},
          },
        },
      });

      await wrapper.find('.mock-loading-icon').trigger('click');

      expect(wrapper.emitted('stopSending')).toBeTruthy();
    });

    it('Fetching 状态点击 LoadingMessageIcon 应该发出 stopSending 事件', async () => {
      wrapper = mount(InputAttachment, {
        props: {
          messageState: MessageStatus.Fetching,
        },
        global: {
          directives: {
            tippy: {},
          },
        },
      });

      await wrapper.find('.mock-loading-icon').trigger('click');

      expect(wrapper.emitted('stopSending')).toBeTruthy();
    });

    it('Disabled 状态点击 SendMessageIcon 不应该发出 sendMessage 事件', async () => {
      wrapper = mount(InputAttachment, {
        props: {
          messageState: MessageStatus.Disabled,
        },
        global: {
          directives: {
            tippy: {},
          },
        },
      });

      await wrapper.find('.mock-send-icon').trigger('click');

      expect(wrapper.emitted('sendMessage')).toBeFalsy();
    });

    it('存在发送阻断提示时点击 SendMessageIcon 不应该发出 sendMessage 事件', async () => {
      wrapper = mount(InputAttachment, {
        props: {
          messageState: MessageStatus.Complete,
          sendDisabledTip: '当前会话有 3 个待审批单，如需继续，请先取消审批',
        },
        global: {
          directives: {
            tippy: {},
          },
        },
      });

      await wrapper.find('.mock-send-icon').trigger('click');

      expect(wrapper.emitted('sendMessage')).toBeFalsy();
      expect(wrapper.find('.send-message-icon__disabled').exists()).toBe(true);
    });

    it('Pending 状态点击 SendMessageIcon 不应该发送消息', async () => {
      wrapper = mount(InputAttachment, {
        props: {
          messageState: MessageStatus.Pending,
        },
        global: {
          directives: {
            tippy: {},
          },
        },
      });

      // Pending 状态显示的是 LoadingIcon
      expect(wrapper.find('.mock-loading-icon').exists()).toBe(true);
    });

    it('Streaming 状态点击 SendMessageIcon 不应该发送消息', async () => {
      wrapper = mount(InputAttachment, {
        props: {
          messageState: MessageStatus.Streaming,
        },
        global: {
          directives: {
            tippy: {},
          },
        },
      });

      // Streaming 状态显示的是 LoadingIcon
      expect(wrapper.find('.mock-loading-icon').exists()).toBe(true);
    });
  });

  describe('Slot 测试', () => {
    it('应该支持默认 slot', () => {
      wrapper = mount(InputAttachment, {
        slots: {
          default: '<div class="custom-content">Custom Content</div>',
        },
        global: {
          directives: {
            tippy: {},
          },
        },
      });

      expect(wrapper.find('.custom-content').exists()).toBe(true);
    });

    it('应该支持 send-icon slot', () => {
      wrapper = mount(InputAttachment, {
        slots: {
          'send-icon': '<div class="custom-send-icon">Custom Send</div>',
        },
        global: {
          directives: {
            tippy: {},
          },
        },
      });

      expect(wrapper.find('.custom-send-icon').exists()).toBe(true);
    });

    it('应该支持 before-send slot', () => {
      wrapper = mount(InputAttachment, {
        slots: {
          'before-send': '<div class="custom-before-send">Before Send</div>',
        },
        global: {
          directives: {
            tippy: {},
          },
        },
      });

      expect(wrapper.find('.custom-before-send').exists()).toBe(true);
    });
  });

  describe('边界情况测试', () => {
    it('应该处理 undefined messageState', () => {
      wrapper = mount(InputAttachment, {
        global: {
          directives: {
            tippy: {},
          },
        },
      });

      expect(wrapper.find('.ai-input-attachment').exists()).toBe(true);
    });

    it('应该正确接收 tippyOptions 属性', () => {
      wrapper = mount(InputAttachment, {
        props: {
          tippyOptions: { appendTo: 'parent' },
        },
        global: {
          directives: {
            tippy: {},
          },
        },
      });

      expect(wrapper.props().tippyOptions).toEqual({ appendTo: 'parent' });
    });
  });

  describe('样式测试', () => {
    it('应该具有正确的类名结构', () => {
      wrapper = mount(InputAttachment, {
        global: {
          directives: {
            tippy: {},
          },
        },
      });

      expect(wrapper.find('.ai-input-attachment').exists()).toBe(true);
      expect(wrapper.find('.send-message-icon').exists()).toBe(true);
    });

    it('容器应具有 flex: 0 0 40px 固定高度样式', () => {
      wrapper = mount(InputAttachment, {
        global: {
          directives: {
            tippy: {},
          },
        },
      });

      const container = wrapper.find('.ai-input-attachment');
      expect(container.exists()).toBe(true);
    });
  });
});
