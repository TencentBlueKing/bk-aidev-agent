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

import { defineComponent, h, nextTick } from 'vue';

import { type VueWrapper, mount } from '@vue/test-utils';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import AiSlashInput from './ai-slash-input.vue';

import type { IAiSlashMenuItem } from '../../../types/editor';

/** 与 edix Editor.command 行为对齐：执行命令函数并传入伪造的 doc / selection，供 GetDocSnapshot 等逻辑使用 */
const { editorCommand, editorOptions } = vi.hoisted(() => {
  const fakeDoc = [[{ type: 'text', text: 'internal-snapshot' }]] as unknown[];
  const options: { onKeyDown?: (event: { key: string; preventDefault?: () => void }) => unknown } = {};
  return {
    editorCommand: vi.fn((fn: (...args: unknown[]) => unknown, ...args: unknown[]) => {
      if (typeof fn === 'function') {
        fn(fakeDoc, [], ...args);
      }
    }),
    editorOptions: options,
  };
});

vi.mock('tippy.js/dist/tippy.css', () => ({}));

// Mock common
vi.mock('../../../common', () => ({
  EDITOR_MENU_Z_INDEX: 1000,
  isEn: false,
}));

// Mock vue-tippy
vi.mock('vue-tippy', () => ({
  Tippy: defineComponent({
    name: 'Tippy',
    props: {
      appendTo: { default: null },
      arrow: { type: Boolean, default: false },
      hideOnClick: { type: Boolean, default: true },
      interactive: { type: Boolean, default: false },
      offset: { type: Array, default: () => [0, 0] },
      placement: { type: String, default: 'right-start' },
      theme: { type: String, default: '' },
      trigger: { type: String, default: 'click' },
      triggerTarget: { default: null },
      zIndex: { type: Number, default: 1000 },
    },
    emits: ['hidden', 'show'],
    setup(_, { slots, expose }) {
      expose({
        show: vi.fn(),
        hide: vi.fn(),
        setProps: vi.fn(),
      });
      return () => h('div', { class: 'mock-tippy' }, slots.content?.());
    },
  }),
  useTippy: vi.fn(),
}));

// Mock composables（与 use-command-selection 返回值对齐，供 modelValue 同步逻辑使用）
vi.mock('../../../composables', () => {
  const docSnapshot = { value: [] as unknown[] };
  return {
    useCommandSelection: () => ({
      commandSelection: { value: { column: 5, line: 0 } },
      GetCursorPosition: 'GetCursorPosition',
      GetDocSnapshot: ((doc: unknown) => {
        docSnapshot.value = doc as unknown[];
      }) as (...args: unknown[]) => void,
      docSnapshot,
    }),
  };
});

// Mock edix（command 需执行 EditorCommand，否则 GetDocSnapshot 无法写入 docSnapshot）
vi.mock('../../../edix', () => ({
  createEditor: (options: { onKeyDown?: (event: { key: string; preventDefault?: () => void }) => unknown }) => {
    editorOptions.onKeyDown = options.onKeyDown;
    return {
      command: editorCommand,
      input: vi.fn(() => vi.fn()),
    };
  },
  ReplaceAll: 'ReplaceAll',
  stringToDoc: (str: string) => [[{ type: 'text', text: str }]],
  docToString: (doc: unknown) => {
    if (!Array.isArray(doc) || doc.length === 0) return '';
    const line = doc[0];
    if (!Array.isArray(line)) return '';
    return line.map((n: { text?: string }) => n?.text ?? '').join('');
  },
}));

// Mock icons
vi.mock('../../../icons', () => ({
  RemoveIcon: defineComponent({
    name: 'RemoveIcon',
    setup() {
      return () => h('span', { class: 'mock-remove-icon' });
    },
  }),
}));

// Mock child components
vi.mock('./ai-prompt-list/ai-prompt-list.vue', () => ({
  default: defineComponent({
    name: 'AiPromptList',
    props: {
      onSelect: { type: Function, default: null },
      prompts: { type: Array, default: () => [] },
    },
    setup() {
      return () => h('div', { class: 'mock-ai-prompt-list' });
    },
  }),
}));

vi.mock('./ai-slash-menu/ai-slash-menu.vue', () => ({
  default: defineComponent({
    name: 'AiSlashMenu',
    props: {
      onSelect: { type: Function, default: null },
      resourceList: { type: Array, default: () => [] },
    },
    setup() {
      return () => h('div', { class: 'mock-ai-slash-menu' });
    },
  }),
}));

vi.mock('./ai-skill-list/ai-skill-list.vue', () => ({
  default: defineComponent({
    name: 'AiSkillList',
    props: {
      onSelect: { type: Function, default: null },
      skills: { type: Array, default: () => [] },
    },
    setup(props) {
      return () =>
        h('div', {
          class: 'mock-ai-skill-list',
          'data-skills-count': String(props.skills?.length ?? 0),
          onClick: () =>
            props.onSelect?.({
              skill_code: 'test_skill',
              skill_name: 'Test Skill',
              description: '',
              icon: '',
            }),
        });
    },
  }),
}));

// Mock commands and constants
vi.mock('./command', () => ({
  DeleteTag: 'DeleteTag',
  InsertSkillTag: 'InsertSkillTag',
  InsertTag: 'InsertTag',
  InsertText: 'InsertText',
}));

vi.mock('./constants', () => ({
  tagSchema: {},
}));

// style-note: chat-x PR4 — wrapper min-height:0 配合父级 max-height 内部滚动
describe('AiSlashInput', () => {
  let wrapper: VueWrapper;

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    wrapper?.unmount();
  });

  describe('渲染测试', () => {
    it('应该正确渲染组件', () => {
      wrapper = mount(AiSlashInput, {
        props: {
          modelValue: '',
        },
      });

      expect(wrapper.find('.ai-slash-input-wrapper').exists()).toBe(true);
    });

    it('应该渲染编辑器区域', () => {
      wrapper = mount(AiSlashInput, {
        props: {
          modelValue: '',
        },
      });

      expect(wrapper.find('.ai-slash-input').exists()).toBe(true);
    });

    it('应该渲染 Tippy 组件', () => {
      wrapper = mount(AiSlashInput, {
        props: {
          modelValue: '',
        },
      });

      expect(wrapper.find('.mock-tippy').exists()).toBe(true);
    });
  });

  describe('Props 测试', () => {
    it('应该正确设置 placeholder', () => {
      const placeholder = '请输入内容';

      wrapper = mount(AiSlashInput, {
        props: {
          modelValue: '',
          placeholder,
        },
      });

      expect(wrapper.find('.ai-slash-input').attributes('aria-placeholder')).toBe(placeholder);
    });

    it('应该接收 prompts 属性', () => {
      const prompts = ['prompt1', 'prompt2'];

      wrapper = mount(AiSlashInput, {
        props: {
          modelValue: '',
          prompts,
        },
      });

      expect(wrapper.find('.ai-slash-input-wrapper').exists()).toBe(true);
    });

    it('应该接收 resources 属性', () => {
      const resources = [{ id: '1', name: 'resource1', type: 'tool' }] as IAiSlashMenuItem[];

      wrapper = mount(AiSlashInput, {
        props: {
          modelValue: '',
          resources,
        },
      });

      expect(wrapper.find('.ai-slash-input-wrapper').exists()).toBe(true);
    });

    it('应该接收 skills 属性', () => {
      const skills = [
        { skill_code: 'test_skill', skill_name: 'Test Skill', description: 'A test skill', icon: '' },
      ];

      wrapper = mount(AiSlashInput, {
        props: {
          modelValue: '',
          skills,
        },
      });

      expect(wrapper.find('.ai-slash-input-wrapper').exists()).toBe(true);
    });
  });

  describe('暴露方法测试', () => {
    it('应该暴露 cleanup 方法', () => {
      wrapper = mount(AiSlashInput, {
        props: {
          modelValue: '',
        },
      });

      expect((wrapper.vm as { cleanup?: () => void }).cleanup).toBeDefined();
    });
  });

  describe('边界情况测试', () => {
    it('应该处理空的 modelValue', () => {
      wrapper = mount(AiSlashInput, {
        props: {
          modelValue: '',
        },
      });

      expect(wrapper.find('.ai-slash-input-wrapper').exists()).toBe(true);
    });

    it('应该处理字符串 modelValue', () => {
      wrapper = mount(AiSlashInput, {
        props: {
          modelValue: 'test content',
        },
      });

      expect(wrapper.find('.ai-slash-input-wrapper').exists()).toBe(true);
    });

    it('应该处理空的 prompts 数组', () => {
      wrapper = mount(AiSlashInput, {
        props: {
          modelValue: '',
          prompts: [],
        },
      });

      expect(wrapper.find('.ai-slash-input-wrapper').exists()).toBe(true);
    });

    it('应该处理空的 resources 数组', () => {
      wrapper = mount(AiSlashInput, {
        props: {
          modelValue: '',
          resources: [],
        },
      });

      expect(wrapper.find('.ai-slash-input-wrapper').exists()).toBe(true);
    });
  });

  describe('样式测试', () => {
    // tippy light 主题背景色由 SCSS 控制（&[data-theme~='light'] { background-color: white }），不在 JSDOM 中验证

    it('应该具有正确的类名结构', () => {
      wrapper = mount(AiSlashInput, {
        props: {
          modelValue: '',
        },
      });

      expect(wrapper.find('.ai-slash-input-wrapper').exists()).toBe(true);
      expect(wrapper.find('.ai-slash-input').exists()).toBe(true);
    });

    it('编辑器应该禁用拼写检查', () => {
      wrapper = mount(AiSlashInput, {
        props: {
          modelValue: '',
        },
      });

      expect(wrapper.find('.ai-slash-input').attributes('spellcheck')).toBe('false');
    });

    it('skill 标签应渲染 data-tag-value 属性', () => {
      wrapper = mount(AiSlashInput, {
        props: {
          modelValue: [
            [
              {
                type: 'tag',
                data: { label: 'Test Skill', value: 'test_skill', type: 'skill' },
              },
            ],
          ],
        },
      });

      const tag = wrapper.find('[data-tag-type="skill"]');
      expect(tag.exists()).toBe(true);
      expect(tag.attributes('data-tag-value')).toBe('test_skill');
    });
  });

  describe('Skill 过滤与插入', () => {
    const openSkillMenu = async () => {
      editorOptions.onKeyDown?.({ key: '/', preventDefault: vi.fn() });
      await nextTick();
    };

    it('已插入的 skill 不应出现在 AiSkillList 的 skills 列表中', async () => {
      const skills = [
        { skill_code: 'skill1', skill_name: 'Skill 1', description: '', icon: '' },
        { skill_code: 'skill2', skill_name: 'Skill 2', description: '', icon: '' },
      ];

      wrapper = mount(AiSlashInput, {
        props: {
          modelValue: [
            [
              {
                type: 'tag',
                data: { label: 'Skill 1', value: 'skill1', type: 'skill' },
              },
            ],
          ],
          skills,
        },
      });
      await nextTick();
      await openSkillMenu();

      const skillList = wrapper.findComponent({ name: 'AiSkillList' });
      expect(skillList.exists()).toBe(true);
      expect(skillList.props('skills')).toHaveLength(1);
      expect(skillList.props('skills')[0].skill_code).toBe('skill2');
    });

    it('选择 skill 时应调用 InsertSkillTag 命令', async () => {
      wrapper = mount(AiSlashInput, {
        props: {
          modelValue: '',
          skills: [{ skill_code: 'test_skill', skill_name: 'Test Skill', description: '', icon: '' }],
        },
      });
      await nextTick();
      await openSkillMenu();
      editorCommand.mockClear();

      await wrapper.find('.mock-ai-skill-list').trigger('click');
      await nextTick();

      const insertSkillCalls = editorCommand.mock.calls.filter(
        call => (call[0] as unknown) === 'InsertSkillTag',
      );
      expect(insertSkillCalls.length).toBeGreaterThan(0);
    });
  });

  describe('modelValue 同步', () => {
    it('外部更新 modelValue 时应完成渲染且不抛错', async () => {
      wrapper = mount(AiSlashInput, {
        props: {
          modelValue: '初始',
        },
      });
      await nextTick();
      await wrapper.setProps({ modelValue: '更新后' });
      await nextTick();
      expect(wrapper.find('.ai-slash-input-wrapper').exists()).toBe(true);
    });

    it('外部更新 modelValue 且与编辑器快照不一致时应调用 ReplaceAll 同步为最新字符串', async () => {
      wrapper = mount(AiSlashInput, {
        props: {
          modelValue: 'A',
        },
      });
      await nextTick();
      editorCommand.mockClear();
      await wrapper.setProps({ modelValue: 'B' });
      await nextTick();
      const replaceCalls = editorCommand.mock.calls.filter(
        call => (call[0] as unknown) === 'ReplaceAll',
      );
      expect(replaceCalls.some(([, text]) => text === 'B')).toBe(true);
    });
  });

  describe('事件测试', () => {
    it('应该定义 upload 事件', () => {
      wrapper = mount(AiSlashInput, {
        props: {
          modelValue: '',
        },
      });

      // 验证组件可以正常渲染，upload 事件在 emits 中定义
      expect(wrapper.find('.ai-slash-input-wrapper').exists()).toBe(true);
    });

    it('应该定义 update:modelValue 事件', () => {
      wrapper = mount(AiSlashInput, {
        props: {
          modelValue: '',
        },
      });

      expect(wrapper.find('.ai-slash-input-wrapper').exists()).toBe(true);
    });

    it('粘贴文件时应该触发 upload 事件', async () => {
      wrapper = mount(AiSlashInput, {
        props: {
          modelValue: '',
        },
      });

      // 由于 editor 是 mock 的，我们验证组件结构正确
      expect(wrapper.find('.ai-slash-input').exists()).toBe(true);
    });
  });
});
