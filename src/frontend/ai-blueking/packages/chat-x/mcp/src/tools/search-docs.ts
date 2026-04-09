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

import { getAllEntries, readDocContent } from '../utils/doc-loader.js';

export const searchDocsSchema = {
  query: z.string().describe('搜索关键词，如"消息"、"上传"、"流式"'),
  limit: z.number().default(5).describe('最大返回数量，默认 5'),
};

interface SearchResult {
  aiSummary?: string;
  category: string;
  matches: string[];
  name: string;
  slug: string;
}

export function searchDocs(args: { limit: number; query: string }) {
  const entries = getAllEntries();
  const results: SearchResult[] = [];

  for (const entry of entries) {
    if (results.length >= args.limit) break;

    const content = readDocContent(entry.docFile);
    const fullText = `${entry.name} ${entry.description} ${entry.aiSummary ?? ''} ${(entry.relatedComponents ?? [])
      .map(r => r.relation)
      .join(' ')} ${content}`;

    if (fullText.toLowerCase().includes(args.query.toLowerCase())) {
      results.push({
        name: entry.name,
        slug: entry.slug,
        category: entry.category,
        aiSummary: entry.aiSummary,
        matches: extractMatchContext(content, args.query),
      });
    }
  }

  return {
    content: [
      {
        type: 'text' as const,
        text: JSON.stringify({ query: args.query, resultCount: results.length, results }, null, 2),
      },
    ],
  };
}

function extractMatchContext(content: string, query: string, contextChars = 80): string[] {
  const matches: string[] = [];
  const lowerContent = content.toLowerCase();
  const lowerQuery = query.toLowerCase();
  let pos = 0;

  while (matches.length < 3) {
    const idx = lowerContent.indexOf(lowerQuery, pos);
    if (idx === -1) break;

    const start = Math.max(0, idx - contextChars);
    const end = Math.min(content.length, idx + query.length + contextChars);
    const snippet = (start > 0 ? '...' : '') + content.slice(start, end).trim() + (end < content.length ? '...' : '');
    matches.push(snippet);
    pos = idx + query.length;
  }

  return matches;
}
