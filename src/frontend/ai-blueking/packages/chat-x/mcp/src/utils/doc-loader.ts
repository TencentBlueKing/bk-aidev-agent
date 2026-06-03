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
import { readFileSync } from 'node:fs';
import { join, resolve } from 'node:path';

export interface DocEntry {
  aiSummary: string;
  description: string;
  docFile: string;
  domain?: string;
  kind: string;
  name: string;
  relatedComponents: Array<{ relation: string; slug: string }>;
  slug: string;
}

export interface DocIndex {
  components: DocEntry[];
  composables: DocEntry[];
  directives: DocEntry[];
  domains: Record<string, { components: string[]; label: string }>;
  edix: DocEntry[];
  generatedAt: string;
  i18n: DocEntry[];
  icons: DocEntry[];
  plugins: DocEntry[];
  theme: DocEntry[];
  types: DocEntry[];
  utils: DocEntry[];
  version: string;
}

const GENERATED_DIR = resolve(__dirname, '../generated');

let cachedIndex: DocIndex | null = null;

export function findBySlug(slug: string): DocEntry | undefined {
  return getAllEntries().find(e => e.slug === slug);
}

export function getAllEntries(): DocEntry[] {
  const index = loadIndex();
  return [
    ...index.components,
    ...index.composables,
    ...index.types,
    ...index.directives,
    ...index.plugins,
    ...index.utils,
    ...index.edix,
    ...index.i18n,
    ...index.icons,
    ...index.theme,
  ];
}

export function loadIndex(): DocIndex {
  if (cachedIndex) return cachedIndex;
  const raw = readFileSync(join(GENERATED_DIR, 'index.json'), 'utf-8');
  cachedIndex = JSON.parse(raw) as DocIndex;
  return cachedIndex;
}

export function readDocContent(docFile: string): string {
  return readFileSync(join(GENERATED_DIR, docFile), 'utf-8');
}
