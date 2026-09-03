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

import { tagNodeToMessageString, tagSchemaToMessageString } from './constants';

import type { VoidNode } from '../../../edix/doc/types';
import type { TagSchema } from '../../../types/input';

describe('tagNodeToMessageString', () => {
  it('skill 序列化为 /value，供后端识别技能编码', () => {
    const node = { data: { type: 'skill', value: 'code-review', label: 'Code Review' } } as unknown as VoidNode;
    expect(tagNodeToMessageString(node)).toBe('/code-review');
  });

  it('其它类型序列化为 @label', () => {
    const node = { data: { type: 'tool', value: 't1', label: 'knowlege-base' } } as unknown as VoidNode;
    expect(tagNodeToMessageString(node)).toBe('@knowlege-base');
  });
});

describe('tagSchemaToMessageString', () => {
  it('把文档里的文本与标签拼成发送用的纯文本', () => {
    const doc = [
      [
        { type: 'text', text: '帮我查一下 ' },
        { type: 'tag', data: { type: 'knowledgebase', value: 'kb_01', label: '知识库01' } },
        { type: 'text', text: ' 和 ' },
        { type: 'tag', data: { type: 'skill', value: 'code-review', label: 'Code Review' } },
      ],
    ] as TagSchema;

    expect(tagSchemaToMessageString(doc)).toBe('帮我查一下 @知识库01 和 /code-review');
  });
});
