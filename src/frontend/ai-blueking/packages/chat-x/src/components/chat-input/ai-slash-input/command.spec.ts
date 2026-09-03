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
import { defineComponent } from 'vue';

import { describe, expect, it } from 'vitest';

import { InsertMenuTag } from './command';

import type { IInputMenuItem } from '../../../types/input-menu';

const readInsertedData = (item: IInputMenuItem) => {
  const transaction = InsertMenuTag([], [], [0, 3], item);
  const operation = transaction[0] as {
    _fragment: Array<Array<{ data: Record<string, string> }>>;
    _pos: [number, number];
  };
  return { data: operation._fragment[0][0].data, pos: operation._pos };
};

describe('InsertMenuTag', () => {
  it('value 取条目 id，保证 skill 序列化成 /id 而不是名称', () => {
    const { data, pos } = readInsertedData({
      id: 'code-review',
      type: 'skill',
      name: 'Code Review',
      description: '审查代码',
      icon: 'https://example.com/skill.png',
    });

    expect(pos).toEqual([0, 3]);
    expect(data).toEqual({
      label: 'Code Review',
      value: 'code-review',
      type: 'skill',
      icon: 'https://example.com/skill.png',
      description: '审查代码',
    });
  });

  it('组件形式的图标无法写入 DOM 属性，存为空字符串交给类型默认图标兜底', () => {
    const { data } = readInsertedData({
      id: 't1',
      type: 'tool',
      name: '工具',
      icon: defineComponent({ name: 'CustomIcon' }),
    });

    expect(data.icon).toBe('');
    expect(data.description).toBe('');
  });
});
