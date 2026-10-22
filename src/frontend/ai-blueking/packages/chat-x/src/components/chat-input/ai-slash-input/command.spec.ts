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

import { DeleteAdjacentTag, InsertMenuTag } from './command';

import type { SelectionSnapshot } from '../../../edix/doc/types';
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

const fileTag = { data: { label: '上传文件接入说明.md', value: 'f1', type: 'artifact' } };

const caret = (column: number, line = 0): SelectionSnapshot => [
  [line, column],
  [line, column],
];

const readDeleteRange = (
  direction: 'backward' | 'forward',
  doc: Parameters<typeof DeleteAdjacentTag>[0],
  selection: SelectionSnapshot,
) => {
  const transaction = DeleteAdjacentTag(doc, selection, direction);
  if (!transaction) {
    return undefined;
  }
  const operation = transaction[0] as { _end: readonly [number, number]; _start: readonly [number, number] };
  return { start: operation._start, end: operation._end };
};

describe('DeleteAdjacentTag', () => {
  it('行首标签后面回删时删掉这个标签', () => {
    expect(readDeleteRange('backward', [[fileTag]], caret(1))).toEqual({
      start: [0, 0],
      end: [0, 1],
    });
  });

  it('标签前面有文字时，只删光标前的标签', () => {
    expect(readDeleteRange('backward', [[{ text: 'hi' }, fileTag]], caret(3))).toEqual({
      start: [0, 2],
      end: [0, 3],
    });
  });

  it('光标紧挨普通文字时不处理', () => {
    expect(readDeleteRange('backward', [[fileTag, { text: ' ' }]], caret(2))).toBeUndefined();
    expect(readDeleteRange('backward', [[{ text: 'hi' }]], caret(1))).toBeUndefined();
  });

  it('行首没有内容时回删不处理', () => {
    expect(readDeleteRange('backward', [[fileTag]], caret(0))).toBeUndefined();
  });

  it('光标在标签前面时，Delete 删掉这个标签', () => {
    expect(readDeleteRange('forward', [[fileTag, { text: 'x' }]], caret(0))).toEqual({
      start: [0, 0],
      end: [0, 1],
    });
  });

  it('有选区时不处理，留给原来的删除', () => {
    const selection: SelectionSnapshot = [
      [0, 0],
      [0, 2],
    ];
    expect(readDeleteRange('backward', [[fileTag, { text: 'x' }]], selection)).toBeUndefined();
  });
});
