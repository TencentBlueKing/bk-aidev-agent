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

import { type VueWrapper, mount } from '@vue/test-utils';
import { afterEach, describe, expect, it, vi } from 'vitest';

import UserQuestionAnsweredCard from './user-question-answered-card.vue';

import type { UserQuestionAnswerItem } from '../../../../ag-ui/types/interrupt';

vi.mock('../../../../lang/lang', () => ({
  t: (key: string) => key,
}));

const answers: UserQuestionAnswerItem[] = [
  {
    question: '请选择方案',
    multiSelect: true,
    answer: [
      { label: 'A', description: '方案1' },
      { label: 'B', description: '方案2' },
    ],
  },
  {
    question: '请选择语言',
    multiSelect: false,
    answer: [{ label: 'others', description: 'Rust' }],
  },
];

describe('UserQuestionAnsweredCard', () => {
  let wrapper: VueWrapper;

  afterEach(() => {
    wrapper?.unmount();
  });

  it('渲染标题与已回复状态', () => {
    wrapper = mount(UserQuestionAnsweredCard, { props: { answers } });

    expect(wrapper.find('.ai-user-question-answered__title').text()).toBe('回答内容');
    expect(wrapper.find('.ai-user-question-answered__status').text()).toBe('已回复');
  });

  it('逐题回显问题与答案，多选问题展示「多选」标签', () => {
    wrapper = mount(UserQuestionAnsweredCard, { props: { answers } });

    const items = wrapper.findAll('.ai-user-question-answered__item');
    expect(items).toHaveLength(2);
    expect(items[0].find('.ai-user-question-answered__question-text').text()).toBe('1. 请选择方案');
    expect(items[0].find('.ai-user-question-answered__tag').text()).toBe('多选');
    expect(items[0].text()).toContain('方案1');
    expect(items[0].text()).toContain('方案2');
  });

  it('Others 答案优先展示用户自定义文本', () => {
    wrapper = mount(UserQuestionAnsweredCard, { props: { answers } });

    expect(wrapper.text()).toContain('Rust');
  });

  it('multiSelect 未定义时不渲染标签', () => {
    wrapper = mount(UserQuestionAnsweredCard, {
      props: { answers: [{ question: 'Q', answer: [{ label: 'x', description: 'x' }] }] },
    });

    expect(wrapper.find('.ai-user-question-answered__tag').exists()).toBe(false);
  });

  it('自定义 #answer 回显 slot：替换默认逐条渲染', () => {
    wrapper = mount(UserQuestionAnsweredCard, {
      props: { answers },
      slots: {
        answer: `
          <template #answer="{ item, index }">
            <div class="custom-answer">{{ index }}-{{ item.question }}-{{ item.answer.length }}</div>
          </template>
        `,
      },
    });

    const customAnswers = wrapper.findAll('.custom-answer');
    expect(customAnswers).toHaveLength(2);
    expect(customAnswers[0].text()).toBe('0-请选择方案-2');
    // 默认逐条段落不再渲染
    expect(wrapper.find('.ai-user-question-answered__answer').exists()).toBe(false);
  });
});
