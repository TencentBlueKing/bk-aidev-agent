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
import { computed, ref as deepRef } from 'vue';

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
const toLetter = (index: number): string => (index < 26 ? String.fromCharCode(65 + index) : String(index + 1));

/** 归一化后的展示问题（已为每题在末尾补齐 Others 输入项） */
export type NormalizedUserQuestion = UserQuestionItem & {
  displayOptions: NormalizedUserQuestionOption[];
};

/** 归一化后的展示选项（含字母序号与 Others 标记） */
export type NormalizedUserQuestionOption = UserQuestionOptionItem & {
  isOthers: boolean;
  letter: string;
};

/**
 * 用户回答问题（human-in-the-loop）选择态管理与 resume payload 构建。
 *
 * 设计目标：把「选择/输入状态」「已答校验」「payload 组装」集中到 composable，
 * 让卡片组件保持纯展示，便于后续自定义不同的回答形式时复用同一套状态逻辑。
 *
 * @param getInterrupt 返回当前 UserQuestion 中断的 getter（响应式）
 */
export const useUserQuestion = (getInterrupt: () => undefined | UserQuestionInterrupt) => {
  // 选中项：questionIndex -> 选中的 optionIndex 列表（单选时长度恒为 0/1）
  const selectedMap = deepRef<Record<number, number[]>>({});
  // Others 输入文本：questionIndex -> 文本
  const othersTextMap = deepRef<Record<number, string>>({});

  const normalizedQuestions = computed<NormalizedUserQuestion[]>(() => {
    const questions = getInterrupt()?.metadata?.questions ?? [];
    return questions.map(question => {
      // 过滤后端可能返回的 others，统一由前端在末尾追加 Others 输入项
      const baseOptions = (question.options ?? []).filter(option => option.label !== OTHERS_OPTION_LABEL);
      const displayOptions: NormalizedUserQuestionOption[] = baseOptions.map((option, index) => ({
        ...option,
        isOthers: false,
        letter: toLetter(index),
      }));
      displayOptions.push({
        label: OTHERS_OPTION_LABEL,
        description: '',
        isOthers: true,
        letter: toLetter(displayOptions.length),
      });
      return { ...question, displayOptions };
    });
  });

  const isOptionSelected = (questionIndex: number, optionIndex: number): boolean =>
    (selectedMap.value[questionIndex] ?? []).includes(optionIndex);

  /** 切换选项：单选直接置为该项，多选则 toggle */
  const toggleOption = (questionIndex: number, optionIndex: number) => {
    const question = normalizedQuestions.value[questionIndex];
    if (!question) return;
    const current = selectedMap.value[questionIndex] ?? [];
    const next = question.multiSelect
      ? current.includes(optionIndex)
        ? current.filter(item => item !== optionIndex)
        : [...current, optionIndex]
      : [optionIndex];
    selectedMap.value = { ...selectedMap.value, [questionIndex]: next };
  };

  const getOthersText = (questionIndex: number): string => othersTextMap.value[questionIndex] ?? '';

  const setOthersText = (questionIndex: number, text: string) => {
    othersTextMap.value = { ...othersTextMap.value, [questionIndex]: text };
  };

  /** 单题是否已作答：至少选中一项；若选中 Others 则要求输入非空 */
  const isQuestionAnswered = (questionIndex: number): boolean => {
    const selected = selectedMap.value[questionIndex] ?? [];
    if (!selected.length) return false;
    const question = normalizedQuestions.value[questionIndex];
    const othersIndex = question?.displayOptions.findIndex(option => option.isOthers) ?? -1;
    if (othersIndex >= 0 && selected.includes(othersIndex)) {
      return getOthersText(questionIndex).trim().length > 0;
    }
    return true;
  };

  const totalCount = computed(() => normalizedQuestions.value.length);
  const answeredCount = computed(() =>
    normalizedQuestions.value.reduce((count, _question, index) => count + (isQuestionAnswered(index) ? 1 : 0), 0),
  );
  /** 全部问题均已作答方可「完成」 */
  const completed = computed(() => totalCount.value > 0 && answeredCount.value === totalCount.value);

  /** 组装各题答案 */
  const buildAnswers = (): UserQuestionAnswerItem[] =>
    normalizedQuestions.value.map((question, questionIndex) => {
      const selected = selectedMap.value[questionIndex] ?? [];
      const answer: UserQuestionOptionItem[] = selected.map(optionIndex => {
        const option = question.displayOptions[optionIndex];
        if (option?.isOthers) {
          return { label: OTHERS_OPTION_LABEL, description: getOthersText(questionIndex).trim() };
        }
        return { label: option?.label ?? '', description: option?.description ?? '' };
      });
      return { question: question.question, answer, multiSelect: question.multiSelect };
    });

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
    normalizedQuestions,
    answeredCount,
    totalCount,
    completed,
    isOptionSelected,
    toggleOption,
    getOthersText,
    setOthersText,
    isQuestionAnswered,
    buildResolvePayload,
    buildSkipPayload,
  };
};

/**
 * 自由文本 resume（用户在 chat-input 直接输入而非走结构化选择）。
 * 多题场景下信息有损：统一作为单条 Others 自由文本回传。
 */
export const buildUserQuestionFreeTextResume = (interrupt: UserQuestionInterrupt, text: string): UserQuestionResume => ({
  interruptId: interrupt.id,
  reason: InterruptReason.UserQuestion,
  status: 'resolved',
  payload: {
    answers: [{ question: '', answer: [{ label: OTHERS_OPTION_LABEL, description: text }] }],
  },
});
