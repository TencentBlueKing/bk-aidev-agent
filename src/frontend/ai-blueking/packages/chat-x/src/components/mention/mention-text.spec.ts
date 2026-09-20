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

import MentionText from './mention-text.vue';

import type { TagSchema } from '../../types/input';

vi.mock('./mention-tag.vue', () => ({
  default: defineComponent({
    name: 'MentionTag',
    props: {
      description: { type: String, default: '' },
      icon: { type: String, default: '' },
      label: { type: String, default: '' },
      type: { type: String, default: '' },
      value: { type: String, default: '' },
    },
    setup(props) {
      return () =>
        h('span', { class: 'mock-mention-tag', 'data-type': props.type, 'data-value': props.value }, props.label);
    },
  }),
}));

describe('MentionText', () => {
  let wrapper: VueWrapper;

  afterEach(() => {
    wrapper?.unmount();
  });

  it('文本节点按原文渲染', () => {
    const doc = [[{ type: 'text', text: '帮我查一下' }]] as TagSchema;
    wrapper = mount(MentionText, { props: { doc } });

    expect(wrapper.find('.ai-mention-text').text()).toBe('帮我查一下');
    expect(wrapper.find('.mock-mention-tag').exists()).toBe(false);
  });

  it('标签节点把 data 透传给 MentionTag', () => {
    const doc = [
      [
        {
          type: 'tag',
          data: {
            label: '知识库01',
            value: 'kb_01',
            type: 'knowledgebase',
            icon: 'https://x/kb.png',
            description: '介绍',
          },
        },
      ],
    ] as TagSchema;
    wrapper = mount(MentionText, { props: { doc } });

    const tag = wrapper.findComponent({ name: 'MentionTag' });
    expect(tag.props()).toMatchObject({
      label: '知识库01',
      value: 'kb_01',
      type: 'knowledgebase',
      icon: 'https://x/kb.png',
      description: '介绍',
    });
  });

  it('同一行内文本与标签交错渲染', () => {
    const doc = [
      [
        { type: 'text', text: '帮我查一下 ' },
        { type: 'tag', data: { label: '知识库01', value: 'kb_01', type: 'knowledgebase' } },
        { type: 'text', text: ' 的内容' },
      ],
    ] as TagSchema;
    wrapper = mount(MentionText, { props: { doc } });

    expect(wrapper.find('.mock-mention-tag').text()).toBe('知识库01');
    expect(wrapper.text()).toBe('帮我查一下 知识库01 的内容');
  });

  it('多行之间用 br 连接，行内连续空格保留', () => {
    const doc = [
      [{ type: 'text', text: '第一行  两个空格' }],
      [{ type: 'tag', data: { label: '知识库01', value: 'kb_01', type: 'knowledgebase' } }],
    ] as TagSchema;
    wrapper = mount(MentionText, { props: { doc } });

    expect(wrapper.find('br').exists()).toBe(true);
    expect(wrapper.text()).toContain('第一行  两个空格');
    expect(wrapper.findAll('.mock-mention-tag')).toHaveLength(1);
  });
});
