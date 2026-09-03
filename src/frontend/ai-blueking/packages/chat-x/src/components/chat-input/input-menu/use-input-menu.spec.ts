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
import { nextTick, shallowRef } from 'vue';

import { describe, expect, it } from 'vitest';

import { useInputMenu } from './use-input-menu';

import type { IInputMenuItem, MenuTrigger } from '../../../types/input-menu';

const buildSources = (): IInputMenuItem[] => [
  { id: 's1', type: 'skill', name: 'Hangzhou' },
  { id: 's2', type: 'skill', name: 'Guangzhou' },
  { id: 's3', type: 'skill', name: 'Shenzhen' },
  { id: 's4', type: 'skill', name: 'Beijing' },
  { id: 's5', type: 'skill', name: 'Shanghai' },
  { id: 'm1', type: 'mcp', name: 'Mcp_1' },
  { id: 't1', type: 'tool', name: 'Tool_1' },
  { id: 'k1', type: 'knowledgebase', name: '知识库01' },
  { id: 'd1', type: 'doc', name: '知识库02' },
  { id: 'a1', type: 'artifact', name: '操作文档.docx' },
  { id: 'p1', type: 'prompt', name: '深圳旅游攻略？', content: '深圳旅游攻略？' },
  { id: 'f1', type: 'file', name: '文件' },
];

const setup = (trigger: MenuTrigger | null, keyword = '', groupItemLimit = 4) =>
  useInputMenu({
    sources: shallowRef(buildSources()),
    keyword: shallowRef(keyword),
    trigger: shallowRef(trigger),
    groupItemLimit: shallowRef(groupItemLimit),
  });

describe('useInputMenu', () => {
  it('trigger 为空时不产出任何分组', () => {
    const { groups, hasContent } = setup(null);
    expect(groups.value).toEqual([]);
    expect(hasContent.value).toBe(false);
  });

  it('/ 触发只展示 Skill、MCP、工具三个分组且顺序固定', () => {
    const { groups } = setup('/');
    expect(groups.value.map(group => group.key)).toEqual(['skill', 'mcp', 'tool']);
  });

  it('@ 触发把 knowledgebase 与 doc 合并为知识库分组', () => {
    const { groups } = setup('@');
    expect(groups.value.map(group => group.key)).toEqual(['knowledgebase', 'artifact']);
    expect(groups.value[0].items.map(item => item.id)).toEqual(['k1', 'd1']);
  });

  it('plus 触发聚合全部分组，「添加」分组带分隔线', () => {
    const { groups } = setup('plus');
    expect(groups.value.map(group => group.key)).toEqual([
      'add',
      'skill',
      'mcp',
      'tool',
      'knowledgebase',
      'artifact',
      'prompt',
    ]);
    expect(groups.value[0].divided).toBe(true);
  });

  it('超过阈值的分组只展示前 N 条并给出折叠条数', () => {
    const { groups } = setup('/');
    const skillGroup = groups.value[0];
    expect(skillGroup.items).toHaveLength(4);
    expect(skillGroup.restCount).toBe(1);
    expect(skillGroup.expanded).toBe(false);
  });

  it('展开分组后展示全部条目', async () => {
    const { groups, toggleGroup } = setup('/');
    toggleGroup('skill');
    await nextTick();
    expect(groups.value[0].items).toHaveLength(5);
    expect(groups.value[0].expanded).toBe(true);
    expect(groups.value[0].restCount).toBe(1);
  });

  it('关键字按名称做大小写不敏感过滤', () => {
    const { groups } = setup('/', 'guang');
    expect(groups.value.map(group => group.key)).toEqual(['skill']);
    expect(groups.value[0].items.map(item => item.id)).toEqual(['s2']);
  });

  it('没有会话产物时该分组仍保留并交由面板展示暂无数据', () => {
    const { groups } = useInputMenu({
      sources: shallowRef<IInputMenuItem[]>([{ id: 'k1', type: 'knowledgebase', name: '知识库01' }]),
      keyword: shallowRef(''),
      trigger: shallowRef<MenuTrigger | null>('@'),
      groupItemLimit: shallowRef(4),
    });
    const artifactGroup = groups.value.find(group => group.key === 'artifact');
    expect(artifactGroup).toBeDefined();
    expect(artifactGroup?.items).toEqual([]);
  });

  it('整体没有任何条目时不产出分组，避免弹出空面板', () => {
    const { groups, hasContent } = useInputMenu({
      sources: shallowRef<IInputMenuItem[]>([]),
      keyword: shallowRef(''),
      trigger: shallowRef<MenuTrigger | null>('@'),
      groupItemLimit: shallowRef(4),
    });
    expect(groups.value).toEqual([]);
    expect(hasContent.value).toBe(false);
  });

  it('flatItems 按面板顺序扁平化且跳过禁用项', () => {
    const { flatItems } = useInputMenu({
      sources: shallowRef<IInputMenuItem[]>([
        { id: 'm1', type: 'mcp', name: 'Mcp_1' },
        { id: 'm2', type: 'mcp', name: 'Mcp_2', disabled: true },
        { id: 't1', type: 'tool', name: 'Tool_1' },
      ]),
      keyword: shallowRef(''),
      trigger: shallowRef<MenuTrigger | null>('/'),
      groupItemLimit: shallowRef(4),
    });
    expect(flatItems.value.map(item => item.id)).toEqual(['m1', 't1']);
  });

  it('\\ 触发只展示 Prompt 分组', () => {
    const { groups } = setup('\\');
    expect(groups.value.map(group => group.key)).toEqual(['prompt']);
    expect(groups.value[0].items.map(item => item.id)).toEqual(['p1']);
  });

  it('groupItemLimit 小于 1 时按 1 条展示', () => {
    const { groups } = setup('/', '', 0);
    expect(groups.value[0].items).toHaveLength(1);
    expect(groups.value[0].restCount).toBe(4);
  });

  it('关键字会先 trim 再做大小写不敏感过滤', () => {
    const { groups } = setup('/', '  Guang  ');
    expect(groups.value[0].items.map(item => item.id)).toEqual(['s2']);
  });

  it('再次 toggle 同一分组会收起', async () => {
    const { groups, toggleGroup } = setup('/');
    toggleGroup('skill');
    await nextTick();
    expect(groups.value[0].expanded).toBe(true);

    toggleGroup('skill');
    await nextTick();
    expect(groups.value[0].expanded).toBe(false);
    expect(groups.value[0].items).toHaveLength(4);
  });

  it('触发方式变化后重置已展开的分组', async () => {
    const trigger = shallowRef<MenuTrigger | null>('/');
    const { groups, toggleGroup } = useInputMenu({
      sources: shallowRef(buildSources()),
      keyword: shallowRef(''),
      trigger,
      groupItemLimit: shallowRef(4),
    });
    toggleGroup('skill');
    await nextTick();
    expect(groups.value[0].expanded).toBe(true);

    trigger.value = '@';
    await nextTick();
    expect(groups.value.every(group => !group.expanded)).toBe(true);
  });

  it('关键字变化后重置已展开的分组', async () => {
    const keyword = shallowRef('');
    const { groups, toggleGroup } = useInputMenu({
      sources: shallowRef(buildSources()),
      keyword,
      trigger: shallowRef<MenuTrigger | null>('/'),
      groupItemLimit: shallowRef(4),
    });
    toggleGroup('skill');
    await nextTick();
    expect(groups.value[0].expanded).toBe(true);

    keyword.value = 'a';
    await nextTick();
    expect(groups.value[0].expanded).toBe(false);
  });
});
