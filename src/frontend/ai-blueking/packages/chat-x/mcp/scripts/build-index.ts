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

import { glob } from 'glob';
import matter from 'gray-matter';
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { basename, dirname, join, relative, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

interface DocEntry {
  aiSummary: string;
  description: string;
  docFile: string;
  domain?: string;
  kind: string;
  name: string;
  relatedComponents: Array<{ relation: string; slug: string }>;
  slug: string;
}

interface DocIndex {
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

const DOMAIN_MAP: Record<string, { label: string }> = {
  setup: { label: '对话搭建' },
  message: { label: '消息系统' },
  rendering: { label: '内容渲染' },
  input: { label: '输入交互' },
  agent: { label: 'Agent 能力' },
  feedback: { label: '工具与反馈' },
  media: { label: '媒体文件' },
  helper: { label: '辅助能力' },
};

const WIKIS_DIR = resolve(__dirname, '../../wikis');
const GENERATED_DIR = resolve(__dirname, '../../dist/mcp/generated');
const DOCS_DIR = join(GENERATED_DIR, 'docs');

type IndexGroupKey = keyof Omit<DocIndex, 'domains' | 'generatedAt' | 'version'>;

const GLOB_PATTERNS: Array<{ group: IndexGroupKey; pattern: string }> = [
  { pattern: 'components/*/*.md', group: 'components' },
  { pattern: 'composables/*.md', group: 'composables' },
  { pattern: 'directives/*.md', group: 'directives' },
  { pattern: 'plugins/*.md', group: 'plugins' },
  { pattern: 'types/*.md', group: 'types' },
  { pattern: 'utils/*.md', group: 'utils' },
  { pattern: 'edix/*.md', group: 'edix' },
  { pattern: 'i18n/*.md', group: 'i18n' },
  { pattern: 'icons/*.md', group: 'icons' },
  { pattern: 'theme/*.md', group: 'theme' },
];

function buildAiInjectedDoc(
  aiSummary: string,
  related: Array<{ relation: string; slug: string }>,
  cleanedBody: string,
): string {
  const lines: string[] = ['<!-- AI SUMMARY -->', '## 快速了解', '', aiSummary.trim(), ''];

  if (related.length > 0) {
    lines.push('### 关联组件');
    for (const r of related) {
      lines.push(`- **${r.slug}** — ${r.relation}`);
    }
    lines.push('');
  }

  lines.push('---');
  lines.push('<!-- FULL DOC -->');
  lines.push('');
  lines.push(cleanedBody.trim());

  return lines.join('\n');
}

/** Outside fenced blocks: strip script/demo blocks and inline styles; merge 3+ blank lines into 2. */
function cleanMarkdownBody(rawBody: string): string {
  const lines = rawBody.split('\n');
  const out: string[] = [];
  let inFence = false;
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];

    if (/^\s*```/.test(line)) {
      inFence = !inFence;
      out.push(line);
      i++;
      continue;
    }

    if (inFence) {
      out.push(line);
      i++;
      continue;
    }

    if (/<script\b/i.test(line)) {
      if (/<\/script>/i.test(line)) {
        i++;
        continue;
      }
      i++;
      while (i < lines.length && !/<\/script>/i.test(lines[i])) {
        i++;
      }
      if (i < lines.length) i++;
      continue;
    }

    if (/<div[^>]*\bclass="demo"[^>]*>/i.test(line)) {
      let depth = 0;
      const start = i;
      while (i < lines.length) {
        depth += countDivDelta(lines[i]);
        i++;
        if (depth <= 0) break;
      }
      if (i === start) i++;
      continue;
    }

    out.push(stripInlineStyles(line));
    i++;
  }

  return mergeBlankLines(out.join('\n'));
}

function countDivDelta(line: string): number {
  const opens = (line.match(/<div\b/gi) ?? []).length;
  const closes = (line.match(/<\/div>/gi) ?? []).length;
  return opens - closes;
}

function extractHeadingMeta(body: string): { description: string; name: string } {
  const markdown = body;
  const titleMatch = markdown.match(/^#\s+(.+)$/m);
  if (!titleMatch) return { name: '', description: '' };

  const titleLine = titleMatch[1].trim();
  const parts = titleLine.split(/\s+/);
  const name = parts[0];
  const inlineDesc = parts.slice(1).join(' ');

  if (inlineDesc) return { name, description: inlineDesc };

  const afterTitle = markdown.slice(markdown.indexOf(titleMatch[0]) + titleMatch[0].length).trim();
  const firstParagraph = afterTitle.split(/\n\s*\n/)[0]?.trim() ?? '';
  const firstSentence = firstParagraph.split(/[。.！!？?]/)[0]?.trim() ?? '';

  return { name, description: firstSentence.slice(0, 80) };
}

function inferGroupFromRel(rel: string): IndexGroupKey | undefined {
  if (/^components\/[^/]+\/[^/]+\.md$/.test(rel)) return 'components';
  if (/^composables\/[^/]+\.md$/.test(rel)) return 'composables';
  if (/^directives\/[^/]+\.md$/.test(rel)) return 'directives';
  if (/^plugins\/[^/]+\.md$/.test(rel)) return 'plugins';
  if (/^types\/[^/]+\.md$/.test(rel)) return 'types';
  if (/^utils\/[^/]+\.md$/.test(rel)) return 'utils';
  if (/^edix\/[^/]+\.md$/.test(rel)) return 'edix';
  if (/^i18n\/[^/]+\.md$/.test(rel)) return 'i18n';
  if (/^icons\/[^/]+\.md$/.test(rel)) return 'icons';
  if (/^theme\/[^/]+\.md$/.test(rel)) return 'theme';
  return undefined;
}

function inferKindFromGroup(group: IndexGroupKey): string {
  if (group === 'components') return 'component';
  if (group === 'composables') return 'composable';
  if (group === 'directives') return 'directive';
  if (group === 'plugins') return 'plugin';
  if (group === 'types') return 'type';
  if (group === 'utils') return 'util';
  if (group === 'edix') return 'edix';
  if (group === 'i18n') return 'i18n';
  if (group === 'icons') return 'icon';
  if (group === 'theme') return 'theme';
  return group;
}

function initDomains(): Record<string, { components: string[]; label: string }> {
  const out: Record<string, { components: string[]; label: string }> = {};
  for (const [key, { label }] of Object.entries(DOMAIN_MAP)) {
    out[key] = { label, components: [] };
  }
  return out;
}

async function main() {
  mkdirSync(DOCS_DIR, { recursive: true });

  const patterns = GLOB_PATTERNS.map(({ pattern }) => join(WIKIS_DIR, pattern));
  const files = [...new Set((await Promise.all(patterns.map(p => glob(p)))).flat())].sort();

  const domains = initDomains();

  const index: DocIndex = {
    version: '2.0.0',
    generatedAt: new Date().toISOString(),
    domains,
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

  const seenSlugs = new Set<string>();

  for (const file of files) {
    const fileName = basename(file, '.md');
    if (fileName === 'index') continue;

    const rel = relative(WIKIS_DIR, file).replace(/\\/g, '/');
    const group = inferGroupFromRel(rel);
    if (!group) continue;

    const raw = readFileSync(file, 'utf-8');
    const parsed = matter(raw);
    const data = parsed.data as Record<string, unknown>;
    const body = parsed.content;

    const slugDefault = fileName;
    const slug = typeof data.slug === 'string' && data.slug.trim() ? data.slug.trim() : slugDefault;
    if (seenSlugs.has(slug)) {
      console.warn(`Duplicate slug "${slug}", skipping duplicate file: ${file}`);
      continue;
    }
    seenSlugs.add(slug);

    const inferredKind = inferKindFromGroup(group);
    const kind =
      typeof data.kind === 'string' && data.kind.trim()
        ? data.kind.trim()
        : inferredKind;

    const headingMeta = extractHeadingMeta(body);
    const name = typeof data.name === 'string' && data.name.trim() ? data.name.trim() : headingMeta.name || slug;
    const description =
      typeof data.description === 'string' && data.description.trim()
        ? data.description.trim()
        : headingMeta.description || '';
    const aiSummary = typeof data.aiSummary === 'string' && data.aiSummary.trim() ? data.aiSummary.trim() : description;
    const relatedComponents = normalizeRelated(data.relatedComponents);

    let domain: string | undefined;
    if (group === 'components') {
      let d = typeof data.domain === 'string' && data.domain.trim() ? data.domain.trim() : 'helper';
      if (!domains[d]) {
        console.warn(`Unknown domain "${d}" for ${slug}, falling back to helper`);
        d = 'helper';
      }
      domain = d;
      domains[d].components.push(slug);
    }

    const cleanedBody = cleanMarkdownBody(body);
    const docFile = `docs/${slug}.md`;
    const fullDoc = buildAiInjectedDoc(aiSummary, relatedComponents, cleanedBody);

    writeFileSync(join(GENERATED_DIR, docFile), fullDoc);

    const entry: DocEntry = {
      name,
      slug,
      kind,
      description,
      aiSummary,
      relatedComponents,
      docFile,
      ...(domain !== undefined ? { domain } : {}),
    };

    index[group].push(entry);
  }

  writeFileSync(join(GENERATED_DIR, 'index.json'), JSON.stringify(index, null, 2));

  const countKeys: IndexGroupKey[] = [
    'components',
    'composables',
    'types',
    'directives',
    'plugins',
    'utils',
    'edix',
    'i18n',
    'icons',
    'theme',
  ];
  const counts = countKeys.map(k => `${k}: ${index[k].length}`).join(', ');
  console.log(`Generated index v2 (${counts})`);
}

function mergeBlankLines(text: string): string {
  return text.replace(/\n{3,}/g, '\n\n');
}

function normalizeRelated(raw: unknown): Array<{ relation: string; slug: string }> {
  if (!Array.isArray(raw)) return [];
  const out: Array<{ relation: string; slug: string }> = [];
  for (const item of raw) {
    if (item && typeof item === 'object' && 'slug' in item && 'relation' in item) {
      const r = item as { relation: unknown; slug: unknown };
      out.push({ slug: String(r.slug), relation: String(r.relation) });
    }
  }
  return out;
}

function stripInlineStyles(line: string): string {
  return line.replace(/\sstyle="[^"]*"/gi, '');
}

main().catch(console.error);
