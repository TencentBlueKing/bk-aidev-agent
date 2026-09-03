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
import { afterEach, describe, expect, it, vi } from 'vitest';

import ResourceIcon from './resource-icon.vue';

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

vi.mock('../../icons', () => ({
  FileUploadIcon: stubIcon('FileUploadIcon', 'mock-file-upload-icon'),
  KnowledgeBaseIcon: stubIcon('KnowledgeBaseIcon', 'mock-knowledge-base-icon'),
  McpIcon: stubIcon('McpIcon', 'mock-mcp-icon'),
  ModuleIcon: stubIcon('ModuleIcon', 'mock-module-icon'),
  ToolIcon: stubIcon('ToolIcon', 'mock-tool-icon'),
}));

vi.mock('../file-icon/file-icon.vue', () => ({
  default: defineComponent({
    name: 'FileIcon',
    props: { fileName: { type: String, default: '' } },
    setup(props) {
      return () => h('span', { class: 'mock-file-icon', 'data-file-name': props.fileName });
    },
  }),
}));

describe('ResourceIcon', () => {
  let wrapper: VueWrapper;

  afterEach(() => {
    wrapper?.unmount();
  });

  describe('传入 icon 时', () => {
    it('字符串按图片地址渲染', () => {
      wrapper = mount(ResourceIcon, { props: { icon: 'https://example.com/a.png', name: 'a', type: 'tool' } });

      expect(wrapper.find('img').attributes('src')).toBe('https://example.com/a.png');
    });

    it('Vue 组件直接渲染', () => {
      const Custom = stubIcon('Custom', 'custom-icon');
      wrapper = mount(ResourceIcon, { props: { icon: Custom, name: 'a', type: 'tool' } });

      expect(wrapper.find('.custom-icon').exists()).toBe(true);
      expect(wrapper.find('img').exists()).toBe(false);
    });

    it('图片加载失败后回退到类型默认图标', async () => {
      wrapper = mount(ResourceIcon, { props: { icon: 'https://example.com/404.png', name: 'a', type: 'mcp' } });

      await wrapper.find('img').trigger('error');

      expect(wrapper.find('img').exists()).toBe(false);
      expect(wrapper.find('.mock-mcp-icon').exists()).toBe(true);
    });

    it('icon 更换后重新尝试图片渲染', async () => {
      wrapper = mount(ResourceIcon, { props: { icon: 'https://example.com/404.png', name: 'a', type: 'mcp' } });
      await wrapper.find('img').trigger('error');
      expect(wrapper.find('.mock-mcp-icon').exists()).toBe(true);

      await wrapper.setProps({ icon: 'https://example.com/ok.png' });

      expect(wrapper.find('img').attributes('src')).toBe('https://example.com/ok.png');
      expect(wrapper.find('.mock-mcp-icon').exists()).toBe(false);
    });
  });

  describe('缺省 icon 时按类型回退', () => {
    it.each([
      ['mcp', 'mock-mcp-icon'],
      ['tool', 'mock-tool-icon'],
      ['knowledgebase', 'mock-knowledge-base-icon'],
      ['doc', 'mock-knowledge-base-icon'],
      ['file', 'mock-file-upload-icon'],
    ])('%s 回退到 %s', (type, className) => {
      wrapper = mount(ResourceIcon, { props: { name: 'a', type } });

      expect(wrapper.find(`.${className}`).exists()).toBe(true);
    });

    it('artifact 按文件名推导文件类型图标', () => {
      wrapper = mount(ResourceIcon, { props: { name: '操作文档.docx', type: 'artifact' } });

      expect(wrapper.find('.mock-file-icon').attributes('data-file-name')).toBe('操作文档.docx');
    });

    it('未知类型回退到通用模块图标', () => {
      wrapper = mount(ResourceIcon, { props: { name: 'a', type: 'model' } });

      expect(wrapper.find('.mock-module-icon').exists()).toBe(true);
    });

    it('skill 没有独立默认图标，同样回退到通用模块图标', () => {
      wrapper = mount(ResourceIcon, { props: { name: 'Code Review', type: 'skill' } });

      expect(wrapper.find('.mock-module-icon').exists()).toBe(true);
    });
  });
});
