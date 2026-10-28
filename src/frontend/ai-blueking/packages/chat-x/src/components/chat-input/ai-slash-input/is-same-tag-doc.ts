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
import type { TagSchema } from '../../../types/input';

type TagNode = TagSchema[number][number];

/** 缺省字段（undefined / null）与空字符串等价：DOM 解析出的标签总会补成 '' */
const isSameTagData = (a: Record<string, unknown>, b: Record<string, unknown>) => {
  const keys = new Set([...Object.keys(a), ...Object.keys(b)]);
  return [...keys].every(key => (a[key] ?? '') === (b[key] ?? ''));
};

const isSameNode = (a: TagNode, b: TagNode) => {
  if (a.type === 'text' && b.type === 'text') {
    return a.text === b.text;
  }
  if (a.type === 'tag' && b.type === 'tag') {
    return isSameTagData(a.data, b.data);
  }
  return false;
};

/**
 * 按节点内容比较两份文档。
 * 不能用序列化后的字符串比较：标签会被拼成 `@名称`，与同名纯文本无法区分。
 */
export const isSameTagDoc = (a: TagSchema, b: TagSchema): boolean =>
  a.length === b.length &&
  a.every((line, i) => {
    const other = b[i]!;
    return line.length === other.length && line.every((node, j) => isSameNode(node, other[j]!));
  });
