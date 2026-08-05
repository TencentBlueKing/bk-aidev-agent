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

import {
  type ComputedRef,
  type ShallowRef,
  computed,
  ref as deepRef,
  inject,
  nextTick,
  provide,
  shallowRef,
  watch,
} from 'vue';

import { t } from '../lang/lang';

import type { CustomTab } from '../types';

export const CUSTOM_TAB_TOKEN = Symbol('CUSTOM_TAB_TOKEN');
export const EXECUTION_TAB_NAME = 'execution';
/** 自定义 Tab 默认排序权重；执行情况固定为 0，业务自定义 Tab 缺省回退到此值 */
export const DEFAULT_TAB_ORDER = 100;

export function useCustomTabProvider<T extends Record<string, unknown>>(options: {
  /** 执行情况 Tab 是否展示，缺省 true；传 getter 以保持响应式 */
  executionTabVisible?: () => boolean | undefined;
  onTabChange?: (tab: CustomTab<T>) => void;
}) {
  const EXECUTION_TAB: CustomTab<T> = {
    closable: false,
    label: t('执行情况'),
    name: EXECUTION_TAB_NAME,
    order: 0,
  };
  const tabs = shallowRef<CustomTab<T>[]>([EXECUTION_TAB]);
  const selectedTab = deepRef<CustomTab<T>>(EXECUTION_TAB);
  const isCollapse = shallowRef(true);

  /** 执行情况显隐由外部配置控制，缺省可见 */
  const isExecutionVisible = computed(() => options.executionTabVisible?.() ?? true);
  const isTabVisible = (tab: Pick<CustomTab<T>, 'name' | 'visible'>) =>
    tab.name === EXECUTION_TAB_NAME ? isExecutionVisible.value : tab.visible !== false;

  /**
   * Tab 栏实际展示列表：过滤掉不可见 Tab，并按 order 升序稳定排序（同 order 保持插入顺序）。
   * 原始 tabs 仍保留全部 Tab，供程序化选中与查找。
   */
  const displayTabs = computed(() =>
    tabs.value
      .filter(isTabVisible)
      .slice()
      .sort((a, b) => (a.order ?? DEFAULT_TAB_ORDER) - (b.order ?? DEFAULT_TAB_ORDER)),
  );

  /** 写入 / 合并 Tab 元信息，不改变展开态与当前选中 */
  const upsertCustomTab = (tab: CustomTab<T>) => {
    const index = tabs.value.findIndex(item => item.name === tab.name);
    if (index === -1) {
      tabs.value = [...tabs.value, tab];
      return;
    }
    // 同名 Tab 合并更新，支持运行时调整 order / visible / label 等元信息
    const next = tabs.value.slice();
    next[index] = { ...next[index], ...tab };
    tabs.value = next;
  };

  /**
   * 确保 Tab 存在（可合并更新），不展开侧栏、不切换选中。
   * 用于「侧栏已因执行情况打开时同步挂上文件产物」等场景。
   */
  const ensureCustomTab = (tab: CustomTab<T>) => {
    upsertCustomTab(tab);
  };

  const addCustomTab = (tab: CustomTab<T>) => {
    upsertCustomTab(tab);
    isCollapse.value = false;
    nextTick(() => {
      selectCustomTab(tabs.value.find(item => item.name === tab.name)!);
    });
  };
  const removeCustomTab = (tabName: CustomTab<T>['name']) => {
    tabs.value = tabs.value.filter(tab => tab.name !== tabName);
    if (displayTabs.value.length === 0) {
      isCollapse.value = true;
    }
  };
  const selectCustomTab = (tab: CustomTab<T>) => {
    selectedTab.value = tab ?? EXECUTION_TAB;
    options.onTabChange?.(tab);
  };

  const resetCustomTab = () => {
    tabs.value = [EXECUTION_TAB];
    selectedTab.value = EXECUTION_TAB;
    isCollapse.value = true;
  };

  /**
   * 选中 Tab 被隐藏时（如执行情况被配置隐藏），不渲染其内容，自动切到首个可见 Tab；
   * 无可见 Tab 时保持原选中，由模板内容守卫兜底为空。
   */
  watch(displayTabs, list => {
    if (isTabVisible(selectedTab.value)) {
      return;
    }
    if (list.length) {
      selectCustomTab(list[0]);
    }
  });

  provide(CUSTOM_TAB_TOKEN, {
    tabs,
    displayTabs,
    selectedTab,
    addCustomTab,
    ensureCustomTab,
    removeCustomTab,
    selectCustomTab,
    resetCustomTab,
  });

  return {
    tabs,
    displayTabs,
    selectedTab,
    isCollapse,
    addCustomTab,
    ensureCustomTab,
    removeCustomTab,
    selectCustomTab,
    resetCustomTab,
  };
}

export const useCustomTabConsumer = <T extends Record<string, unknown>>() => {
  return inject<
    | undefined
    | {
        addCustomTab: (tab: CustomTab<T>) => void;
        displayTabs: ComputedRef<CustomTab<T>[]>;
        ensureCustomTab: (tab: CustomTab<T>) => void;
        removeCustomTab: (tabName: CustomTab<T>['name']) => void;
        selectCustomTab: (tab: CustomTab<T>) => void;
        selectedTab: ShallowRef<CustomTab<T> | null>;
        tabs: ShallowRef<CustomTab<T>[]>;
      }
  >(CUSTOM_TAB_TOKEN);
};
