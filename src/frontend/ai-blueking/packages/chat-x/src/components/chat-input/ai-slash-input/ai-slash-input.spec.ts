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

import type { IInputMenuItem, TagSchema } from '../../../types';

/** 与 edix Editor.command 行为对齐：执行命令函数并传入伪造的 doc / selection，供 GetDocSnapshot 等逻辑使用 */
const { editorCommand, editorOptions } = vi.hoisted(() => {
  const fakeDoc = [[{ type: 'text', text: 'internal-snapshot' }]] as unknown[];
  const options: { onKeyDown?: (event: { key: string; preventDefault?: () => void; shiftKey?: boolean }) => unknown } =
    {};
  return {
    editorCommand: vi.fn((fn: unknown, ...args: unknown[]) => {
      if (typeof fn === 'function') {
        (fn as (...params: unknown[]) => unknown)(fakeDoc, [], ...args);
      }
    }),
    editorOptions: options,
  };
});

vi.mock('tippy.js/dist/tippy.css', () => ({}));

// MentionTag 通过 v-tippy 挂描述气泡，这里只需保证指令可用
vi.mock('vue-tippy', () => ({ directive: {} }));

vi.mock('../../../common', () => ({
  EDITOR_MENU_Z_INDEX: 10001,
  isEn: false,
}));

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

vi.mock('../../../edix', () => ({
  createEditor: (options: { onKeyDown?: (event: { key: string }) => unknown }) => {
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

const { stubIcon } = vi.hoisted(() => {
  const stubIcon = (name: string, className: string) =>
    defineComponent({
      name,
      setup() {
        return () => h('span', { class: className });
      },
    });
  return { stubIcon };
});

vi.mock('../../../icons', () => ({
  FileUploadIcon: stubIcon('FileUploadIcon', 'mock-file-upload-icon'),
  KnowledgeBaseIcon: stubIcon('KnowledgeBaseIcon', 'mock-knowledge-base-icon'),
  McpIcon: stubIcon('McpIcon', 'mock-mcp-icon'),
  ModuleIcon: stubIcon('ModuleIcon', 'mock-module-icon'),
  ToolIcon: stubIcon('ToolIcon', 'mock-tool-icon'),
}));

vi.mock('../../file-icon/file-icon.vue', () => ({
  default: defineComponent({
    name: 'FileIcon',
    props: { fileName: { type: String, default: '' } },
    setup() {
      return () => h('span', { class: 'mock-file-icon' });
    },
  }),
}));

vi.mock('./command', () => ({
  DeleteTag: 'DeleteTag',
  InsertMenuTag: 'InsertMenuTag',
  InsertText: 'InsertText',
}));

vi.mock('./constants', () => ({
  tagSchema: {},
}));

const buildDoc = (icon = ''): TagSchema =>
  [
    [
      { type: 'text', text: 'hi ' },
      { type: 'tag', data: { label: '知识库01', value: 'k1', type: 'knowledgebase', icon } },
    ],
  ] as unknown as TagSchema;

describe('AiSlashInput', () => {
  let wrapper: VueWrapper;

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    wrapper?.unmount();
  });

  describe('渲染', () => {
    it('渲染编辑器容器与 placeholder', () => {
      wrapper = mount(AiSlashInput, { props: { modelValue: '', placeholder: '请输入' } });
      expect(wrapper.find('.ai-slash-input-wrapper').exists()).toBe(true);
      expect(wrapper.find('.ai-slash-input').attributes('aria-placeholder')).toBe('请输入');
    });

    it('标签按设计稿渲染为图标 + 名称，且不再有删除按钮', () => {
      wrapper = mount(AiSlashInput, { props: { modelValue: buildDoc() } });
      const tag = wrapper.find('.ai-mention-tag');
      expect(tag.exists()).toBe(true);
      expect(tag.attributes('data-tag-type')).toBe('knowledgebase');
      expect(tag.attributes('data-tag-value')).toBe('k1');
      expect(tag.attributes('data-tag-label')).toBe('知识库01');
      expect(tag.find('.ai-mention-tag-name').text()).toBe('知识库01');
      expect(wrapper.find('.mention-tag-remove-icon').exists()).toBe(false);
    });

    it('标签节点自带 icon 时直接使用，不依赖外部数据源', () => {
      wrapper = mount(AiSlashInput, { props: { modelValue: buildDoc('https://example.com/kb.png') } });
      expect(wrapper.find('.ai-resource-icon img').attributes('src')).toBe('https://example.com/kb.png');
    });

    it('标签节点缺失 icon 时按类型回退到知识库图标', () => {
      wrapper = mount(AiSlashInput, { props: { modelValue: buildDoc() } });
      expect(wrapper.find('.mock-knowledge-base-icon').exists()).toBe(true);
    });
  });

  describe('菜单触发', () => {
    it.each(['@', '/', '\\'])('输入 %s 上报对应触发方式', async key => {
      wrapper = mount(AiSlashInput, { props: { modelValue: '' } });
      editorOptions.onKeyDown?.({ key });
      await nextTick();
      expect(wrapper.emitted('menuChange')?.[0]).toEqual([{ trigger: key, keyword: '' }]);
    });

    it('openPlusMenu 上报 plus 触发', async () => {
      wrapper = mount(AiSlashInput, { props: { modelValue: '' }, attachTo: document.body });
      (wrapper.vm as unknown as { openPlusMenu: () => void }).openPlusMenu();
      await nextTick();
      expect(wrapper.emitted('menuChange')?.[0]).toEqual([{ trigger: 'plus', keyword: '' }]);
    });

    it('closeMenu 上报触发方式为空', async () => {
      wrapper = mount(AiSlashInput, { props: { modelValue: '' } });
      const vm = wrapper.vm as unknown as { closeMenu: () => void };
      editorOptions.onKeyDown?.({ key: '@' });
      await nextTick();
      vm.closeMenu();
      await nextTick();
      const emitted = wrapper.emitted('menuChange') ?? [];
      expect(emitted[emitted.length - 1]).toEqual([{ trigger: null, keyword: '' }]);
    });
  });

  describe('选中条目', () => {
    it('insertMenuItem 先删除触发文本再插入标签与空格', () => {
      wrapper = mount(AiSlashInput, { props: { modelValue: '' } });
      const vm = wrapper.vm as unknown as { insertMenuItem: (item: IInputMenuItem) => void };
      editorOptions.onKeyDown?.({ key: '@' });
      editorCommand.mockClear();
      vm.insertMenuItem({ id: 'k1', type: 'knowledgebase', name: '知识库01' });

      const commands = editorCommand.mock.calls.map(call => call[0]);
      expect(commands).toEqual(['GetCursorPosition', 'DeleteTag', 'InsertMenuTag', 'InsertText']);
      // 光标在第 5 列，触发符「@」占 1 列，过滤词为空 → 从第 4 列开始替换
      expect(editorCommand.mock.calls[1].slice(1)).toEqual([
        [0, 4],
        [0, 5],
      ]);
      expect(editorCommand.mock.calls[3].slice(1)).toEqual([[0, 5], ' ']);
    });

    it('replaceAll 整体替换输入框内容', () => {
      wrapper = mount(AiSlashInput, { props: { modelValue: '' } });
      const vm = wrapper.vm as unknown as { replaceAll: (value: string) => void };
      editorCommand.mockClear();
      vm.replaceAll('深圳旅游攻略？');
      expect(editorCommand).toHaveBeenCalledWith('ReplaceAll', '深圳旅游攻略？');
    });

    it('appendMention 按文档末尾插入标签，不依赖当前光标', () => {
      wrapper = mount(AiSlashInput, {
        props: { modelValue: [[{ type: 'text', text: 'hi' }]] as unknown as TagSchema },
      });
      const vm = wrapper.vm as unknown as { appendMention: (item: IInputMenuItem) => void };
      editorCommand.mockClear();
      vm.appendMention({ id: 'k1', type: 'knowledgebase', name: '知识库01' });

      const commands = editorCommand.mock.calls.map(call => call[0]);
      expect(commands).toEqual(['InsertMenuTag', 'InsertText']);
      expect(editorCommand.mock.calls[0].slice(1)).toEqual([
        [0, 2],
        { id: 'k1', type: 'knowledgebase', name: '知识库01' },
      ]);
      expect(editorCommand.mock.calls[1].slice(1)).toEqual([[0, 3], ' ']);
    });
  });

  describe('键盘与粘贴', () => {
    it('Enter 阻止默认换行，Shift + Enter 放行', () => {
      wrapper = mount(AiSlashInput, { props: { modelValue: '' } });
      const preventDefault = vi.fn();
      expect(editorOptions.onKeyDown?.({ key: 'Enter', preventDefault })).toBe(false);
      expect(preventDefault).toHaveBeenCalled();
      expect(editorOptions.onKeyDown?.({ key: 'Enter', shiftKey: true, preventDefault })).toBeUndefined();
    });

    it('粘贴文件时抛出 upload 事件', async () => {
      wrapper = mount(AiSlashInput, { props: { modelValue: '' }, attachTo: document.body });
      const file = new File(['x'], 'a.txt', { type: 'text/plain' });
      const event = new Event('paste') as ClipboardEvent;
      Object.defineProperty(event, 'clipboardData', {
        value: { items: [{ kind: 'file', getAsFile: () => file }] },
      });
      wrapper.find('.ai-slash-input').element.dispatchEvent(event);
      await nextTick();
      expect(wrapper.emitted('upload')?.[0]).toEqual([[file]]);
    });
  });
});
