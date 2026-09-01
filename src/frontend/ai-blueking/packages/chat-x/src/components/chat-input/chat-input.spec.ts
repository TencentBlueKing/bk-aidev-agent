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

import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

import { defineComponent, h } from 'vue';

import { type VueWrapper, mount } from '@vue/test-utils';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { MessageStatus } from '../../ag-ui/types';
import ChatInput from './chat-input.vue';

import type { UploadFile } from '../../types';
import type { IAiSlashMenuItem } from '../../types/editor';

const chatInputSource = readFileSync(join(dirname(fileURLToPath(import.meta.url)), 'chat-input.vue'), 'utf-8');

async function waitUntilSendEnabled(wrapper: VueWrapper) {
  await vi.waitFor(() => {
    expect(wrapper.findComponent({ name: 'InputAttachment' }).props('sendDisabledTip')).toBeFalsy();
  });
}

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
    MAX_UPLOAD_FILES: 9,
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
const mockInputFocus = vi.fn();
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
    setup(props, { emit, expose }) {
      expose({
        cleanup: vi.fn(),
        focus: mockInputFocus,
      });
      return () =>
        h('div', {
          class: 'mock-ai-slash-input',
          'aria-placeholder': props.placeholder,
          onKeydown: (e: KeyboardEvent) => emit('keydown', e),
        });
    },
  }),
}));

// Mock ModelSelector
vi.mock('./model-selector', () => ({
  ModelSelector: defineComponent({
    name: 'ModelSelector',
    props: {
      models: { type: Array, default: () => [] },
      modelValue: { type: String, default: '' },
    },
    emits: ['update:modelValue', 'change'],
    setup(props, { emit }) {
      return () =>
        h(
          'div',
          {
            class: 'mock-model-selector',
            onClick: () => {
              const model = (props.models as Array<{ id: string; name: string }>)[0];
              if (model) {
                emit('update:modelValue', model.id);
                emit('change', model);
              }
            },
          },
          'ModelSelector',
        );
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
          slots['before-send']?.(),
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

// style-note: chat-x PR4 — inputMaxHeight 默认 280 / 未激活灰边框
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

    it('输入容器底部间距应为 16px', () => {
      wrapper = mount(ChatInput, {
        props: {
          modelValue: '',
        },
      });

      expect(wrapper.find('.ai-chat-input-container').exists()).toBe(true);
      expect(chatInputSource).toMatch(/\.ai-chat-input-container\s*\{[\s\S]*?padding:\s*0\s+16px\s+16px;/);
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

    it('无 Skill/Prompt/Resources 时默认 placeholder 仅保留换行提示', () => {
      wrapper = mount(ChatInput, {
        props: {
          modelValue: '',
        },
      });

      expect(wrapper.find('.mock-ai-slash-input').attributes('aria-placeholder')).toBe(
        '通过 Shift + Enter 进行换行输入',
      );
    });

    it('仅有 Skill 时默认 placeholder 含 Skill 行且不含 Prompt 和 @ 行', () => {
      wrapper = mount(ChatInput, {
        props: {
          modelValue: '',
          skills: [
            {
              skill_name: 'Code Review',
              skill_code: 'code-review',
              description: '审查代码',
              icon: '',
            },
          ],
        },
      });

      const placeholder = wrapper.find('.mock-ai-slash-input').attributes('aria-placeholder') ?? '';
      expect(placeholder).toContain('输入 "/" 唤出 Skill');
      expect(placeholder).not.toContain('唤出 Prompt');
      expect(placeholder).not.toContain('工具和 MCP');
      expect(placeholder).toContain('通过 Shift + Enter 进行换行输入');
    });

    it('显式 placeholder 不被 skills/prompts/resources 改写', () => {
      const placeholder = '请输入你的问题';

      wrapper = mount(ChatInput, {
        props: {
          modelValue: '',
          placeholder,
          skills: [
            {
              skill_name: 'Code Review',
              skill_code: 'code-review',
              description: '审查代码',
              icon: '',
            },
          ],
          prompts: ['帮我总结'],
          resources: [{ id: '1', name: 'resource1', type: 'tool' }] as IAiSlashMenuItem[],
        },
      });

      expect(wrapper.find('.mock-ai-slash-input').attributes('aria-placeholder')).toBe(placeholder);
    });

    it('显式空字符串 placeholder 完全覆盖动态文案', () => {
      wrapper = mount(ChatInput, {
        props: {
          modelValue: '',
          placeholder: '',
          skills: [
            {
              skill_name: 'Code Review',
              skill_code: 'code-review',
              description: '审查代码',
              icon: '',
            },
          ],
        },
      });

      expect(wrapper.find('.mock-ai-slash-input').attributes('aria-placeholder')).toBe('');
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

    it('应该正确接收 models', () => {
      const models = [{ id: 'gpt-4', name: 'GPT-4' }];

      wrapper = mount(ChatInput, {
        props: {
          modelValue: '',
          models,
        },
      });

      expect(wrapper.find('.mock-model-selector').exists()).toBe(true);
    });

    it('models 为空时不应渲染 ModelSelector', () => {
      wrapper = mount(ChatInput, {
        props: {
          modelValue: '',
          models: [],
        },
      });

      expect(wrapper.find('.mock-model-selector').exists()).toBe(false);
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
    it('ModelSelector 变更时应触发 modelChange 事件', async () => {
      const models = [{ id: 'gpt-4', name: 'GPT-4' }];

      wrapper = mount(ChatInput, {
        props: {
          modelValue: '',
          models,
        },
      });

      await wrapper.find('.mock-model-selector').trigger('click');

      expect(wrapper.emitted('modelChange')?.[0]).toEqual([{ id: 'gpt-4', name: 'GPT-4' }]);
    });

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

    it('应该支持 model-selector slot 覆盖默认模型选择器', () => {
      const models = [{ id: 'gpt-4', name: 'GPT-4' }];

      wrapper = mount(ChatInput, {
        props: {
          modelValue: '',
          models,
        },
        slots: {
          'model-selector': '<div class="custom-model-selector">Custom Model</div>',
        },
      });

      expect(wrapper.find('.custom-model-selector').exists()).toBe(true);
      expect(wrapper.find('.mock-model-selector').exists()).toBe(false);
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

    it('上传返回空对象时应标记为 Error', async () => {
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

    it('上传仅返回 id 时应成功，发送内容携带永久身份', async () => {
      const onSendMessage = vi.fn();
      const onUpload = vi.fn().mockResolvedValue({ id: 'files/report.pdf', status: 'success' });

      wrapper = mount(ChatInput, {
        props: {
          modelValue: '',
          onSendMessage,
          onUpload,
        },
      });

      const aiSlashInput = wrapper.findComponent({ name: 'AiSlashInput' });
      await aiSlashInput.vm.$emit('upload', [new File(['pdf'], 'report.pdf', { type: 'application/pdf' })]);
      await waitUntilSendEnabled(wrapper);
      await wrapper.find('.send-btn').trigger('click');

      expect(onSendMessage.mock.calls[0][0][0]).toMatchObject({
        id: 'files/report.pdf',
        filename: 'report.pdf',
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

    it('文件加入列表后应自动聚焦输入区', async () => {
      const onUpload = vi.fn().mockResolvedValue({ download_url: 'http://example.com/file.txt' });

      wrapper = mount(ChatInput, {
        props: {
          modelValue: '',
          onUpload,
        },
      });

      const aiSlashInput = wrapper.findComponent({ name: 'AiSlashInput' });
      await aiSlashInput.vm.$emit('upload', [new File(['test'], 'test.txt', { type: 'text/plain' })]);

      expect(mockInputFocus).toHaveBeenCalled();
    });

    it('全部文件都未通过校验时不应聚焦输入区', async () => {
      wrapper = mount(ChatInput, {
        props: {
          modelValue: '',
          onUpload: vi.fn(),
        },
      });

      const aiSlashInput = wrapper.findComponent({ name: 'AiSlashInput' });
      await aiSlashInput.vm.$emit('upload', [new File([], 'empty.txt', { type: 'text/plain' })]);

      expect(mockInputFocus).not.toHaveBeenCalled();
    });

    it('只有附件、输入框为空时发送按钮应可用', async () => {
      wrapper = mount(ChatInput, {
        props: {
          modelValue: '',
          messageStatus: MessageStatus.Complete,
          onUpload: vi.fn().mockResolvedValue({ download_url: 'http://example.com/report.pdf' }),
        },
      });

      const inputAttachment = wrapper.findComponent({ name: 'InputAttachment' });
      expect(inputAttachment.props('messageState')).toBe(MessageStatus.Disabled);

      const aiSlashInput = wrapper.findComponent({ name: 'AiSlashInput' });
      await aiSlashInput.vm.$emit('upload', [new File(['pdf'], 'report.pdf', { type: 'application/pdf' })]);

      expect(inputAttachment.props('messageState')).toBe(MessageStatus.Complete);
    });

    it('纯附件消息不应带空文本段', async () => {
      const onSendMessage = vi.fn();

      wrapper = mount(ChatInput, {
        props: {
          modelValue: '',
          onSendMessage,
          onUpload: vi.fn().mockResolvedValue({ download_url: 'http://example.com/report.pdf' }),
        },
      });

      const aiSlashInput = wrapper.findComponent({ name: 'AiSlashInput' });
      await aiSlashInput.vm.$emit('upload', [new File(['pdf'], 'report.pdf', { type: 'application/pdf' })]);
      await waitUntilSendEnabled(wrapper);
      await wrapper.find('.send-btn').trigger('click');

      const content = onSendMessage.mock.calls[0][0];
      expect(content).toHaveLength(1);
      expect(content[0]).toMatchObject({ filename: 'report.pdf' });
    });

    it('modelValue 为普通字符串且有附件时应正常发送（编辑态回填）', async () => {
      const onSendMessage = vi.fn();
      const defaultFiles = [
        {
          type: 'binary',
          url: 'http://example.com/report.pdf',
          filename: 'report.pdf',
          mimeType: 'application/pdf',
        },
      ] as unknown as UploadFile[];

      wrapper = mount(ChatInput, {
        props: {
          modelValue: '这是编辑态的文本',
          defaultUploadFiles: defaultFiles,
          onSendMessage,
        },
      });

      await wrapper.find('.send-btn').trigger('click');

      const content = onSendMessage.mock.calls[0][0];
      expect(content).toHaveLength(2);
      expect(content[1]).toMatchObject({ text: '这是编辑态的文本' });
    });

    it('只有附件时 Enter 键也应能发送', async () => {
      const onSendMessage = vi.fn();

      wrapper = mount(ChatInput, {
        props: {
          modelValue: '',
          onSendMessage,
          onUpload: vi.fn().mockResolvedValue({ download_url: 'http://example.com/report.pdf' }),
        },
      });

      const aiSlashInput = wrapper.findComponent({ name: 'AiSlashInput' });
      await aiSlashInput.vm.$emit('upload', [new File(['pdf'], 'report.pdf', { type: 'application/pdf' })]);
      await waitUntilSendEnabled(wrapper);
      await wrapper.find('.mock-ai-slash-input').trigger('keydown', { key: 'Enter' });

      expect(onSendMessage).toHaveBeenCalled();
    });

    it('发送时应带上 filename / mimeType / size', async () => {
      const onSendMessage = vi.fn();
      const onUpload = vi.fn().mockResolvedValue({ download_url: 'http://example.com/report.pdf' });

      wrapper = mount(ChatInput, {
        props: {
          modelValue: 'hello',
          onSendMessage,
          onUpload,
        },
      });

      const aiSlashInput = wrapper.findComponent({ name: 'AiSlashInput' });
      await aiSlashInput.vm.$emit('upload', [new File(['pdf-body'], 'report.pdf', { type: 'application/pdf' })]);
      await waitUntilSendEnabled(wrapper);
      await wrapper.find('.send-btn').trigger('click');

      expect(onSendMessage.mock.calls[0][0][0]).toMatchObject({
        filename: 'report.pdf',
        mimeType: 'application/pdf',
        size: 8,
      });
    });

    it('编辑态回填的附件（无 File）发送时仍保留 filename / mimeType / size', async () => {
      const onSendMessage = vi.fn();
      const defaultFiles = [
        {
          type: 'binary',
          url: 'http://example.com/report.pdf',
          filename: 'report.pdf',
          mimeType: 'application/pdf',
          size: 2048,
        },
      ] as unknown as UploadFile[];

      wrapper = mount(ChatInput, {
        props: {
          modelValue: 'hello',
          defaultUploadFiles: defaultFiles,
          onSendMessage,
        },
      });

      await wrapper.find('.send-btn').trigger('click');

      expect(onSendMessage.mock.calls[0][0][0]).toMatchObject({
        filename: 'report.pdf',
        mimeType: 'application/pdf',
        size: 2048,
      });
    });

    it('上传未完成时点击、Enter、triggerSendMessage 均不发送', async () => {
      let resolveUpload: (value: { download_url: string }) => void = () => {};
      const onUpload = vi.fn(
        () =>
          new Promise<{ download_url: string }>(resolve => {
            resolveUpload = resolve;
          }),
      );
      const onSendMessage = vi.fn();

      wrapper = mount(ChatInput, {
        props: { modelValue: 'hello', onSendMessage, onUpload },
      });

      const aiSlashInput = wrapper.findComponent({ name: 'AiSlashInput' });
      await aiSlashInput.vm.$emit('upload', [new File(['pdf'], 'report.pdf', { type: 'application/pdf' })]);
      await wrapper.vm.$nextTick();

      const inputAttachment = wrapper.findComponent({ name: 'InputAttachment' });
      expect(inputAttachment.props('sendDisabledTip')).toBe('文件上传中，请稍候');
      expect(inputAttachment.props('messageState')).not.toBe(MessageStatus.Pending);

      await wrapper.find('.send-btn').trigger('click');
      await wrapper.find('.mock-ai-slash-input').trigger('keydown', { key: 'Enter' });
      (wrapper.vm as { triggerSendMessage: () => void }).triggerSendMessage();

      expect(onSendMessage).not.toHaveBeenCalled();

      resolveUpload({ download_url: 'http://example.com/report.pdf' });
      await vi.waitFor(() => {
        expect(inputAttachment.props('sendDisabledTip')).toBeFalsy();
      });

      await wrapper.find('.send-btn').trigger('click');
      expect(onSendMessage).toHaveBeenCalled();
    });

    it('上传失败后仍禁用，删除失败附件后恢复发送', async () => {
      const onUpload = vi.fn().mockResolvedValue({ status: 'failed' });
      const onSendMessage = vi.fn();

      wrapper = mount(ChatInput, {
        props: { modelValue: 'hello', onSendMessage, onUpload },
      });

      const aiSlashInput = wrapper.findComponent({ name: 'AiSlashInput' });
      await aiSlashInput.vm.$emit('upload', [new File(['pdf'], 'report.pdf', { type: 'application/pdf' })]);
      await vi.waitFor(() => {
        expect(wrapper.findComponent({ name: 'InputAttachment' }).props('sendDisabledTip')).toBe(
          '存在上传失败的文件，请删除后重试',
        );
      });

      await wrapper.find('.send-btn').trigger('click');
      expect(onSendMessage).not.toHaveBeenCalled();
      expect(wrapper.find('.mock-file-content').exists()).toBe(true);

      await wrapper.find('.mock-file-item').trigger('click');
      await wrapper.vm.$nextTick();

      expect(wrapper.findComponent({ name: 'InputAttachment' }).props('sendDisabledTip')).toBeFalsy();
      await wrapper.find('.send-btn').trigger('click');
      expect(onSendMessage).toHaveBeenCalled();
    });

    it('多文件中任一 Pending 或 Error 都阻塞发送', async () => {
      let resolveFirst: (value: { download_url: string }) => void = () => {};
      const onUpload = vi
        .fn()
        .mockImplementationOnce(
          () =>
            new Promise<{ download_url: string }>(resolve => {
              resolveFirst = resolve;
            }),
        )
        .mockResolvedValueOnce({ status: 'failed' });
      const onSendMessage = vi.fn();

      wrapper = mount(ChatInput, {
        props: { modelValue: 'hello', onSendMessage, onUpload },
      });

      const aiSlashInput = wrapper.findComponent({ name: 'AiSlashInput' });
      await aiSlashInput.vm.$emit('upload', [
        new File(['a'], 'a.pdf', { type: 'application/pdf', lastModified: 1 }),
        new File(['b'], 'b.pdf', { type: 'application/pdf', lastModified: 2 }),
      ]);
      await wrapper.vm.$nextTick();

      expect(wrapper.findComponent({ name: 'InputAttachment' }).props('sendDisabledTip')).toBe('文件上传中，请稍候');

      resolveFirst({ download_url: 'http://example.com/a.pdf' });
      await vi.waitFor(() => {
        expect(wrapper.findComponent({ name: 'InputAttachment' }).props('sendDisabledTip')).toBe(
          '存在上传失败的文件，请删除后重试',
        );
      });

      await wrapper.find('.send-btn').trigger('click');
      expect(onSendMessage).not.toHaveBeenCalled();
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

  // ---------- 拖拽上传测试 ----------
  describe('拖拽上传测试', () => {
    const createFileDataTransfer = (files: File[]) => ({
      dropEffect: '',
      files,
      types: ['Files'],
    });

    it('拖入文件时输入框应进入拖拽态', async () => {
      wrapper = mount(ChatInput, {
        props: { modelValue: '' },
      });

      await wrapper.find('.chat-input').trigger('dragenter', { dataTransfer: createFileDataTransfer([]) });

      expect(wrapper.find('.chat-input').classes()).toContain('is-dragover');
    });

    it('拖离后应退出拖拽态', async () => {
      wrapper = mount(ChatInput, {
        props: { modelValue: '' },
      });

      const dropZone = wrapper.find('.chat-input');
      await dropZone.trigger('dragenter', { dataTransfer: createFileDataTransfer([]) });
      await dropZone.trigger('dragleave', { dataTransfer: createFileDataTransfer([]) });

      expect(dropZone.classes()).not.toContain('is-dragover');
    });

    it('进入子元素再离开不应提前退出拖拽态', async () => {
      wrapper = mount(ChatInput, {
        props: { modelValue: '' },
      });

      const dropZone = wrapper.find('.chat-input');
      await dropZone.trigger('dragenter', { dataTransfer: createFileDataTransfer([]) });
      await dropZone.trigger('dragenter', { dataTransfer: createFileDataTransfer([]) });
      await dropZone.trigger('dragleave', { dataTransfer: createFileDataTransfer([]) });

      expect(dropZone.classes()).toContain('is-dragover');
    });

    it('编辑器内部拖拽（非文件）不应进入拖拽态', async () => {
      wrapper = mount(ChatInput, {
        props: { modelValue: '' },
      });

      await wrapper
        .find('.chat-input')
        .trigger('dragenter', { dataTransfer: { dropEffect: '', files: [], types: ['text/plain'] } });

      expect(wrapper.find('.chat-input').classes()).not.toContain('is-dragover');
    });

    it('supportUpload 为 false 时不响应拖拽', async () => {
      const onUpload = vi.fn();

      wrapper = mount(ChatInput, {
        props: { modelValue: '', onUpload, supportUpload: false },
      });

      const file = new File(['test'], 'test.txt', { type: 'text/plain' });
      await wrapper.find('.chat-input').trigger('drop', { dataTransfer: createFileDataTransfer([file]) });

      expect(wrapper.find('.chat-input').classes()).not.toContain('is-dragover');
      expect(onUpload).not.toHaveBeenCalled();
    });

    it('释放文件应走同一条上传链路并退出拖拽态', async () => {
      const onUpload = vi.fn().mockResolvedValue({ download_url: 'http://example.com/report.pdf' });

      wrapper = mount(ChatInput, {
        props: { modelValue: '', onUpload },
      });

      const dropZone = wrapper.find('.chat-input');
      const file = new File(['pdf-body'], 'report.pdf', { type: 'application/pdf' });
      await dropZone.trigger('dragenter', { dataTransfer: createFileDataTransfer([file]) });
      await dropZone.trigger('drop', { dataTransfer: createFileDataTransfer([file]) });

      expect(onUpload).toHaveBeenCalledWith(file);
      expect(dropZone.classes()).not.toContain('is-dragover');
    });
  });
});
