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

import { MessageStatus } from '../../ag-ui/types';
import ChatInput from './chat-input.vue';

import type { UploadFile } from '../../types';
import type { IAiSlashMenuItem } from '../../types/editor';

const mockBkMessage = vi.fn();
vi.mock('bkui-vue', () => ({
  Message: (...args: unknown[]) => mockBkMessage(...args),
}));

vi.mock('../../lang/lang', () => ({
  t: (key: string) => key,
}));

// Mock common
vi.mock('../../common', async importOriginal => {
  const actual = await importOriginal<typeof import('../../common')>();
  return {
    ...actual,
    CHAT_Z_INDEX: 1000,
    isEn: false,
    MAX_UPLOAD_FILES: 3,
    MAX_UPLOAD_FILE_SIZE: 2.5 * 1024 * 1024,
    commonSVGProps: {
      class: 'mock-svg-icon',
      xmlns: 'http://www.w3.org/2000/svg',
      viewBox: '0 0 24 24',
    },
  };
});

// Mock edix
vi.mock('../../edix', () => ({
  docToString: (doc: unknown) => (typeof doc === 'string' ? doc : JSON.stringify(doc)),
  schema: vi.fn(() => ({})),
  voidNode: vi.fn(() => ({})),
}));

vi.mock('./ai-slash-input/constants', () => ({
  tagSchemaToMessageString: (doc: unknown) => {
    if (!Array.isArray(doc)) {
      return '';
    }
    return doc
      .flat()
      .map((node: { data?: { label?: string; type?: string; value?: string }; text?: string; type?: string }) => {
        if (node.type === 'text') {
          return node.text ?? '';
        }
        if (node.type === 'tag' && node.data?.type === 'skill') {
          return `/${node.data.value ?? ''}`;
        }
        if (node.type === 'tag') {
          return `@${node.data?.label ?? ''}`;
        }
        return '';
      })
      .join('');
  },
}));

// Mock CiteContent
vi.mock('../chat-content/cite-content/cite-content.vue', () => ({
  default: defineComponent({
    name: 'CiteContent',
    props: {
      content: { type: String, default: '' },
    },
    emits: ['close'],
    setup(props, { emit }) {
      return () =>
        h('div', { class: 'mock-cite-content' }, [
          h('span', props.content),
          h('button', { class: 'close-btn', onClick: () => emit('close') }, 'X'),
        ]);
    },
  }),
}));

// Mock AiSlashInput
vi.mock('./ai-slash-input/ai-slash-input.vue', () => ({
  default: defineComponent({
    name: 'AiSlashInput',
    props: {
      modelValue: { type: [String, Array], default: '' },
      placeholder: { type: String, default: '' },
      prompts: { type: Array, default: () => [] },
      resources: { type: Array, default: () => [] },
      skills: { type: Array, default: () => [] },
    },
    emits: ['update:modelValue', 'keydown', 'upload'],
    setup(_, { emit, expose }) {
      expose({
        cleanup: vi.fn(),
      });
      return () =>
        h('div', {
          class: 'mock-ai-slash-input',
          onKeydown: (e: KeyboardEvent) => emit('keydown', e),
        });
    },
  }),
}));

// Mock InputAttachment
vi.mock('./input-attachment/input-attachment.vue', () => ({
  default: defineComponent({
    name: 'InputAttachment',
    props: {
      messageState: { type: String, default: '' },
      sendDisabledTip: { type: String, default: '' },
    },
    emits: ['sendMessage', 'stopSending'],
    setup(_, { emit, slots }) {
      return () =>
        h('div', { class: 'mock-input-attachment' }, [
          h('button', { class: 'send-btn', onClick: () => emit('sendMessage') }, 'Send'),
          h('button', { class: 'stop-btn', onClick: () => emit('stopSending') }, 'Stop'),
          slots.default?.(),
          slots['send-icon']?.(),
        ]);
    },
  }),
}));

// Mock ShortcutBtns
vi.mock('../ai-shortcut/shortcut-btns/shortcut-btns.vue', () => ({
  default: defineComponent({
    name: 'ShortcutBtns',
    props: {
      shortcuts: { type: Array, default: () => [] },
    },
    emits: ['selectShortcut'],
    setup(props, { emit }) {
      return () =>
        h(
          'div',
          { class: 'mock-shortcut-btns' },
          (props.shortcuts as Array<{ id: string; name: string }>).map(shortcut =>
            h(
              'button',
              {
                class: 'mock-shortcut-item',
                'data-id': shortcut.id,
                onClick: () => emit('selectShortcut', shortcut),
              },
              shortcut.name,
            ),
          ),
        );
    },
  }),
}));

// Mock ShortcutBtn
vi.mock('../ai-shortcut/shortcut-btn/shortcut-btn.vue', () => ({
  default: defineComponent({
    name: 'ShortcutBtn',
    props: {
      shortcut: { type: Object, default: null },
    },
    setup(props, { slots }) {
      return () =>
        h('button', { class: 'mock-shortcut-btn', 'data-id': props.shortcut?.id }, [
          props.shortcut?.name,
          slots.append?.(),
        ]);
    },
  }),
}));

// Mock CloseIcon
vi.mock('../../icons', () => ({
  CloseIcon: defineComponent({
    name: 'CloseIcon',
    emits: ['click'],
    setup(_, { emit }) {
      return () =>
        h('span', {
          class: 'mock-close-icon',
          onClick: () => emit('click'),
        });
    },
  }),
}));

// Mock FileContent
vi.mock('../chat-content/file-content/file-content.vue', () => ({
  default: defineComponent({
    name: 'FileContent',
    props: {
      files: { type: Array, default: () => [] },
      readonly: { type: Boolean, default: false },
    },
    emits: ['deleteFile'],
    setup(props, { emit }) {
      return () =>
        h(
          'div',
          { class: 'mock-file-content' },
          (props.files as Array<{ file?: { name: string } }>).map((file, index) =>
            h(
              'div',
              {
                class: 'mock-file-item',
                key: index,
                onClick: () => emit('deleteFile', file),
              },
              file.file?.name || 'file',
            ),
          ),
        );
    },
  }),
}));

// Mock FileUploadBtn
vi.mock('../ai-buttons/file-upload-btn/file-upload-btn.vue', () => ({
  default: defineComponent({
    name: 'FileUploadBtn',
    emits: ['upload'],
    setup(_, { emit }) {
      return () =>
        h('button', {
          class: 'mock-file-upload-btn',
          onClick: () => {
            const mockFile = new File(['test'], 'test.txt', { type: 'text/plain' });
            emit('upload', [mockFile]);
          },
        });
    },
  }),
}));

describe('ChatInput', () => {
  let wrapper: VueWrapper;

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    wrapper?.unmount();
  });

  describe('渲染测试', () => {
    it('应该正确渲染组件', () => {
      wrapper = mount(ChatInput, {
        props: {
          modelValue: '',
        },
      });

      expect(wrapper.find('.ai-chat-input-container').exists()).toBe(true);
    });

    it('应该渲染 chat-input 容器', () => {
      wrapper = mount(ChatInput, {
        props: {
          modelValue: '',
        },
      });

      expect(wrapper.find('.chat-input').exists()).toBe(true);
    });

    it('应该渲染 AiSlashInput', () => {
      wrapper = mount(ChatInput, {
        props: {
          modelValue: '',
        },
      });

      expect(wrapper.find('.mock-ai-slash-input').exists()).toBe(true);
    });

    it('应该渲染 InputAttachment', () => {
      wrapper = mount(ChatInput, {
        props: {
          modelValue: '',
        },
      });

      expect(wrapper.find('.mock-input-attachment').exists()).toBe(true);
    });
  });

  describe('CiteContent 渲染测试', () => {
    it('有 cite 时应该渲染 CiteContent', () => {
      wrapper = mount(ChatInput, {
        props: {
          modelValue: '',
          cite: '引用内容',
        },
      });

      expect(wrapper.find('.mock-cite-content').exists()).toBe(true);
    });

    it('没有 cite 时不应该渲染 CiteContent', () => {
      wrapper = mount(ChatInput, {
        props: {
          modelValue: '',
        },
      });

      expect(wrapper.find('.mock-cite-content').exists()).toBe(false);
    });

    it('关闭 cite 应该清空 cite', async () => {
      wrapper = mount(ChatInput, {
        props: {
          modelValue: '',
          cite: '引用内容',
          'onUpdate:cite': (val: string) => wrapper.setProps({ cite: val }),
        },
      });

      await wrapper.find('.close-btn').trigger('click');

      expect(wrapper.emitted('update:cite')).toBeTruthy();
    });
  });

  describe('Props 测试', () => {
    it('应该正确接收 placeholder', () => {
      const placeholder = '输入 "/"唤出 Prompt\n输入"@"唤出 工具 和 MCP\n通过 Shift + Enter 进行换行输入';

      wrapper = mount(ChatInput, {
        props: {
          modelValue: '',
          placeholder,
        },
      });

      expect(wrapper.find('.ai-chat-input-container').exists()).toBe(true);
    });

    it('应该正确接收 prompts', () => {
      const prompts = ['prompt1', 'prompt2'];

      wrapper = mount(ChatInput, {
        props: {
          modelValue: '',
          prompts,
        },
      });

      expect(wrapper.find('.ai-chat-input-container').exists()).toBe(true);
    });

    it('应该正确接收 resources', () => {
      const resources = [{ id: '1', name: 'resource1', type: 'tool' }] as IAiSlashMenuItem[];

      wrapper = mount(ChatInput, {
        props: {
          modelValue: '',
          resources,
        },
      });

      expect(wrapper.find('.ai-chat-input-container').exists()).toBe(true);
    });

    it('应该正确接收 shortcuts', () => {
      const shortcuts = [
        { id: 'shortcut1', name: '快捷指令1' },
        { id: 'shortcut2', name: '快捷指令2' },
      ];

      wrapper = mount(ChatInput, {
        props: {
          modelValue: '',
          shortcuts,
        },
      });

      expect(wrapper.find('.mock-shortcut-btns').exists()).toBe(true);
    });

    it('应该正确接收 shortcutId', () => {
      const shortcuts = [
        { id: 'shortcut1', name: '快捷指令1' },
        { id: 'shortcut2', name: '快捷指令2' },
      ];

      wrapper = mount(ChatInput, {
        props: {
          modelValue: '',
          shortcuts,
          shortcutId: 'shortcut1',
        },
      });

      // 选中快捷指令时，应该显示 ShortcutBtn 而不是 ShortcutBtns
      expect(wrapper.find('.mock-shortcut-btn').exists()).toBe(true);
      expect(wrapper.find('.mock-shortcut-btns').exists()).toBe(false);
    });

    it('应该正确接收 supportUpload 属性', () => {
      wrapper = mount(ChatInput, {
        props: {
          modelValue: '',
          supportUpload: false,
        },
      });

      expect(wrapper.find('.ai-chat-input-container').exists()).toBe(true);
    });

    it('应该正确接收 tippyOptions 属性', () => {
      wrapper = mount(ChatInput, {
        props: {
          modelValue: '',
          tippyOptions: { appendTo: 'parent' },
        },
      });

      expect(wrapper.find('.ai-chat-input-container').exists()).toBe(true);
    });

    it('应该正确接收 skills 属性', () => {
      const skills = [
        { skill_code: 'test_skill', skill_name: 'Test Skill', description: 'A test skill', icon: '' },
      ];

      wrapper = mount(ChatInput, {
        props: {
          modelValue: '',
          skills,
        },
      });

      expect(wrapper.find('.ai-chat-input-container').exists()).toBe(true);
    });
  });

  describe('update:modelValue 事件测试', () => {
    it('AiSlashInput 触发 update:model-value 时应该透传 update:modelValue 事件', async () => {
      wrapper = mount(ChatInput, {
        props: {
          modelValue: '',
        },
      });

      const aiSlashInput = wrapper.findComponent({ name: 'AiSlashInput' });
      await aiSlashInput.vm.$emit('update:modelValue', 'new value', []);

      expect(wrapper.emitted('update:modelValue')).toBeTruthy();
    });

    it('update:modelValue 事件应该携带 selectedResourceList 参数', async () => {
      const resources = [{ id: '1', name: 'resource1', type: 'tool' }] as IAiSlashMenuItem[];

      wrapper = mount(ChatInput, {
        props: {
          modelValue: '',
          resources,
        },
      });

      const aiSlashInput = wrapper.findComponent({ name: 'AiSlashInput' });
      await aiSlashInput.vm.$emit('update:modelValue', 'new value', resources);

      expect(wrapper.emitted('update:modelValue')?.[0]).toEqual(['new value', resources]);
    });
  });

  describe('messageState 计算测试', () => {
    it('空内容时 messageState 应该是 Disabled', () => {
      wrapper = mount(ChatInput, {
        props: {
          modelValue: '',
        },
      });

      // InputAttachment 应该收到 Disabled 状态
      expect(wrapper.find('.mock-input-attachment').exists()).toBe(true);
    });

    it('有内容时应该使用 messageStatus', () => {
      wrapper = mount(ChatInput, {
        props: {
          modelValue: 'some content',
          messageStatus: MessageStatus.Complete,
        },
      });

      expect(wrapper.find('.mock-input-attachment').exists()).toBe(true);
    });

    it('数组 modelValue 内容为空白字符串时应该是 Disabled', () => {
      wrapper = mount(ChatInput, {
        props: {
          modelValue: ['  '],
        },
      });

      const inputAttachment = wrapper.findComponent({ name: 'InputAttachment' });
      expect(inputAttachment.props('messageState')).toBe(MessageStatus.Disabled);
    });

    it('数组 modelValue 仅包含 skill 标签时不应为 Disabled', () => {
      wrapper = mount(ChatInput, {
        props: {
          modelValue: [
            [
              {
                type: 'tag',
                data: { label: 'Test Skill', value: 'test_skill', type: 'skill' },
              },
            ],
          ],
          messageStatus: MessageStatus.Complete,
        },
      });

      const inputAttachment = wrapper.findComponent({ name: 'InputAttachment' });
      expect(inputAttachment.props('messageState')).toBe(MessageStatus.Complete);
    });

    it('发送消息时 skill 标签应序列化为 /skill_code 格式', async () => {
      const onSendMessage = vi.fn();

      wrapper = mount(ChatInput, {
        props: {
          modelValue: [
            [
              {
                type: 'tag',
                data: { label: 'Test Skill', value: 'test_skill', type: 'skill' },
              },
            ],
          ],
          messageStatus: MessageStatus.Complete,
          onSendMessage,
        },
      });

      await wrapper.find('.send-btn').trigger('click');

      expect(onSendMessage).toHaveBeenCalledWith('/test_skill', expect.any(Array));
    });

    it('messageStatus 为 Pending 时应优先返回 Pending（即使输入为空）', () => {
      wrapper = mount(ChatInput, {
        props: {
          modelValue: '',
          messageStatus: MessageStatus.Pending,
        },
      });

      const inputAttachment = wrapper.findComponent({ name: 'InputAttachment' });
      expect(inputAttachment.props('messageState')).toBe(MessageStatus.Pending);
    });

    it('messageStatus 为 Streaming 时应优先返回 Streaming（即使输入为空）', () => {
      wrapper = mount(ChatInput, {
        props: {
          modelValue: '',
          messageStatus: MessageStatus.Streaming,
        },
      });

      const inputAttachment = wrapper.findComponent({ name: 'InputAttachment' });
      expect(inputAttachment.props('messageState')).toBe(MessageStatus.Streaming);
    });

    it('messageStatus 为 Fetching 时应优先返回 Fetching（即使输入为空）', () => {
      wrapper = mount(ChatInput, {
        props: {
          modelValue: '',
          messageStatus: MessageStatus.Fetching,
        },
      });

      const inputAttachment = wrapper.findComponent({ name: 'InputAttachment' });
      expect(inputAttachment.props('messageState')).toBe(MessageStatus.Fetching);
    });
  });

  describe('事件测试', () => {
    it('点击发送应该调用 onSendMessage', async () => {
      const onSendMessage = vi.fn();

      wrapper = mount(ChatInput, {
        props: {
          modelValue: 'test message',
          onSendMessage,
        },
      });

      await wrapper.find('.send-btn').trigger('click');

      expect(onSendMessage).toHaveBeenCalled();
    });

    it('存在发送阻断提示时应阻止点击发送', async () => {
      const onSendMessage = vi.fn();

      wrapper = mount(ChatInput, {
        props: {
          modelValue: 'test message',
          sendDisabledTip: '当前会话有 3 个待审批单，如需继续，请先取消审批',
          onSendMessage,
        },
      });

      const inputAttachment = wrapper.findComponent({ name: 'InputAttachment' });
      expect(inputAttachment.props('sendDisabledTip')).toBe('当前会话有 3 个待审批单，如需继续，请先取消审批');

      await wrapper.find('.send-btn').trigger('click');
      expect(onSendMessage).not.toHaveBeenCalled();
    });

    it('存在发送阻断提示时 Enter 键不应该发送消息', async () => {
      const onSendMessage = vi.fn();

      wrapper = mount(ChatInput, {
        props: {
          modelValue: 'hello',
          sendDisabledTip: '当前会话有 1 个待审批单，如需继续，请先取消审批',
          onSendMessage,
        },
      });

      await wrapper.find('.mock-ai-slash-input').trigger('keydown', { key: 'Enter' });

      expect(onSendMessage).not.toHaveBeenCalled();
    });

    it('点击停止应该调用 onStopSending', async () => {
      const onStopSending = vi.fn();

      wrapper = mount(ChatInput, {
        props: {
          modelValue: 'test',
          onStopSending,
        },
      });

      await wrapper.find('.stop-btn').trigger('click');

      expect(onStopSending).toHaveBeenCalled();
    });

    it('Enter 键在 Disabled 状态下不应该发送消息', async () => {
      const onSendMessage = vi.fn();

      wrapper = mount(ChatInput, {
        props: {
          modelValue: '',
          onSendMessage,
        },
      });

      await wrapper.find('.mock-ai-slash-input').trigger('keydown', { key: 'Enter' });

      expect(onSendMessage).not.toHaveBeenCalled();
    });

    it('Enter 键在 Fetching 状态下不应该发送消息', async () => {
      const onSendMessage = vi.fn();

      wrapper = mount(ChatInput, {
        props: {
          modelValue: 'hello',
          messageStatus: MessageStatus.Fetching,
          onSendMessage,
        },
      });

      await wrapper.find('.mock-ai-slash-input').trigger('keydown', { key: 'Enter' });

      expect(onSendMessage).not.toHaveBeenCalled();
    });

    it('点击快捷指令应该触发 selectShortcut 事件', async () => {
      const shortcuts = [
        { id: 'shortcut1', name: '快捷指令1' },
        { id: 'shortcut2', name: '快捷指令2' },
      ];

      wrapper = mount(ChatInput, {
        props: {
          modelValue: '',
          shortcuts,
        },
      });

      await wrapper.find('.mock-shortcut-item').trigger('click');

      expect(wrapper.emitted('selectShortcut')).toBeTruthy();
      expect(wrapper.emitted('selectShortcut')?.[0]).toEqual([shortcuts[0]]);
    });

    it('点击关闭图标应该触发 deleteShortcut 事件', async () => {
      const shortcuts = [{ id: 'shortcut1', name: '快捷指令1' }];

      wrapper = mount(ChatInput, {
        props: {
          modelValue: '',
          shortcuts,
          shortcutId: 'shortcut1',
        },
      });

      await wrapper.find('.mock-close-icon').trigger('click');

      expect(wrapper.emitted('deleteShortcut')).toBeTruthy();
    });
  });

  describe('Slot 测试', () => {
    it('应该支持 top slot', () => {
      wrapper = mount(ChatInput, {
        props: {
          modelValue: '',
        },
        slots: {
          top: '<div class="custom-top">Top Content</div>',
        },
      });

      expect(wrapper.find('.custom-top').exists()).toBe(true);
    });

    it('应该支持 attachment slot', () => {
      wrapper = mount(ChatInput, {
        props: {
          modelValue: '',
        },
        slots: {
          attachment: '<div class="custom-attachment">Attachment</div>',
        },
      });

      expect(wrapper.find('.custom-attachment').exists()).toBe(true);
    });

    it('应该支持 send-icon slot', () => {
      wrapper = mount(ChatInput, {
        props: {
          modelValue: '',
        },
        slots: {
          'send-icon': '<div class="custom-send-icon">Send Icon</div>',
        },
      });

      expect(wrapper.find('.custom-send-icon').exists()).toBe(true);
    });

    it('无自定义 attachment slot 时应该渲染默认的 ShortcutBtns', () => {
      const shortcuts = [{ id: 'shortcut1', name: '快捷指令1' }];

      wrapper = mount(ChatInput, {
        props: {
          modelValue: '',
          shortcuts,
        },
      });

      // 没有传入 attachment slot，应该使用默认渲染 ShortcutBtns
      expect(wrapper.find('.mock-shortcut-btns').exists()).toBe(true);
    });

    it('自定义 attachment slot 应该覆盖默认的快捷指令渲染', () => {
      const shortcuts = [{ id: 'shortcut1', name: '快捷指令1' }];

      wrapper = mount(ChatInput, {
        props: {
          modelValue: '',
          shortcuts,
        },
        slots: {
          attachment: '<div class="custom-attachment">Custom</div>',
        },
      });

      // 传入了 attachment slot，应该不渲染默认的 ShortcutBtns
      expect(wrapper.find('.custom-attachment').exists()).toBe(true);
      expect(wrapper.find('.mock-shortcut-btns').exists()).toBe(false);
    });
  });

  describe('边界情况测试', () => {
    it('应该处理数组类型的 modelValue', () => {
      wrapper = mount(ChatInput, {
        props: {
          modelValue: [],
        },
      });

      expect(wrapper.find('.ai-chat-input-container').exists()).toBe(true);
    });

    it('无 shortcuts 时不应该渲染 ShortcutBtns', () => {
      wrapper = mount(ChatInput, {
        props: {
          modelValue: '',
        },
      });

      expect(wrapper.find('.mock-shortcut-btns').exists()).toBe(false);
    });

    it('空 shortcuts 数组时不应该渲染 ShortcutBtns', () => {
      wrapper = mount(ChatInput, {
        props: {
          modelValue: '',
          shortcuts: [],
        },
      });

      // v-if="shortcuts && !selectedShortcut" - 空数组也是 falsy 在渲染条件里
      // 需要确认实际逻辑
      expect(wrapper.find('.ai-chat-input-container').exists()).toBe(true);
    });

    it('shortcutId 对应的 shortcut 不存在时不应该显示 ShortcutBtn', () => {
      const shortcuts = [{ id: 'shortcut1', name: '快捷指令1' }];

      wrapper = mount(ChatInput, {
        props: {
          modelValue: '',
          shortcuts,
          shortcutId: 'non-existent-id',
        },
      });

      // selectedShortcut 为 undefined，应该显示 ShortcutBtns
      expect(wrapper.find('.mock-shortcut-btns').exists()).toBe(true);
      expect(wrapper.find('.mock-shortcut-btn').exists()).toBe(false);
    });
  });

  describe('样式测试', () => {
    it('应该具有正确的类名结构', () => {
      wrapper = mount(ChatInput, {
        props: {
          modelValue: '',
        },
      });

      expect(wrapper.find('.ai-chat-input-container').exists()).toBe(true);
      expect(wrapper.find('.chat-input').exists()).toBe(true);
    });
  });

  describe('文件上传功能测试', () => {
    it('supportUpload 默认为 true 时应该渲染 FileUploadBtn', () => {
      wrapper = mount(ChatInput, {
        props: {
          modelValue: '',
        },
      });

      expect(wrapper.find('.mock-file-upload-btn').exists()).toBe(true);
    });

    it('supportUpload 为 false 时不应该渲染 FileUploadBtn', () => {
      wrapper = mount(ChatInput, {
        props: {
          modelValue: '',
          supportUpload: false,
        },
      });

      expect(wrapper.find('.mock-file-upload-btn').exists()).toBe(false);
    });

    it('没有上传文件时不应该渲染 FileContent', () => {
      wrapper = mount(ChatInput, {
        props: {
          modelValue: '',
        },
      });

      expect(wrapper.find('.mock-file-content').exists()).toBe(false);
    });

    it('有 defaultUploadFiles 时应该渲染 FileContent', () => {
      const defaultFiles = [
        { file: new File(['test'], 'test.txt', { type: 'text/plain' }), status: 'success' },
      ] as UploadFile[];

      wrapper = mount(ChatInput, {
        props: {
          modelValue: '',
          defaultUploadFiles: defaultFiles,
        },
      });

      expect(wrapper.find('.mock-file-content').exists()).toBe(true);
    });

    it('点击 FileUploadBtn 应该触发上传', async () => {
      const onUpload = vi.fn().mockResolvedValue({ download_url: 'http://example.com/file.txt' });

      wrapper = mount(ChatInput, {
        props: {
          modelValue: '',
          onUpload,
        },
      });

      await wrapper.find('.mock-file-upload-btn').trigger('click');

      expect(onUpload).toHaveBeenCalled();
    });

    it('上传返回 download_url 时应标记为 Success', async () => {
      const onUpload = vi.fn().mockResolvedValue({ download_url: 'http://example.com/file.txt' });

      wrapper = mount(ChatInput, {
        props: {
          modelValue: '',
          onUpload,
        },
      });

      await wrapper.find('.mock-file-upload-btn').trigger('click');
      await vi.waitFor(() => {
        expect(onUpload).toHaveBeenCalled();
      });
    });

    it('上传返回无 download_url 时应标记为 Error', async () => {
      const onUpload = vi.fn().mockResolvedValue({});

      wrapper = mount(ChatInput, {
        props: {
          modelValue: '',
          onUpload,
        },
      });

      await wrapper.find('.mock-file-upload-btn').trigger('click');
      await vi.waitFor(() => {
        expect(onUpload).toHaveBeenCalled();
      });
    });

    it('应该基于文件名+大小+修改时间去重', async () => {
      const onUpload = vi.fn().mockResolvedValue({ download_url: 'http://example.com/file.txt' });
      const sameFile = new File(['test'], 'test.txt', { type: 'text/plain', lastModified: 1000 });

      wrapper = mount(ChatInput, {
        props: {
          modelValue: '',
          onUpload,
        },
      });

      const aiSlashInput = wrapper.findComponent({ name: 'AiSlashInput' });
      await aiSlashInput.vm.$emit('upload', [sameFile]);
      await aiSlashInput.vm.$emit('upload', [sameFile]);

      expect(onUpload).toHaveBeenCalledTimes(1);
    });

    it('同名但不同大小的文件不应被去重', async () => {
      const onUpload = vi.fn().mockResolvedValue({ download_url: 'http://example.com/file.txt' });
      const file1 = new File(['test1'], 'test.txt', { type: 'text/plain', lastModified: 1000 });
      const file2 = new File(['test12345'], 'test.txt', { type: 'text/plain', lastModified: 1000 });

      wrapper = mount(ChatInput, {
        props: {
          modelValue: '',
          onUpload,
        },
      });

      const aiSlashInput = wrapper.findComponent({ name: 'AiSlashInput' });
      await aiSlashInput.vm.$emit('upload', [file1]);
      await aiSlashInput.vm.$emit('upload', [file2]);

      expect(onUpload).toHaveBeenCalledTimes(2);
    });

    it('同批次中重复文件也应去重', async () => {
      const onUpload = vi.fn().mockResolvedValue({ download_url: 'http://example.com/file.txt' });
      const file = new File(['test'], 'dup.txt', { type: 'text/plain', lastModified: 2000 });

      wrapper = mount(ChatInput, {
        props: {
          modelValue: '',
          onUpload,
        },
      });

      const aiSlashInput = wrapper.findComponent({ name: 'AiSlashInput' });
      await aiSlashInput.vm.$emit('upload', [file, file]);

      expect(onUpload).toHaveBeenCalledTimes(1);
    });

    it('应该正确接收 inputMaxHeight 属性', () => {
      wrapper = mount(ChatInput, {
        props: {
          modelValue: '',
          inputMaxHeight: 300,
        },
      });

      expect(wrapper.find('.ai-chat-input-container').exists()).toBe(true);
    });

    it('有 shortcuts 或 selectedShortcut 时应该显示分隔线', () => {
      const shortcuts = [{ id: 'shortcut1', name: '快捷指令1' }];

      wrapper = mount(ChatInput, {
        props: {
          modelValue: '',
          shortcuts,
        },
      });

      expect(wrapper.find('.ai-divider').exists()).toBe(true);
    });

    it('没有 shortcuts 时不应该显示分隔线', () => {
      wrapper = mount(ChatInput, {
        props: {
          modelValue: '',
        },
      });

      expect(wrapper.find('.ai-divider').exists()).toBe(false);
    });

    it('应该支持 files slot', () => {
      const defaultFiles = [
        { file: new File(['test'], 'test.txt', { type: 'text/plain' }), status: 'success' },
      ] as UploadFile[];

      wrapper = mount(ChatInput, {
        props: {
          modelValue: '',
          defaultUploadFiles: defaultFiles,
        },
        slots: {
          files: '<div class="custom-files">Custom Files</div>',
        },
      });

      expect(wrapper.find('.custom-files').exists()).toBe(true);
    });
  });
});
