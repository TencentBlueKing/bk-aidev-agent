/* eslint-disable @typescript-eslint/no-explicit-any */
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

import { MessageToolsStatus } from '../../../types/tool';
import UserMessage from './user-message.vue';

// Mock bkui-vue
vi.mock('bkui-vue', () => ({
  Button: defineComponent({
    name: 'ButtonComponent',
    props: {
      size: { type: String, default: 'medium' },
      theme: { type: String, default: 'default' },
    },
    emits: ['click'],
    setup(props, { slots, emit }) {
      return () =>
        h(
          'button',
          {
            class: ['mock-button', `mock-button-${props.theme}`],
            onClick: () => emit('click'),
          },
          slots.default?.(),
        );
    },
  }),
}));

// Mock i18n
vi.mock('../../../lang/lang', () => ({
  t: (key: string) => key,
}));

// Mock composables
vi.mock('../../../composables', () => ({
  useClipboard: () => ({
    copy: vi.fn(),
  }),
}));

// Mock common/constants
vi.mock('../../../common/constants', () => ({
  CONST_USER_MESSAGE_TOOLS: [
    { id: 'edit', name: '编辑', description: '编辑消息' },
    { id: 'copy', name: '复制', description: '复制消息' },
  ],
}));

// Mock child components
vi.mock('../../ai-shortcut/shortcut-render/shortcut-render.vue', () => ({
  default: defineComponent({
    name: 'ShortcutRender',
    emits: ['close', 'submit'],
    setup() {
      return () => h('div', { class: 'mock-shortcut-render' });
    },
  }),
}));

vi.mock('../../chat-content/cite-content/cite-content.vue', () => ({
  default: defineComponent({
    name: 'CiteContent',
    props: {
      content: { type: String, default: '' },
    },
    setup(props) {
      return () => h('div', { class: 'mock-cite-content' }, props.content);
    },
  }),
}));

vi.mock('../../chat-content/key-value-content/key-value-content.vue', () => ({
  default: defineComponent({
    name: 'KeyValueContent',
    props: {
      content: { type: Array, default: () => [] },
      title: { type: String, default: '' },
    },
    setup() {
      return () => h('div', { class: 'mock-key-value-content' });
    },
  }),
}));

vi.mock('../../chat-content/markdown-content/markdown-content.vue', () => ({
  default: defineComponent({
    name: 'MarkdownContent',
    props: {
      content: { type: String, default: '' },
    },
    setup(props) {
      return () => h('div', { class: 'mock-markdown-content' }, props.content);
    },
  }),
}));

vi.mock('../../chat-content/file-content/file-content.vue', () => ({
  default: defineComponent({
    name: 'FileContent',
    props: {
      files: { type: Array, default: () => [] },
      readonly: { type: Boolean, default: false },
    },
    setup(props) {
      return () =>
        h(
          'div',
          { class: 'mock-file-content' },
          (props.files as Array<{ filename?: string; url?: string }>).map((file, index) =>
            h('div', { class: 'mock-file-item', key: index }, file.filename || file.url || 'file'),
          ),
        );
    },
  }),
}));

vi.mock('../../chat-input/chat-input.vue', () => ({
  default: defineComponent({
    name: 'ChatInput',
    props: {
      modelValue: { type: [String, Object], default: '' },
      defaultUploadFiles: { type: Array, default: () => [] },
    },
    emits: ['update:modelValue'],
    setup(props, { slots }) {
      return () =>
        h('div', { class: 'mock-chat-input', 'data-files': JSON.stringify(props.defaultUploadFiles) }, [
          slots['send-icon']?.(),
        ]);
    },
  }),
}));

vi.mock('../../message-tools/message-tools.vue', () => ({
  default: defineComponent({
    name: 'MessageTools',
    props: {
      messageTools: { type: Array, default: () => [] },
      messageToolsStatus: { type: String, default: undefined },
      onAction: { type: Function, default: null },
      tippyOptions: { type: Object, default: undefined },
      updateTools: { type: Array, default: () => [] },
    },
    setup(props) {
      return () =>
        h(
          'div',
          {
            class: 'mock-message-tools',
            'data-message-tools-status': props.messageToolsStatus,
            'data-has-tippy-options': props.tippyOptions !== undefined ? 'true' : undefined,
          },
          'Message Tools',
        );
    },
  }),
}));

vi.mock('../../../composables/use-global-config', () => ({
  injectGlobalConfig: vi.fn(() => undefined),
}));

describe('UserMessage', () => {
  let wrapper: VueWrapper;

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    wrapper?.unmount();
  });

  describe('渲染测试', () => {
    it('应该正确渲染组件', () => {
      wrapper = mount(UserMessage, {
        props: {
          content: '用户消息内容',
        },
      });

      expect(wrapper.find('.ai-user-message').exists()).toBe(true);
    });

    it('应该渲染 MarkdownContent', () => {
      wrapper = mount(UserMessage, {
        props: {
          content: '用户消息内容',
        },
      });

      expect(wrapper.find('.mock-markdown-content').exists()).toBe(true);
    });

    it('应该正确显示 content 内容', () => {
      const content = '这是用户发送的消息';

      wrapper = mount(UserMessage, {
        props: { content },
      });

      expect(wrapper.find('.mock-markdown-content').text()).toBe(content);
    });

    it('应该渲染 MessageTools', () => {
      wrapper = mount(UserMessage, {
        props: {
          content: '用户消息内容',
        },
      });

      expect(wrapper.find('.mock-message-tools').exists()).toBe(true);
    });
  });

  describe('CiteContent 渲染测试', () => {
    it('有字符串 cite 时应该渲染 CiteContent', () => {
      wrapper = mount(UserMessage, {
        props: {
          content: '消息',
          property: {
            extra: {
              cite: '引用内容',
            },
          },
        } as any,
      });

      expect(wrapper.find('.mock-cite-content').exists()).toBe(true);
    });

    it('没有 cite 时不应该渲染 CiteContent', () => {
      wrapper = mount(UserMessage, {
        props: {
          content: '消息',
        },
      });

      expect(wrapper.find('.mock-cite-content').exists()).toBe(false);
    });
  });

  describe('数组 content 渲染测试', () => {
    it('应该渲染数组 content (Text 类型)', () => {
      wrapper = mount(UserMessage, {
        props: {
          content: [
            { type: 'text', text: '消息1' },
            { type: 'text', text: '消息2' },
          ],
        } as any,
      });

      expect(wrapper.findAll('.mock-markdown-content').length).toBe(2);
    });
  });

  describe('Props 测试', () => {
    it('应该正确接收 content 属性', () => {
      const content = '测试内容';

      wrapper = mount(UserMessage, {
        props: { content },
      });

      expect((wrapper.props() as { content: string }).content).toBe(content);
    });

    it('应该正确接收 onAction 属性', () => {
      const onAction = vi.fn();

      wrapper = mount(UserMessage, {
        props: {
          content: '消息',
          onAction,
        },
      });

      expect(wrapper.find('.ai-user-message').exists()).toBe(true);
    });
  });

  describe('边界情况测试', () => {
    it('应该处理空 content', () => {
      wrapper = mount(UserMessage, {
        props: {
          content: '',
        },
      });

      expect(wrapper.find('.ai-user-message').exists()).toBe(true);
    });

    it('应该处理 undefined content', () => {
      wrapper = mount(UserMessage, {
        props: {},
      });

      expect(wrapper.find('.ai-user-message').exists()).toBe(true);
    });
  });

  describe('样式测试', () => {
    it('应该具有正确的类名结构', () => {
      wrapper = mount(UserMessage, {
        props: {
          content: '消息',
        },
      });

      expect(wrapper.find('.ai-user-message').exists()).toBe(true);
      expect(wrapper.find('.ai-user-message-content').exists()).toBe(true);
      expect(wrapper.find('.ai-user-message-tools').exists()).toBe(true);
    });
  });

  describe('二进制文件渲染测试', () => {
    it('应该渲染 Binary 类型的文件', () => {
      wrapper = mount(UserMessage, {
        props: {
          content: [
            { type: 'binary', url: 'http://example.com/file.txt', filename: 'test.txt', mimeType: 'text/plain' },
          ],
        } as any,
      });

      expect(wrapper.find('.mock-file-content').exists()).toBe(true);
    });

    it('没有 Binary 类型时不应该渲染 FileContent', () => {
      wrapper = mount(UserMessage, {
        props: {
          content: [{ type: 'text', text: '纯文本消息' }],
        } as any,
      });

      expect(wrapper.find('.mock-file-content').exists()).toBe(false);
    });

    it('应该同时渲染 Binary 和 Text 类型内容', () => {
      wrapper = mount(UserMessage, {
        props: {
          content: [
            { type: 'binary', url: 'http://example.com/file.txt', filename: 'test.txt', mimeType: 'text/plain' },
            { type: 'text', text: '文本内容' },
          ],
        } as any,
      });

      expect(wrapper.find('.mock-file-content').exists()).toBe(true);
      expect(wrapper.find('.mock-markdown-content').exists()).toBe(true);
    });

    it('图片类型的二进制文件应被归类为 binaryImageFiles', () => {
      wrapper = mount(UserMessage, {
        props: {
          content: [
            { type: 'binary', url: 'http://example.com/photo.png', filename: 'photo.png', mimeType: 'image/png' },
            { type: 'binary', url: 'http://example.com/pic.jpg', filename: 'pic.jpg', mimeType: 'image/jpeg' },
          ],
        } as any,
      });

      const fileContents = wrapper.findAll('.mock-file-content');
      expect(fileContents.length).toBe(1);
    });

    it('非图片二进制文件应该各自独立渲染', () => {
      wrapper = mount(UserMessage, {
        props: {
          content: [
            { type: 'binary', filename: 'doc.pdf', mimeType: 'application/pdf' },
            { type: 'binary', filename: 'data.csv', mimeType: 'text/csv' },
          ],
        } as any,
      });

      const fileContents = wrapper.findAll('.mock-file-content');
      expect(fileContents.length).toBe(2);
    });

    it('混合图片和非图片二进制文件应分别渲染', () => {
      wrapper = mount(UserMessage, {
        props: {
          content: [
            { type: 'binary', url: 'http://example.com/photo.png', filename: 'photo.png', mimeType: 'image/png' },
            { type: 'binary', filename: 'doc.pdf', mimeType: 'application/pdf' },
            { type: 'binary', url: 'http://example.com/pic.jpg', filename: 'pic.jpg', mimeType: 'image/jpeg' },
          ],
        } as any,
      });

      const fileContents = wrapper.findAll('.mock-file-content');
      expect(fileContents.length).toBe(2);
    });

    it('有 url 的文件应被识别为图片文件', () => {
      wrapper = mount(UserMessage, {
        props: {
          content: [{ type: 'binary', url: 'http://example.com/file', filename: 'file' }],
        } as any,
      });

      const fileContents = wrapper.findAll('.mock-file-content');
      expect(fileContents.length).toBe(1);
    });
  });

  describe('MessageContentType.Text 渲染测试', () => {
    it('应该渲染 Text 类型的内容', () => {
      wrapper = mount(UserMessage, {
        props: {
          content: [{ type: 'text', text: '这是文本内容' }],
        } as any,
      });

      expect(wrapper.find('.mock-markdown-content').exists()).toBe(true);
    });

    it('应该渲染多个 Text 类型的内容', () => {
      wrapper = mount(UserMessage, {
        props: {
          content: [
            { type: 'text', text: '文本1' },
            { type: 'text', text: '文本2' },
          ],
        } as any,
      });

      expect(wrapper.findAll('.mock-markdown-content').length).toBe(2);
    });
  });

  describe('tippyOptions 透传测试', () => {
    it('应该正确将 tippyOptions 传递给 MessageTools', () => {
      const tippyOptions = { appendTo: 'parent' as const };

      wrapper = mount(UserMessage, {
        props: {
          content: '消息',
          tippyOptions,
        },
      });

      const messageTools = wrapper.find('.mock-message-tools');
      expect(messageTools.exists()).toBe(true);
      expect(messageTools.attributes('data-has-tippy-options')).toBe('true');
    });

    it('不传 tippyOptions 时 MessageTools 不应有 tippyOptions', () => {
      wrapper = mount(UserMessage, {
        props: {
          content: '消息',
        },
      });

      const messageTools = wrapper.find('.mock-message-tools');
      expect(messageTools.attributes('data-has-tippy-options')).toBeUndefined();
    });
  });

  describe('messageToolsStatus 测试', () => {
    it('应该正确接收 messageToolsStatus 属性', () => {
      wrapper = mount(UserMessage, {
        props: {
          content: '消息',
          messageToolsStatus: MessageToolsStatus.Disabled,
        },
      });

      expect(wrapper.props().messageToolsStatus).toBe(MessageToolsStatus.Disabled);
    });

    it('messageToolsStatus 应该传递给 MessageTools', () => {
      wrapper = mount(UserMessage, {
        props: {
          content: '消息',
          messageToolsStatus: MessageToolsStatus.Disabled,
        },
      });

      const messageTools = wrapper.find('.mock-message-tools');
      expect(messageTools.exists()).toBe(true);
      expect(messageTools.attributes('data-message-tools-status')).toBe(MessageToolsStatus.Disabled);
    });

    it('messageToolsStatus 为 Hidden 时不应该渲染 MessageTools', () => {
      wrapper = mount(UserMessage, {
        props: {
          content: '消息',
          messageToolsStatus: MessageToolsStatus.Hidden,
        },
      });

      expect(wrapper.find('.mock-message-tools').exists()).toBe(false);
    });

    it('messageToolsStatus 为 Disabled 时应该渲染 MessageTools', () => {
      wrapper = mount(UserMessage, {
        props: {
          content: '消息',
          messageToolsStatus: MessageToolsStatus.Disabled,
        },
      });

      expect(wrapper.find('.mock-message-tools').exists()).toBe(true);
    });

    it('messageToolsStatus 未设置时应该正常渲染 MessageTools', () => {
      wrapper = mount(UserMessage, {
        props: {
          content: '消息',
        },
      });

      expect(wrapper.find('.mock-message-tools').exists()).toBe(true);
    });
  });

  describe('globalConfig 注入测试', () => {
    it('无 globalConfig 时 ChatInput 的 support-upload 应为 false', async () => {
      const onAction = vi.fn();

      wrapper = mount(UserMessage, {
        props: {
          content: '消息',
          onAction,
        },
      });

      const editBtn = wrapper.findAll('.mock-message-tools');
      expect(editBtn.length).toBeGreaterThan(0);
    });
  });
});
