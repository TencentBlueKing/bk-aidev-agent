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
import { z } from 'zod';

import { findBySlug, readDocContent } from '../utils/doc-loader.js';

export const getComponentDocSchema = {
  slug: z
    .string()
    .describe(
      '文档 slug（如 chat-container、use-message-group、overflow-tips），可通过 list_components 获取任意已索引条目',
    ),
};

export function getComponentDoc(args: { slug: string }) {
  const entry = findBySlug(args.slug);
  if (!entry) {
    return {
      content: [
        {
          type: 'text' as const,
          text: `未找到 slug 为 "${args.slug}" 的文档。请先调用 list_components 查看可用组件。`,
        },
      ],
      isError: true,
    };
  }

  const content = readDocContent(entry.docFile);
  return {
    content: [
      {
        type: 'text' as const,
        text: content,
      },
    ],
  };
}
