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
import type { lang } from '../../../lang/lang';
import type { MenuItemType, MenuTrigger } from '../../../types/input-menu';

/** 分组的静态定义：一个分组可聚合多个语义相近的 type */
export interface IMenuGroupDef {
  /** 该分组无数据时是否仍然渲染并展示「暂无数据」 */
  keepWhenEmpty: boolean;
  key: string;
  /** 文案 key，渲染时经 t() 转换 */
  name: keyof typeof lang;
  types: MenuItemType[];
}

export const MENU_GROUP_DEFS = {
  add: { key: 'add', name: '添加', types: ['file'], keepWhenEmpty: false },
  skill: { key: 'skill', name: 'Skill', types: ['skill'], keepWhenEmpty: false },
  mcp: { key: 'mcp', name: 'MCP', types: ['mcp'], keepWhenEmpty: false },
  tool: { key: 'tool', name: '工具', types: ['tool'], keepWhenEmpty: false },
  // 后端历史上用 doc / knowledgebase 表示同一语义，面板里合并成一个分组
  knowledgebase: { key: 'knowledgebase', name: '知识库', types: ['knowledgebase', 'doc'], keepWhenEmpty: false },
  // 设计稿标注：没有会话产物时该分组仍需展示「暂无数据」
  artifact: { key: 'artifact', name: '会话产物', types: ['artifact'], keepWhenEmpty: true },
  prompt: { key: 'prompt', name: 'Prompt', types: ['prompt'], keepWhenEmpty: false },
} satisfies Record<string, IMenuGroupDef>;

export type MenuGroupKey = keyof typeof MENU_GROUP_DEFS;

/** 触发方式 → 分组渲染顺序 */
export const TRIGGER_GROUP_KEYS: Record<MenuTrigger, MenuGroupKey[]> = {
  '/': ['skill', 'mcp', 'tool'],
  '@': ['knowledgebase', 'artifact'],
  '\\': ['prompt'],
  plus: ['add', 'skill', 'mcp', 'tool', 'knowledgebase', 'artifact', 'prompt'],
};

/** 需要在下方画分隔线的分组（设计稿：+ 菜单「添加」组与其余资源之间有分隔线） */
export const DIVIDED_GROUP_KEYS: MenuGroupKey[] = ['add'];

/** 分组默认最多展示的条数，超出折叠为「更多 +N」 */
export const DEFAULT_GROUP_ITEM_LIMIT = 4;

/** 字符触发符与菜单的对应关系 */
export const CHAR_TRIGGERS = ['@', '/', '\\'] as const satisfies readonly MenuTrigger[];

/** type → 分组名，由分组定义反查生成，避免菜单与标签各维护一份映射 */
const MENU_TYPE_LABELS = Object.values(MENU_GROUP_DEFS).reduce<Partial<Record<MenuItemType, keyof typeof lang>>>(
  (acc, def) => {
    for (const type of def.types) {
      acc[type] = def.name;
    }
    return acc;
  },
  {},
);

/**
 * 取类型的展示名（文案 key，渲染时经 t() 转换）。
 * 菜单分组标题与标签气泡标题共用，保证两处文案永远一致。
 */
export const getMenuTypeLabel = (type: string): '' | keyof typeof lang => MENU_TYPE_LABELS[type as MenuItemType] ?? '';
