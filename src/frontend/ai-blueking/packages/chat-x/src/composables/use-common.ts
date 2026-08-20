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

import { type ComputedRef, type MaybeRef, computed, inject, provide, shallowRef, toValue } from 'vue';

import { RenderMode } from '../common/constants';

import type { AITippyProps } from '../types';

/**
 * 执行情况下的全局搜索关键词 token
 */
export const KEYWORD_TOKEN = Symbol('KEYWORD_TOKEN');

export const RENDER_MODE_TOKEN = Symbol('RENDER_MODE_TOKEN');
export const COMMON_TIPPY_OPTIONS_TOKEN = Symbol('COMMON_TIPPY_OPTIONS_TOKEN');
/**
 * 侧栏「执行情况」面板上下文 token。
 * 面板与对话流复用同一套消息渲染链路，内容组件据此按面板场景只读呈现。
 */
export const EXECUTION_PANEL_TOKEN = Symbol('EXECUTION_PANEL_TOKEN');
export const useKeywordProvider = () => {
  const keyword = shallowRef('');
  provide(
    KEYWORD_TOKEN,
    computed(() => keyword.value),
  );
  return {
    keyword,
  };
};
export const useRenderModeProvider = ({ renderMode }: { renderMode: MaybeRef<RenderMode> }) => {
  provide(
    RENDER_MODE_TOKEN,
    computed(() => toValue(renderMode)),
  );
  return { renderMode };
};

export const useRenderModeInject = () => {
  return inject<ComputedRef<RenderMode>>(
    RENDER_MODE_TOKEN,
    computed(() => RenderMode.Chat),
  );
};
export const useCommonTippyProvider = (options: { tippyOptions: ComputedRef<AITippyProps | undefined> }) => {
  provide(COMMON_TIPPY_OPTIONS_TOKEN, options.tippyOptions);
};

export const useKeywordInject = () => {
  return inject<ComputedRef<string> | undefined>(KEYWORD_TOKEN, undefined);
};

export const useCommonTippyInject = () => {
  return inject<ComputedRef<AITippyProps> | undefined>(COMMON_TIPPY_OPTIONS_TOKEN, undefined);
};

/** 侧栏「执行情况」面板内渲染消息时调用；面板身份在组件树中恒定，无需响应式 */
export const useExecutionPanelProvider = () => {
  provide(EXECUTION_PANEL_TOKEN, true);
};

/** 是否处于侧栏「执行情况」面板内；缺省 false，即对话流内渲染 */
export const useExecutionPanelInject = () => {
  return inject<boolean>(EXECUTION_PANEL_TOKEN, false);
};

export const useKeywordMatch = (getSearchTexts: () => (string | undefined)[]) => {
  const keyword = useKeywordInject();
  const keywordMatched = computed(() => {
    const kw = keyword?.value?.trim().toLowerCase();
    if (!kw) return null;
    return getSearchTexts()
      .filter(Boolean)
      .some(text => text?.toLowerCase().includes(kw));
  });
  return { keywordMatched, keyword };
};
