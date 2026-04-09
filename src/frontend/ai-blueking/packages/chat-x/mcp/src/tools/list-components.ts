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

import { type DocEntry, loadIndex } from '../utils/doc-loader.js';

export const listComponentsSchema = {
  category: z
    .enum([
      'all',
      'atomic',
      'molecular',
      'composable',
      'directive',
      'plugin',
      'type',
      'util',
      'edix',
      'i18n',
      'icon',
      'theme',
    ])
    .default('all')
    .describe('过滤分类：all 返回全部，或按具体分类筛选'),
  domain: z
    .enum(['all', 'message', 'input', 'content', 'media', 'tools', 'helper'])
    .default('all')
    .describe('按功能域过滤（仅对组件生效，其他分类不受影响）'),
};

type ListGroupKey =
  | 'components'
  | 'composables'
  | 'directives'
  | 'edix'
  | 'i18n'
  | 'icons'
  | 'plugins'
  | 'theme'
  | 'types'
  | 'utils';

export function listComponents(args: { category: string; domain: string }) {
  const index = loadIndex();
  const { category, domain } = args;

  const result: Record<ListGroupKey, ReturnType<typeof mapEntry>[]> = {
    components: [],
    composables: [],
    types: [],
    directives: [],
    plugins: [],
    utils: [],
    edix: [],
    i18n: [],
    icons: [],
    theme: [],
  };

  if (shouldIncludeGroup('components', category)) {
    result.components = filterComponentEntries(index.components, category, domain).map(mapEntry);
  }
  if (shouldIncludeGroup('composables', category)) {
    result.composables = index.composables.map(mapEntry);
  }
  if (shouldIncludeGroup('types', category)) {
    result.types = index.types.map(mapEntry);
  }
  if (shouldIncludeGroup('directives', category)) {
    result.directives = index.directives.map(mapEntry);
  }
  if (shouldIncludeGroup('plugins', category)) {
    result.plugins = index.plugins.map(mapEntry);
  }
  if (shouldIncludeGroup('utils', category)) {
    result.utils = index.utils.map(mapEntry);
  }
  if (shouldIncludeGroup('edix', category)) {
    result.edix = index.edix.map(mapEntry);
  }
  if (shouldIncludeGroup('i18n', category)) {
    result.i18n = index.i18n.map(mapEntry);
  }
  if (shouldIncludeGroup('icons', category)) {
    result.icons = index.icons.map(mapEntry);
  }
  if (shouldIncludeGroup('theme', category)) {
    result.theme = index.theme.map(mapEntry);
  }

  return {
    content: [
      {
        type: 'text' as const,
        text: JSON.stringify(result, null, 2),
      },
    ],
  };
}

function filterComponentEntries(entries: DocEntry[], category: string, domain: string): DocEntry[] {
  let result = entries;
  if (category === 'atomic') result = result.filter(e => e.category === 'atomic');
  else if (category === 'molecular') result = result.filter(e => e.category === 'molecular');
  if (domain !== 'all') result = result.filter(e => (e.domain ?? 'helper') === domain);
  return result;
}

function mapEntry(entry: DocEntry) {
  return {
    name: entry.name,
    slug: entry.slug,
    category: entry.category,
    description: entry.description,
    aiSummary: entry.aiSummary,
    ...(entry.domain !== undefined ? { domain: entry.domain } : {}),
  };
}

function shouldIncludeGroup(groupKey: ListGroupKey, category: string): boolean {
  if (category === 'all') return true;
  const single: Record<string, ListGroupKey> = {
    atomic: 'components',
    molecular: 'components',
    composable: 'composables',
    directive: 'directives',
    plugin: 'plugins',
    type: 'types',
    util: 'utils',
    edix: 'edix',
    i18n: 'i18n',
    icon: 'icons',
    theme: 'theme',
  };
  return single[category] === groupKey;
}
