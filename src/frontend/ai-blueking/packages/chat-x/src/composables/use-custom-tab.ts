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

import { type ShallowRef, ref as deepRef, inject, nextTick, provide, shallowRef } from 'vue';

import { t } from '../lang/lang';
import { type CustomTab } from '../types';

export const CUSTOM_TAB_TOKEN = Symbol('CUSTOM_TAB_TOKEN');
export const EXECUTION_TAB_NAME = 'execution';

export function useCustomTabProvider<T extends Record<string, unknown>>(options: {
  onTabChange?: (tab: CustomTab<T>) => void;
}) {
  const EXECUTION_TAB: CustomTab<T> = {
    label: t('执行情况'),
    name: EXECUTION_TAB_NAME,
  };
  const tabs = shallowRef<CustomTab<T>[]>([EXECUTION_TAB]);
  const selectedTab = deepRef<CustomTab<T>>(EXECUTION_TAB);
  const isCollapse = shallowRef(true);

  const addCustomTab = (tab: CustomTab<T>) => {
    if (!tabs.value.find(t => t.name === tab.name)) {
      tabs.value = [...tabs.value, tab];
    }
    isCollapse.value = false;
    nextTick(() => {
      selectCustomTab(tab);
    });
  };
  const removeCustomTab = (tabName: CustomTab<T>['name']) => {
    tabs.value = tabs.value.filter(tab => tab.name !== tabName);
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

  provide(CUSTOM_TAB_TOKEN, {
    tabs,
    selectedTab,
    addCustomTab,
    removeCustomTab,
    selectCustomTab,
    resetCustomTab,
  });

  return {
    tabs,
    selectedTab,
    isCollapse,
    addCustomTab,
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
        removeCustomTab: (tabName: CustomTab<T>['name']) => void;
        selectCustomTab: (tab: CustomTab<T>) => void;
        selectedTab: ShallowRef<CustomTab<T> | null>;
        tabs: ShallowRef<CustomTab<T>[]>;
      }
  >(CUSTOM_TAB_TOKEN);
};
