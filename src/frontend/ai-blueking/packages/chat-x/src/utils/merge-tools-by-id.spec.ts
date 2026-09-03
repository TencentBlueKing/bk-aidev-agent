/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 */
import { describe, expect, it } from 'vitest';

import { mergeToolsById } from './merge-tools-by-id';

import type { IToolBtn } from '../types';

const BASE: IToolBtn[] = [
  { id: 'copy', name: '复制', description: '复制' },
  { id: 'cite', name: '引用', description: '引用' },
  { id: 'edit', name: '编辑', description: '编辑' },
  { id: 'delete', name: '删除', description: '删除' },
];

describe('mergeToolsById', () => {
  it('extra 为空时返回原列表', () => {
    expect(mergeToolsById(BASE)).toBe(BASE);
    expect(mergeToolsById(BASE, [])).toBe(BASE);
  });

  it('同 id 应字段级覆盖且不新增', () => {
    const result = mergeToolsById(BASE, [{ id: 'copy', description: '复制全文' }]);
    expect(result).toHaveLength(4);
    expect(result.find(tool => tool.id === 'copy')).toEqual({
      id: 'copy',
      name: '复制',
      description: '复制全文',
    });
  });

  it('新 id 应追加到末尾', () => {
    const result = mergeToolsById(BASE, [{ id: 'save', name: '保存', description: '保存' }]);
    expect(result).toHaveLength(5);
    expect(result.at(-1)?.id).toBe('save');
  });

  it('hidden 为 true 的项应被过滤', () => {
    const result = mergeToolsById(BASE, [
      { id: 'edit', hidden: true },
      { id: 'delete', hidden: true },
    ]);
    expect(result.map(tool => tool.id)).toEqual(['copy', 'cite']);
  });
});
