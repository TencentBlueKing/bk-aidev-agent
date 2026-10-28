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

import { tagSchema } from './constants';
import { isSameTagDoc } from './is-same-tag-doc';

import type { TagSchema } from '../../../types/input';

const hostDoc = (description = '上海机房'): TagSchema => [
  [
    { type: 'text', text: '帮我分析 ' },
    {
      type: 'tag',
      data: { type: 'hostxxx', value: 'host-001', label: '生产服务器', icon: '', description },
    },
  ],
];

describe('isSameTagDoc', () => {
  it('内容相同的新对象视为相同', () => {
    expect(isSameTagDoc(hostDoc(), hostDoc())).toBe(true);
  });

  it('经过编辑器 schema 往返后的文档与原文档相同', () => {
    const doc = hostDoc();
    expect(isSameTagDoc(tagSchema.js(tagSchema.doc(doc)), doc)).toBe(true);
  });

  it('纯文本 @名称 与同名标签不同', () => {
    const plain: TagSchema = [[{ type: 'text', text: '帮我分析 @生产服务器' }]];
    expect(isSameTagDoc(plain, hostDoc())).toBe(false);
  });

  it('标签任一字段变化都视为不同', () => {
    expect(isSameTagDoc(hostDoc('北京机房'), hostDoc())).toBe(false);
  });

  it('缺省的 icon / description 与空字符串等价', () => {
    const sparse = [
      [{ type: 'tag', data: { type: 'hostxxx', value: 'host-001', label: '生产服务器' } }],
    ] as unknown as TagSchema;
    const filled: TagSchema = [
      [{ type: 'tag', data: { type: 'hostxxx', value: 'host-001', label: '生产服务器', icon: '', description: '' } }],
    ];
    expect(isSameTagDoc(sparse, filled)).toBe(true);
  });

  it('行数或节点数不同视为不同', () => {
    expect(isSameTagDoc([[]], [[], []])).toBe(false);
    expect(isSameTagDoc([[{ type: 'text', text: 'a' }]], [[]])).toBe(false);
  });
});
