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

import { ARTIFACT_PREVIEW_TOKEN } from '../../composables/use-artifact-preview';
import MentionTag from './mention-tag.vue';

vi.mock('tippy.js/dist/tippy.css', () => ({}));

/** 记录指令收到的 tippy 配置，用于断言气泡内容而不依赖真实浮层渲染 */
const tippyBindings: Record<string, unknown>[] = [];
vi.mock('vue-tippy', () => ({
  directive: {
    mounted: (_el: HTMLElement, binding: { value: Record<string, unknown> }) => {
      tippyBindings.push(binding.value);
    },
    updated: vi.fn(),
    unmounted: vi.fn(),
  },
}));

vi.mock('../../lang/lang', () => ({ t: (key: string) => key }));

vi.mock('../resource-icon', () => ({
  ResourceIcon: defineComponent({
    name: 'ResourceIcon',
    props: {
      icon: { type: [String, Object], default: '' },
      name: { type: String, default: '' },
      type: { type: String, default: '' },
    },
    setup() {
      return () => h('span', { class: 'mock-resource-icon' });
    },
  }),
}));

const baseProps = { label: 'knowlege-base', type: 'tool', value: 'tool_1' };

describe('MentionTag', () => {
  let wrapper: VueWrapper;

  afterEach(() => {
    wrapper?.unmount();
    tippyBindings.length = 0;
  });

  it('渲染图标与名称，并带上编辑器识别所需的 data-tag-*', () => {
    wrapper = mount(MentionTag, { props: baseProps });

    const tag = wrapper.find('.ai-mention-tag');
    expect(wrapper.find('.mock-resource-icon').exists()).toBe(true);
    expect(tag.find('.ai-mention-tag-name').text()).toBe('knowlege-base');
    expect(tag.attributes('data-tag-type')).toBe('tool');
    expect(tag.attributes('data-tag-value')).toBe('tool_1');
    expect(tag.attributes('data-tag-label')).toBe('knowlege-base');
    expect(tag.attributes('contenteditable')).toBe('false');
  });

  it('传入 icon 时写入 data-tag-icon，文档才能脱离数据源还原图标', () => {
    wrapper = mount(MentionTag, { props: { ...baseProps, icon: 'https://example.com/tool.png' } });

    expect(wrapper.find('.ai-mention-tag').attributes('data-tag-icon')).toBe('https://example.com/tool.png');
  });

  it('有描述时把描述写入 data-tag-description，文档才能自洽还原', () => {
    wrapper = mount(MentionTag, { props: { ...baseProps, description: '描述介绍' } });

    expect(wrapper.find('.ai-mention-tag').attributes('data-tag-description')).toBe('描述介绍');
  });

  it('有描述时气泡标题为「类型：名称」', () => {
    wrapper = mount(MentionTag, { props: { ...baseProps, description: '描述介绍' } });

    const options = tippyBindings.at(-1) as { content?: { props?: Record<string, unknown> } };
    expect(options?.content?.props).toMatchObject({ title: '工具：knowlege-base', description: '描述介绍' });
  });

  it('有描述时带 is-interactive，用于 hover 下划线提示', () => {
    wrapper = mount(MentionTag, { props: { ...baseProps, description: '描述介绍' } });

    expect(wrapper.find('.ai-mention-tag').classes()).toContain('is-interactive');
  });

  it('没有描述时不弹气泡，也不加可交互提示', () => {
    wrapper = mount(MentionTag, { props: baseProps });

    expect(wrapper.find('.ai-mention-tag').classes()).not.toContain('is-interactive');
    expect(wrapper.find('.ai-mention-tag').attributes('data-tag-description')).toBeUndefined();
    const options = tippyBindings.at(-1) as { onShow?: () => boolean };
    expect(options?.onShow?.()).toBe(false);
  });

  it('未知类型时标题回退为纯名称', () => {
    wrapper = mount(MentionTag, { props: { ...baseProps, type: 'unknown', description: '描述介绍' } });

    const options = tippyBindings.at(-1) as { content?: { props?: Record<string, unknown> } };
    expect(options?.content?.props).toMatchObject({ title: 'knowlege-base' });
  });

  describe('会话产物点击预览', () => {
    const artifactProps = { label: '操作文档.docx', type: 'artifact', value: 'output-1' };
    const mountWithPreview = (props: Record<string, unknown>, openPreview = vi.fn()) => {
      wrapper = mount(MentionTag, {
        global: { provide: { [ARTIFACT_PREVIEW_TOKEN]: { openPreview } } },
        props: props as never,
      });
      return openPreview;
    };

    it('点击 artifact 标签按 outputId 打开预览', async () => {
      const openPreview = mountWithPreview(artifactProps);

      await wrapper.find('.ai-mention-tag').trigger('click');

      expect(openPreview).toHaveBeenCalledWith({ file: { outputId: 'output-1' } });
    });

    it('artifact 标签即使没有描述也标记为可交互', () => {
      mountWithPreview(artifactProps);

      expect(wrapper.find('.ai-mention-tag').classes()).toContain('is-interactive');
    });

    it('非 artifact 类型点击不触发预览', async () => {
      const openPreview = mountWithPreview(baseProps);

      await wrapper.find('.ai-mention-tag').trigger('click');

      expect(openPreview).not.toHaveBeenCalled();
    });

    it('没有预览上下文时 artifact 标签不可交互', async () => {
      wrapper = mount(MentionTag, { props: artifactProps as never });

      await wrapper.find('.ai-mention-tag').trigger('click');

      expect(wrapper.find('.ai-mention-tag').classes()).not.toContain('is-interactive');
    });
  });
});
