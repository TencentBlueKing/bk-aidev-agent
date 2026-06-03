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
import { computed, shallowRef } from 'vue';

import { InterruptReason } from '../../../../ag-ui/types/constants';

import type {
  UserQuestionAnswerItem,
  UserQuestionInterrupt,
  UserQuestionItem,
  UserQuestionOptionItem,
  UserQuestionResume,
} from '../../../../ag-ui/types/interrupt';

/** label 为该值的选项代表「Others 自定义输入」 */
export const OTHERS_OPTION_LABEL = 'others';

/** 选项序号字母：0 -> A、1 -> B …… 超过 26 时回退为数字 */
export const toLetter = (index: number): string => (index < 26 ? String.fromCharCode(65 + index) : String(index + 1));

/** 归一化后的展示选项（含字母序号与 Others 标记），由选择题渲染组件内部使用 */
export type NormalizedUserQuestionOption = UserQuestionOptionItem & {
  isOthers: boolean;
  letter: string;
};

/**
 * 用户回答问题（human-in-the-loop）的答案聚合与 resume payload 构建。
 *
 * 设计目标：composable 只负责「收集每题答案 + 完成态计算 + payload 组装」，
 * 对「回答形态」（单选/多选/表单/任意自定义）零感知；
 * 各题如何作答与如何校验，全部下沉到对应的渲染组件（默认为选择题），
 * 渲染组件作答有效时回传已组装的 {@link UserQuestionAnswerItem}，无效时回传 undefined。
 *
 * @param getInterrupt 返回当前 UserQuestion 中断的 getter（响应式）
 */
export const useUserQuestion = (getInterrupt: () => undefined | UserQuestionInterrupt) => {
  const questions = computed<UserQuestionItem[]>(() => getInterrupt()?.metadata?.questions ?? []);

  // 每题答案：questionIndex -> 已组装答案；undefined 代表该题未作答
  const answerMap = shallowRef<Record<number, undefined | UserQuestionAnswerItem>>({});

  const getAnswer = (questionIndex: number): undefined | UserQuestionAnswerItem => answerMap.value[questionIndex];

  /** 写入/清空某题答案：传 undefined 表示该题回到未作答态 */
  const setAnswer = (questionIndex: number, answer: undefined | UserQuestionAnswerItem) => {
    answerMap.value = { ...answerMap.value, [questionIndex]: answer };
  };

  const totalCount = computed(() => questions.value.length);
  const answeredCount = computed(() =>
    questions.value.reduce((count, _question, index) => count + (answerMap.value[index] ? 1 : 0), 0),
  );
  /** 全部问题均已作答方可「完成」 */
  const completed = computed(() => totalCount.value > 0 && answeredCount.value === totalCount.value);

  /** 组装各题答案；未作答题以空答案兜底，保证与问题一一对应 */
  const buildAnswers = (): UserQuestionAnswerItem[] =>
    questions.value.map((question, index) => answerMap.value[index] ?? { question: question.question, answer: [] });

  /** 完成：resolved + 各题答案 */
  const buildResolvePayload = (): UserQuestionResume => ({
    interruptId: getInterrupt()?.id ?? '',
    reason: InterruptReason.UserQuestion,
    status: 'resolved',
    payload: { answers: buildAnswers() },
  });

  /** 跳过：cancelled + 空答案 */
  const buildSkipPayload = (): UserQuestionResume => ({
    interruptId: getInterrupt()?.id ?? '',
    reason: InterruptReason.UserQuestion,
    status: 'cancelled',
    payload: { answers: [] },
  });

  return {
    questions,
    answeredCount,
    totalCount,
    completed,
    getAnswer,
    setAnswer,
    buildResolvePayload,
    buildSkipPayload,
  };
};

/**
 * 自由文本 resume（用户在 chat-input 直接输入而非走结构化选择）。
 * 多题场景下信息有损：统一作为单条 Others 自由文本回传。
 */
export const buildUserQuestionFreeTextResume = (
  interrupt: UserQuestionInterrupt,
  text: string,
): UserQuestionResume => ({
  interruptId: interrupt.id,
  reason: InterruptReason.UserQuestion,
  status: 'resolved',
  payload: {
    answers: [{ question: '', answer: [{ label: OTHERS_OPTION_LABEL, description: text }] }],
  },
});
