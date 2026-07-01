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

import { Button } from 'bkui-vue';

import { InterruptReason } from '../../../../ag-ui/types/constants';
import UserQuestionCard from './user-question-card.vue';

import type { UserQuestionInterrupt } from '../../../../ag-ui/types/interrupt';

// 避免 tippy/IntersectionObserver 在 jsdom 中的副作用
vi.mock('../../../../directives/overflow-tips', () => ({
  OverflowTips: {},
}));

vi.mock('../../../../lang/lang', () => ({
  t: (key: string) => key,
}));

const buildInterrupt = (): UserQuestionInterrupt => ({
  id: 'uq-1',
  reason: InterruptReason.UserQuestion,
  toolCallId: 'tc-1',
  message: '请回答问题',
  metadata: {
    questions: [
      {
        header: '请回答问题',
        multiSelect: false,
        question: 'Q1',
        options: [
          { label: 'A', description: 'a' },
          { label: 'B', description: 'b' },
        ],
      },
      {
        header: '请回答问题',
        multiSelect: true,
        question: 'Q2',
        options: [{ label: 'C', description: 'c' }],
      },
    ],
  },
});

describe('UserQuestionCard', () => {
  let wrapper: VueWrapper;

  afterEach(() => {
    wrapper?.unmount();
  });

  it('初始渲染标题、计数与全部题目（每题末尾追加 Others 输入项）', () => {
    wrapper = mount(UserQuestionCard, { props: { interrupt: buildInterrupt() } });

    expect(wrapper.find('.ai-user-question-card__title').text()).toBe('请回答问题');
    expect(wrapper.find('.ai-user-question-card__counter').text()).toBe('0 / 2');
    // Q1: A、B、Others = 3；Q2: C、Others = 2，共 5
    expect(wrapper.findAll('.ai-user-question-option')).toHaveLength(5);
  });

  it('选择选项后已答计数递增', async () => {
    wrapper = mount(UserQuestionCard, { props: { interrupt: buildInterrupt() } });

    const options = wrapper.findAll('.ai-user-question-option');
    await options[0].trigger('click'); // Q1.A
    expect(wrapper.find('.ai-user-question-card__counter').text()).toBe('1 / 2');
    await options[3].trigger('click'); // Q2.C
    expect(wrapper.find('.ai-user-question-card__counter').text()).toBe('2 / 2');
  });

  it('未答完时点击完成不触发 resume', async () => {
    const onResume = vi.fn();
    wrapper = mount(UserQuestionCard, { props: { interrupt: buildInterrupt(), onResume } });

    await wrapper.find('.ai-user-question-card__complete').trigger('click');
    expect(onResume).not.toHaveBeenCalled();
  });

  it('答完全部题后完成，按 resume 协议回传 resolved 答案', async () => {
    const onResume = vi.fn();
    const interrupt = buildInterrupt();
    wrapper = mount(UserQuestionCard, { props: { interrupt, onResume } });

    const options = wrapper.findAll('.ai-user-question-option');
    await options[0].trigger('click'); // Q1.A
    await options[3].trigger('click'); // Q2.C
    await wrapper.find('.ai-user-question-card__complete').trigger('click');

    expect(onResume).toHaveBeenCalledTimes(1);
    const [payload, itrpt] = onResume.mock.calls[0];
    expect(itrpt).toEqual(interrupt);
    expect(payload.status).toBe('resolved');
    expect(payload.interruptId).toBe('uq-1');
    expect(payload.payload.answers).toHaveLength(2);
    expect(payload.payload.answers[0]).toMatchObject({
      question: 'Q1',
      multiSelect: false,
      answer: [{ label: 'A', description: 'a' }],
    });
  });

  it('点击跳过按 resume 协议回传 cancelled 空答案', async () => {
    const onResume = vi.fn();
    const interrupt = buildInterrupt();
    wrapper = mount(UserQuestionCard, { props: { interrupt, onResume } });

    await wrapper.find('.ai-user-question-card__skip').trigger('click');

    expect(onResume).toHaveBeenCalledTimes(1);
    const [payload, itrpt] = onResume.mock.calls[0];
    expect(itrpt).toEqual(interrupt);
    expect(payload.status).toBe('cancelled');
    expect(payload.payload.answers).toHaveLength(0);
  });

  it('点击完成后完成按钮 loading、跳过按钮禁用，且防重复提交', async () => {
    const onResume = vi.fn();
    wrapper = mount(UserQuestionCard, { props: { interrupt: buildInterrupt(), onResume } });

    const options = wrapper.findAll('.ai-user-question-option');
    await options[0].trigger('click');
    await options[3].trigger('click');

    const completeBtn = wrapper.find('.ai-user-question-card__complete');
    const skipBtn = wrapper.find('.ai-user-question-card__skip');
    await completeBtn.trigger('click');
    await completeBtn.trigger('click');

    expect(onResume).toHaveBeenCalledTimes(1);
    expect(completeBtn.findComponent(Button).props('loading')).toBe(true);
    expect(skipBtn.findComponent(Button).props('disabled')).toBe(true);
    expect(wrapper.find('.ai-user-question-card__enter-icon').exists()).toBe(false);
  });

  it('点击跳过后跳过按钮 loading、完成按钮禁用，且防重复提交', async () => {
    const onResume = vi.fn();
    wrapper = mount(UserQuestionCard, { props: { interrupt: buildInterrupt(), onResume } });

    const skipBtn = wrapper.find('.ai-user-question-card__skip');
    const completeBtn = wrapper.find('.ai-user-question-card__complete');
    await skipBtn.trigger('click');
    await skipBtn.trigger('click');

    expect(onResume).toHaveBeenCalledTimes(1);
    expect(skipBtn.findComponent(Button).props('loading')).toBe(true);
    expect(completeBtn.findComponent(Button).props('disabled')).toBe(true);
    expect(wrapper.find('.ai-user-question-card__skip-icon').exists()).toBe(false);
  });

  it('点击箭头可折叠，body 与 footer 通过 v-show 隐藏而非卸载', async () => {
    wrapper = mount(UserQuestionCard, { props: { interrupt: buildInterrupt() } });

    await wrapper.find('.ai-user-question-card__arrow').trigger('click');
    expect(wrapper.classes()).toContain('ai-user-question-card--collapsed');
    // v-show 保留 DOM，避免折叠时丢失勾选态
    const body = wrapper.find('.ai-user-question-card__body');
    const footer = wrapper.find('.ai-user-question-card__footer');
    expect(body.exists()).toBe(true);
    expect(footer.exists()).toBe(true);
    expect((body.element as HTMLElement).style.display).toBe('none');
    expect((footer.element as HTMLElement).style.display).toBe('none');
  });

  it('折叠后再展开应保留已选答案', async () => {
    wrapper = mount(UserQuestionCard, { props: { interrupt: buildInterrupt() } });

    const options = wrapper.findAll('.ai-user-question-option');
    await options[0].trigger('click');
    expect(wrapper.find('.ai-user-question-card__counter').text()).toBe('1 / 2');

    await wrapper.find('.ai-user-question-card__arrow').trigger('click');
    expect(wrapper.find('.ai-user-question-card__counter').text()).toBe('1 / 2');

    await wrapper.find('.ai-user-question-card__arrow').trigger('click');
    expect(wrapper.findAll('.ai-user-question-option')[0].classes()).toContain('ai-user-question-option--selected');
    expect(wrapper.find('.ai-user-question-card__counter').text()).toBe('1 / 2');
  });

  it('选中 Others 但未输入文本不计为已答', async () => {
    wrapper = mount(UserQuestionCard, { props: { interrupt: buildInterrupt() } });

    const options = wrapper.findAll('.ai-user-question-option');
    // Q1 的 Others 为第 3 个（索引 2）
    await options[2].trigger('click');
    expect(wrapper.find('.ai-user-question-card__counter').text()).toBe('0 / 2');

    await options[2].find('.ai-user-question-option__input').setValue('自定义');
    expect(wrapper.find('.ai-user-question-card__counter').text()).toBe('1 / 2');
  });

  it('自定义 #question 表单 slot：通过 setAnswer 回传任意答案并驱动完成态', async () => {
    const onResume = vi.fn();
    const interrupt = buildInterrupt();
    wrapper = mount(UserQuestionCard, {
      props: { interrupt, onResume },
      slots: {
        // 模拟自定义表单：点击按钮即写入一条符合协议的答案
        question: `
          <template #question="{ question, setAnswer }">
            <button
              class="form-fill"
              @click="setAnswer({ question: question.question, answer: [{ label: 'custom', description: question.question + '-填写' }] })"
            >fill</button>
          </template>
        `,
      },
    });

    const fillButtons = wrapper.findAll('.form-fill');
    // 两题，需各自填写后才能完成
    expect(fillButtons).toHaveLength(2);
    await fillButtons[0].trigger('click');
    expect(wrapper.find('.ai-user-question-card__counter').text()).toBe('1 / 2');
    await fillButtons[1].trigger('click');
    expect(wrapper.find('.ai-user-question-card__counter').text()).toBe('2 / 2');

    await wrapper.find('.ai-user-question-card__complete').trigger('click');
    expect(onResume).toHaveBeenCalledTimes(1);
    const [payload] = onResume.mock.calls[0];
    expect(payload.status).toBe('resolved');
    expect(payload.payload.answers).toEqual([
      { question: 'Q1', answer: [{ label: 'custom', description: 'Q1-填写' }] },
      { question: 'Q2', answer: [{ label: 'custom', description: 'Q2-填写' }] },
    ]);
  });
});
