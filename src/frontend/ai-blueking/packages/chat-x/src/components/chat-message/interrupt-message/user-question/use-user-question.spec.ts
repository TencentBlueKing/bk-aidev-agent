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

import { describe, expect, it } from 'vitest';

import { InterruptReason } from '../../../../ag-ui/types/constants';
import { OTHERS_OPTION_LABEL, toLetter, useUserQuestion } from './use-user-question';

import type { UserQuestionAnswerItem, UserQuestionInterrupt } from '../../../../ag-ui/types/interrupt';

const buildInterrupt = (overrides?: Partial<UserQuestionInterrupt>): UserQuestionInterrupt => ({
  id: 'uq-1',
  reason: InterruptReason.UserQuestion,
  toolCallId: 'tc-1',
  message: '选择方案',
  metadata: {
    questions: [
      {
        header: '选择方案',
        multiSelect: false,
        question: 'Q1',
        options: [{ label: 'A', description: 'a' }],
      },
      {
        header: '选择方案',
        multiSelect: true,
        question: 'Q2',
        options: [{ label: 'B', description: 'b' }],
      },
      {
        header: '选择方案',
        multiSelect: false,
        question: 'Q3',
        options: [{ label: 'C', description: 'c' }],
      },
    ],
  },
  ...overrides,
});

const buildAnswer = (
  question: string,
  options: UserQuestionAnswerItem['answer'],
  multiSelect?: boolean,
): UserQuestionAnswerItem => ({
  question,
  multiSelect,
  answer: options,
});

describe('useUserQuestion', () => {
  it('toLetter 应按索引映射 A-Z，超出后回退数字', () => {
    expect(toLetter(0)).toBe('A');
    expect(toLetter(25)).toBe('Z');
    expect(toLetter(26)).toBe('27');
  });

  it('初始 currentIndex 为 0，边界箭头态正确', () => {
    const { currentIndex, canGoPrev, canGoNext, totalCount, answeredCount, completed } = useUserQuestion(() =>
      buildInterrupt(),
    );

    expect(currentIndex.value).toBe(0);
    expect(totalCount.value).toBe(3);
    expect(answeredCount.value).toBe(0);
    expect(completed.value).toBe(false);
    expect(canGoPrev.value).toBe(false);
    expect(canGoNext.value).toBe(true);
  });

  it('goPrev / goNext 应按边界切换 currentIndex', () => {
    const { currentIndex, canGoPrev, canGoNext, goPrev, goNext } = useUserQuestion(() => buildInterrupt());

    goPrev();
    expect(currentIndex.value).toBe(0);

    goNext();
    expect(currentIndex.value).toBe(1);
    expect(canGoPrev.value).toBe(true);

    goNext();
    expect(currentIndex.value).toBe(2);
    expect(canGoNext.value).toBe(false);

    goNext();
    expect(currentIndex.value).toBe(2);
  });

  it('单选从未答变为有效答时应自动跳到下一题', () => {
    const { currentIndex, answeredCount, setAnswer } = useUserQuestion(() => buildInterrupt());

    setAnswer(0, buildAnswer('Q1', [{ label: 'A', description: 'a' }], false));
    expect(answeredCount.value).toBe(1);
    expect(currentIndex.value).toBe(1);
  });

  it('最后一题单选作答后应停留，不越界', () => {
    const { currentIndex, goNext, setAnswer } = useUserQuestion(() => buildInterrupt());

    goNext();
    goNext();
    expect(currentIndex.value).toBe(2);

    setAnswer(2, buildAnswer('Q3', [{ label: 'C', description: 'c' }], false));
    expect(currentIndex.value).toBe(2);
  });

  it('多选作答后不应自动跳转', () => {
    const { currentIndex, goNext, setAnswer, answeredCount } = useUserQuestion(() => buildInterrupt());

    goNext();
    setAnswer(1, buildAnswer('Q2', [{ label: 'B', description: 'b' }], true));
    expect(answeredCount.value).toBe(1);
    expect(currentIndex.value).toBe(1);
  });

  it('Others 有效作答后不应自动跳转', () => {
    const { currentIndex, setAnswer, answeredCount } = useUserQuestion(() => buildInterrupt());

    setAnswer(
      0,
      buildAnswer('Q1', [{ label: OTHERS_OPTION_LABEL, description: '自定义内容' }], false),
    );
    expect(answeredCount.value).toBe(1);
    expect(currentIndex.value).toBe(0);
  });

  it('改选已答题不应再次自动跳转', () => {
    const { currentIndex, goPrev, setAnswer } = useUserQuestion(() => buildInterrupt());

    setAnswer(0, buildAnswer('Q1', [{ label: 'A', description: 'a' }], false));
    expect(currentIndex.value).toBe(1);

    goPrev();
    setAnswer(0, buildAnswer('Q1', [{ label: 'A', description: '改选' }], false));
    expect(currentIndex.value).toBe(0);
  });

  it('非当前题写入答案不应触发自动跳转', () => {
    const { currentIndex, setAnswer } = useUserQuestion(() => buildInterrupt());

    setAnswer(2, buildAnswer('Q3', [{ label: 'C', description: 'c' }], false));
    expect(currentIndex.value).toBe(0);
  });

  it('全部作答后 completed 为 true，resolve payload 与题目一一对应', () => {
    const interrupt = buildInterrupt();
    const { setAnswer, completed, buildResolvePayload, goNext } = useUserQuestion(() => interrupt);

    setAnswer(0, buildAnswer('Q1', [{ label: 'A', description: 'a' }], false));
    setAnswer(1, buildAnswer('Q2', [{ label: 'B', description: 'b' }], true));
    // 自动跳到 Q2 后需手动到 Q3
    goNext();
    setAnswer(2, buildAnswer('Q3', [{ label: 'C', description: 'c' }], false));

    expect(completed.value).toBe(true);
    const payload = buildResolvePayload();
    expect(payload.status).toBe('resolved');
    expect(payload.interruptId).toBe('uq-1');
    expect(payload.payload.answers).toHaveLength(3);
    expect(payload.payload.answers[0].answer[0].label).toBe('A');
  });

  it('skip payload 应为 cancelled 且空答案', () => {
    const { buildSkipPayload } = useUserQuestion(() => buildInterrupt());
    const payload = buildSkipPayload();
    expect(payload.status).toBe('cancelled');
    expect(payload.payload.answers).toEqual([]);
  });

  it('清空答案后 answeredCount 应回退', () => {
    const { setAnswer, answeredCount, getAnswer } = useUserQuestion(() => buildInterrupt());

    setAnswer(0, buildAnswer('Q1', [{ label: 'A', description: 'a' }], false));
    expect(answeredCount.value).toBe(1);
    setAnswer(0, undefined);
    expect(answeredCount.value).toBe(0);
    expect(getAnswer(0)).toBeUndefined();
  });
});
