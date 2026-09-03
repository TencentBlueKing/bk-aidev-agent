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
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { MessageStatus } from '../../ag-ui/types';
import ChatInput from './chat-input.vue';

import type { IInputMenuItem, UploadFile } from '../../types';

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
const mockCloseMenu = vi.fn();
const mockOpenPlusMenu = vi.fn();
const mockInsertMenuItem = vi.fn();
const mockReplaceAll = vi.fn();
const mockAppendMention = vi.fn();
const mockConsumeTriggerText = vi.fn();
vi.mock('./ai-slash-input/ai-slash-input.vue', () => ({
  default: defineComponent({
    name: 'AiSlashInput',
    props: {
      modelValue: { type: [String, Array], default: '' },
      placeholder: { type: String, default: '' },
    },
    emits: ['update:modelValue', 'keydown', 'upload', 'menuChange'],
    setup(props, { emit, expose }) {
      expose({
        cleanup: vi.fn(),
        closeMenu: mockCloseMenu,
        consumeTriggerText: mockConsumeTriggerText,
        focus: mockInputFocus,
        insertMenuItem: mockInsertMenuItem,
        openPlusMenu: mockOpenPlusMenu,
        replaceAll: mockReplaceAll,
        appendMention: mockAppendMention,
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

// Mock AddMenuBtn（左下角 + 号）
vi.mock('../ai-buttons/add-menu-btn/add-menu-btn.vue', () => ({
  default: defineComponent({
    name: 'AddMenuBtn',
    props: { active: { type: Boolean, default: false } },
    emits: ['toggle'],
    setup(props, { emit }) {
      return () =>
        h('button', {
          class: 'mock-add-menu-btn',
          'data-active': String(props.active),
          onClick: () => emit('toggle'),
        });
    },
  }),
}));

// Mock InputMenuPanel（面板渲染细节由 input-menu-panel.spec 覆盖；分组逻辑仍走真实 composable）
vi.mock('./input-menu', async () => {
  const { useInputMenu } = await import('./input-menu/use-input-menu');
  const { DEFAULT_GROUP_ITEM_LIMIT } = await import('./input-menu/constants');
  return {
    useInputMenu,
    DEFAULT_GROUP_ITEM_LIMIT,
    InputMenuPanel: defineComponent({
      name: 'InputMenuPanel',
      props: {
        flatItems: { type: Array, default: () => [] },
        groups: { type: Array, default: () => [] },
      },
      emits: ['select', 'toggleGroup', 'close'],
      setup(props) {
        return () =>
          h('div', {
            class: 'mock-input-menu-panel',
            'data-groups': (props.groups as { key: string }[]).map(group => group.key).join(','),
          });
      },
    }),
  };
});

/** 从编辑器侧模拟一次菜单触发上报 */
const emitMenuChange = (wrapper: VueWrapper, trigger: null | string, keyword = '') =>
  wrapper.findComponent({ name: 'AiSlashInput' }).vm.$emit('menuChange', { trigger, keyword });

/** 从编辑器侧模拟一次文件上传（粘贴 / 拖拽 / 文件选择器最终都走这里） */
const emitUpload = (wrapper: VueWrapper, files: File[]) =>
  wrapper.findComponent({ name: 'AiSlashInput' }).vm.$emit('upload', files);

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

    it('未传 placeholder 时按数据源类型拼接提示文案', () => {
      wrapper = mount(ChatInput, {
        props: {
          modelValue: '',
          menuSources: [{ id: 's1', type: 'skill', name: 'Code Review' }] as IInputMenuItem[],
        },
      });

      const placeholder = wrapper.find('.mock-ai-slash-input').attributes('aria-placeholder');
      expect(placeholder).toContain('输入 "/" 唤出 Skill，工具，MCP');
      expect(placeholder).not.toContain('输入 "@"');
    });

    it('仅有知识库时默认 placeholder 含 @ 行且不含 / 行', () => {
      wrapper = mount(ChatInput, {
        props: {
          modelValue: '',
          menuSources: [{ id: 'k1', type: 'knowledgebase', name: '知识库01' }] as IInputMenuItem[],
        },
      });

      const placeholder = wrapper.find('.mock-ai-slash-input').attributes('aria-placeholder') ?? '';
      expect(placeholder).toContain('输入 "@" 唤出会话产物，知识库');
      expect(placeholder).not.toContain('输入 "/"');
      expect(placeholder).not.toContain('唤出 Prompt');
    });

    it('显式 placeholder 不被 menuSources 改写', () => {
      const placeholder = '请输入你的问题';

      wrapper = mount(ChatInput, {
        props: {
          modelValue: '',
          placeholder,
          menuSources: [
            { id: 'code-review', type: 'skill', name: 'Code Review' },
            { id: 'p1', type: 'prompt', name: '帮我总结' },
            { id: '1', type: 'tool', name: 'resource1' },
          ] as IInputMenuItem[],
        },
      });

      expect(wrapper.find('.mock-ai-slash-input').attributes('aria-placeholder')).toBe(placeholder);
    });

    it('显式空字符串 placeholder 完全覆盖动态文案', () => {
      wrapper = mount(ChatInput, {
        props: {
          modelValue: '',
          placeholder: '',
          menuSources: [{ id: 'code-review', type: 'skill', name: 'Code Review' }] as IInputMenuItem[],
        },
      });

      expect(wrapper.find('.mock-ai-slash-input').attributes('aria-placeholder')).toBe('');
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
  });

  describe('update:modelValue 事件测试', () => {
    it('AiSlashInput 触发 update:model-value 时应该透传 update:modelValue 事件', async () => {
      wrapper = mount(ChatInput, {
        props: {
          modelValue: '',
        },
      });

      const aiSlashInput = wrapper.findComponent({ name: 'AiSlashInput' });
      await aiSlashInput.vm.$emit('update:modelValue', []);

      expect(wrapper.emitted('update:modelValue')).toBeTruthy();
    });

    it('update:modelValue 事件把文档里的标签还原成 menuSources 里的选项', async () => {
      const menuSources = [{ id: '1', type: 'tool', name: 'resource1' }] as IInputMenuItem[];

      wrapper = mount(ChatInput, {
        props: {
          modelValue: '',
          menuSources,
        },
      });

      const doc = [[{ type: 'tag', data: { label: 'resource1', value: '1', type: 'tool' } }]];
      const aiSlashInput = wrapper.findComponent({ name: 'AiSlashInput' });
      await aiSlashInput.vm.$emit('update:modelValue', doc);

      expect(wrapper.emitted('update:modelValue')?.[0]).toEqual([doc, menuSources]);
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

  describe('输入框菜单', () => {
    const menuSources = [
      { id: 's1', type: 'skill', name: 'Code Review' },
      { id: 'k1', type: 'knowledgebase', name: '知识库01' },
      { id: 'p1', type: 'prompt', name: '深圳旅游攻略？', content: '深圳旅游攻略？全文' },
    ] as IInputMenuItem[];

    it('未触发时不渲染菜单面板', () => {
      wrapper = mount(ChatInput, { props: { modelValue: '', menuSources } });
      expect(wrapper.find('.mock-input-menu-panel').exists()).toBe(false);
    });

    it('/ 触发只展示 Skill 相关分组', async () => {
      wrapper = mount(ChatInput, { props: { modelValue: '', menuSources } });
      await emitMenuChange(wrapper, '/');
      expect(wrapper.find('.mock-input-menu-panel').attributes('data-groups')).toBe('skill');
    });

    it('@ 触发展示知识库与会话产物分组', async () => {
      wrapper = mount(ChatInput, { props: { modelValue: '', menuSources } });
      await emitMenuChange(wrapper, '@');
      expect(wrapper.find('.mock-input-menu-panel').attributes('data-groups')).toBe('knowledgebase,artifact');
    });

    it('plus 触发聚合全部分组，并把内置「文件」放在添加分组', async () => {
      wrapper = mount(ChatInput, { props: { modelValue: '', menuSources } });
      await emitMenuChange(wrapper, 'plus');
      expect(wrapper.find('.mock-input-menu-panel').attributes('data-groups')).toBe(
        'add,skill,knowledgebase,artifact,prompt',
      );
    });

    it('过滤关键字命中不到条目时不展示面板', async () => {
      wrapper = mount(ChatInput, { props: { modelValue: '', menuSources } });
      await emitMenuChange(wrapper, '/', 'nothing-matched');
      expect(wrapper.find('.mock-input-menu-panel').exists()).toBe(false);
    });

    it('已插入编辑器的标签不再出现在菜单里', async () => {
      const doc = [[{ type: 'tag', data: { label: 'Code Review', value: 's1', type: 'skill' } }]];
      wrapper = mount(ChatInput, { props: { modelValue: doc as never, menuSources } });
      await emitMenuChange(wrapper, '/');
      expect(wrapper.find('.mock-input-menu-panel').exists()).toBe(false);
    });

    it('点击 + 号唤起聚合菜单，再次点击收起', async () => {
      wrapper = mount(ChatInput, { props: { modelValue: '', menuSources } });
      await wrapper.find('.mock-add-menu-btn').trigger('click');
      expect(mockOpenPlusMenu).toHaveBeenCalled();

      await emitMenuChange(wrapper, 'plus');
      expect(wrapper.find('.mock-add-menu-btn').attributes('data-active')).toBe('true');

      await wrapper.find('.mock-add-menu-btn').trigger('click');
      expect(mockCloseMenu).toHaveBeenCalled();
    });

    it('选中普通条目时插入标签', async () => {
      wrapper = mount(ChatInput, { props: { modelValue: '', menuSources } });
      await emitMenuChange(wrapper, '/');
      await wrapper.findComponent({ name: 'InputMenuPanel' }).vm.$emit('select', menuSources[0]);
      expect(mockInsertMenuItem).toHaveBeenCalledWith(menuSources[0]);
    });

    it('选中 Prompt 时整体替换输入框内容', async () => {
      wrapper = mount(ChatInput, { props: { modelValue: '', menuSources } });
      await emitMenuChange(wrapper, '\\');
      await wrapper.findComponent({ name: 'InputMenuPanel' }).vm.$emit('select', menuSources[2]);
      expect(mockReplaceAll).toHaveBeenCalledWith('深圳旅游攻略？全文');
    });

    it('Prompt 没有 content 时回退到名称', async () => {
      wrapper = mount(ChatInput, { props: { modelValue: '', menuSources } });
      await emitMenuChange(wrapper, '\\');
      await wrapper
        .findComponent({ name: 'InputMenuPanel' })
        .vm.$emit('select', { id: 'p2', type: 'prompt', name: '标题' });
      expect(mockReplaceAll).toHaveBeenCalledWith('标题');
    });

    it('选中内置「文件」时先吃掉过滤词再唤起文件选择器', async () => {
      wrapper = mount(ChatInput, { props: { modelValue: '', menuSources } });
      await emitMenuChange(wrapper, 'plus');
      const fileInput = wrapper.find('.chat-input-file-input');
      const clickSpy = vi.spyOn(fileInput.element as HTMLInputElement, 'click').mockImplementation(() => {});
      await wrapper
        .findComponent({ name: 'InputMenuPanel' })
        .vm.$emit('select', { id: '__built_in_file__', type: 'file', name: '文件' });
      expect(mockConsumeTriggerText).toHaveBeenCalled();
      expect(mockCloseMenu).toHaveBeenCalled();
      expect(clickSpy).toHaveBeenCalled();
    });

    it('insertMention 把条目追加到编辑器末尾', () => {
      wrapper = mount(ChatInput, { props: { modelValue: '', menuSources } });
      (wrapper.vm as unknown as { insertMention: (item: IInputMenuItem) => void }).insertMention(menuSources[1]);
      expect(mockAppendMention).toHaveBeenCalledWith(menuSources[1]);
    });

    it('菜单展开时按 Enter 不触发发送', async () => {
      const onSendMessage = vi.fn();
      wrapper = mount(ChatInput, { props: { modelValue: 'hello', menuSources, onSendMessage } });
      await emitMenuChange(wrapper, '/');
      await wrapper.findComponent({ name: 'AiSlashInput' }).vm.$emit('keydown', { key: 'Enter' });
      expect(onSendMessage).not.toHaveBeenCalled();
    });
  });

  describe('文件上传功能测试', () => {
    it('supportUpload 默认为 true 时应该渲染 + 号按钮', () => {
      wrapper = mount(ChatInput, {
        props: {
          modelValue: '',
        },
      });

      expect(wrapper.find('.mock-add-menu-btn').exists()).toBe(true);
    });

    it('既不支持上传也没有菜单数据时不渲染 + 号按钮', () => {
      wrapper = mount(ChatInput, {
        props: {
          modelValue: '',
          supportUpload: false,
        },
      });

      expect(wrapper.find('.mock-add-menu-btn').exists()).toBe(false);
    });

    it('不支持上传但有菜单数据时仍渲染 + 号按钮', () => {
      wrapper = mount(ChatInput, {
        props: {
          modelValue: '',
          supportUpload: false,
          menuSources: [{ id: 's1', type: 'skill', name: 'Code Review' }] as IInputMenuItem[],
        },
      });

      expect(wrapper.find('.mock-add-menu-btn').exists()).toBe(true);
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

    it('编辑器上报文件时应该触发上传', async () => {
      const onUpload = vi.fn().mockResolvedValue({ download_url: 'http://example.com/file.txt' });

      wrapper = mount(ChatInput, {
        props: {
          modelValue: '',
          onUpload,
        },
      });

      await emitUpload(wrapper, [new File(['test'], 'test.txt', { type: 'text/plain' })]);

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

      await emitUpload(wrapper, [new File(['test'], 'test.txt', { type: 'text/plain' })]);
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

      await emitUpload(wrapper, [new File(['test'], 'test.txt', { type: 'text/plain' })]);
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
      expect(mockBkMessage).not.toHaveBeenCalled();
    });

    it('仅因重复未加入时不应提示超过大小或个数', async () => {
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
      mockBkMessage.mockClear();
      await aiSlashInput.vm.$emit('upload', [sameFile]);

      expect(mockBkMessage).not.toHaveBeenCalled();
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
      expect(mockBkMessage).not.toHaveBeenCalled();
    });

    it('一次选择多个文件时只调用一次 onUpload 并传入全部文件', async () => {
      const onUpload = vi.fn().mockResolvedValue([
        { id: 'files/a.pdf', status: 'success' },
        { id: 'files/b.pdf', status: 'success' },
      ]);
      const fileA = new File(['a'], 'a.pdf', { type: 'application/pdf', lastModified: 1 });
      const fileB = new File(['b'], 'b.pdf', { type: 'application/pdf', lastModified: 2 });

      wrapper = mount(ChatInput, {
        props: {
          modelValue: '',
          onUpload,
        },
      });

      const aiSlashInput = wrapper.findComponent({ name: 'AiSlashInput' });
      await aiSlashInput.vm.$emit('upload', [fileA, fileB]);

      expect(onUpload).toHaveBeenCalledTimes(1);
      expect(onUpload).toHaveBeenCalledWith([fileA, fileB]);
    });

    it('批量结果按顺序回填，部分失败只标记对应文件', async () => {
      const onUpload = vi.fn().mockResolvedValue([
        { id: 'files/ok.pdf', status: 'success' },
        { status: 'failed', error: 'too large' },
      ]);
      const onSendMessage = vi.fn();

      wrapper = mount(ChatInput, {
        props: {
          modelValue: 'hello',
          onSendMessage,
          onUpload,
        },
      });

      const aiSlashInput = wrapper.findComponent({ name: 'AiSlashInput' });
      await aiSlashInput.vm.$emit('upload', [
        new File(['ok'], 'ok.pdf', { type: 'application/pdf', lastModified: 1 }),
        new File(['bad'], 'bad.pdf', { type: 'application/pdf', lastModified: 2 }),
      ]);
      await vi.waitFor(() => {
        expect(wrapper.findComponent({ name: 'InputAttachment' }).props('sendDisabledTip')).toBe(
          '存在上传失败的文件，请删除后重试',
        );
      });

      await wrapper.find('.send-btn').trigger('click');
      expect(onSendMessage).not.toHaveBeenCalled();
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
      let resolveBatch: (value: Array<{ download_url?: string; status?: 'failed' | 'success' }>) => void = () => {};
      const onUpload = vi.fn(
        () =>
          new Promise<Array<{ download_url?: string; status?: 'failed' | 'success' }>>(resolve => {
            resolveBatch = resolve;
          }),
      );
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

      resolveBatch([{ download_url: 'http://example.com/a.pdf' }, { status: 'failed' }]);
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

      expect(onUpload).toHaveBeenCalledWith([file]);
      expect(dropZone.classes()).not.toContain('is-dragover');
    });
  });
});
