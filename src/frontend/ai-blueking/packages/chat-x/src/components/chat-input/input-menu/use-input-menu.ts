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
import { type ComputedRef, type Ref, computed, shallowRef, watch } from 'vue';

import { DIVIDED_GROUP_KEYS, MENU_GROUP_DEFS, TRIGGER_GROUP_KEYS } from './constants';

import type { IInputMenuGroup, IInputMenuItem, MenuItemType, MenuTrigger } from '../../../types/input-menu';
import type { MenuGroupKey } from './constants';

/**
 * 输入框菜单的纯数据逻辑（与 UI 解耦，可独立单测）：
 * 按触发方式筛选类型 → 按关键字过滤 → 分组 → 应用折叠阈值 → 扁平化供键盘导航。
 */
export const useInputMenu = (params: {
  /** 每个分组默认展示的条数上限 */
  groupItemLimit: ComputedRef<number> | Ref<number>;
  /** 过滤关键字（触发符之后用户输入的文本） */
  keyword: ComputedRef<string> | Ref<string>;
  /** 全部可选项 */
  sources: ComputedRef<IInputMenuItem[]> | Ref<IInputMenuItem[]>;
  /** 当前触发方式，为 null 表示菜单未激活 */
  trigger: ComputedRef<MenuTrigger | null> | Ref<MenuTrigger | null>;
}) => {
  /** 用户手动展开的分组 key */
  const expandedKeys = shallowRef<MenuGroupKey[]>([]);

  // 关键字或触发方式变化时结果集完全不同，沿用上一次的展开状态会造成误导
  watch([() => params.keyword.value, () => params.trigger.value], () => {
    expandedKeys.value = [];
  });

  const groups = computed<IInputMenuGroup[]>(() => {
    const trigger = params.trigger.value;
    if (!trigger) {
      return [];
    }
    const limit = Math.max(params.groupItemLimit.value, 1);
    const keyword = params.keyword.value.trim().toLowerCase();
    const result: IInputMenuGroup[] = [];
    // keepWhenEmpty 的分组不计入总数：整个面板没有任何真实条目时不应弹出
    let totalCount = 0;

    for (const key of TRIGGER_GROUP_KEYS[trigger]) {
      const def = MENU_GROUP_DEFS[key];
      const matched = params.sources.value.filter(
        item =>
          (def.types as MenuItemType[]).includes(item.type) && (!keyword || item.name.toLowerCase().includes(keyword)),
      );
      totalCount += matched.length;
      if (!matched.length && !def.keepWhenEmpty) {
        continue;
      }
      const expanded = expandedKeys.value.includes(key);
      const restCount = Math.max(matched.length - limit, 0);
      result.push({
        key,
        name: def.name,
        divided: DIVIDED_GROUP_KEYS.includes(key),
        expanded,
        items: expanded || !restCount ? matched : matched.slice(0, limit),
        restCount,
      });
    }

    return totalCount > 0 ? result : [];
  });

  /** 当前可见且可选中的条目，顺序与面板一致，供键盘上下选择 */
  const flatItems = computed<IInputMenuItem[]>(() =>
    groups.value.flatMap(group => group.items.filter(item => !item.disabled)),
  );

  const hasContent = computed(() => groups.value.length > 0);

  const toggleGroup = (key: MenuGroupKey) => {
    const index = expandedKeys.value.indexOf(key);
    expandedKeys.value =
      index === -1
        ? [...expandedKeys.value, key]
        : [...expandedKeys.value.slice(0, index), ...expandedKeys.value.slice(index + 1)];
  };

  return {
    groups,
    flatItems,
    hasContent,
    toggleGroup,
  };
};
