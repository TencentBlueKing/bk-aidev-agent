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
/** biome-ignore-all lint/suspicious/noAssignInExpressions: <explanation> */

/**
 * 从 wikis 生成 blueking-chat-x skill 的 references。
 *
 * 设计目标：把面向人类阅读的 VitePress 文档（含大量 demo 脚本/演示 HTML）清洗成
 * LLM 友好的「使用方视角」精简文档——剥离演示噪音、保留完整 API 表格与示例代码。
 *
 * 与 mcp/scripts/build-index.ts 共享清洗思路，但本脚本：
 *   1. 强化代码围栏处理：正确识别 ````vue 内嵌套 ``` 的情况，避免误删示例里的 <script setup>；
 *   2. 按「使用方」需要的范围生成（组件全量 + composables/types/theme），并产出能力地图索引。
 *
 * 运行（在 packages/chat-x 下，依赖 glob / gray-matter 已在 devDependencies）：
 *   node skills/blueking-chat-x/scripts/generate-references.mjs
 */

import { glob } from 'glob';
import matter from 'gray-matter';
import { mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { basename, dirname, join, relative, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

// scripts/ -> blueking-chat-x -> skills -> chat-x
const WIKIS_DIR = resolve(__dirname, '../../../wikis');
const REFERENCES_DIR = resolve(__dirname, '../references');

/** 组件能力域：以 wikis/components/<domain>/ 目录为准，避免依赖 frontmatter.domain 出现的拼写漂移。 */
const DOMAIN_LABELS = {
  setup: '对话搭建',
  message: '消息系统',
  rendering: '内容渲染',
  medias: '媒体文件',
  input: '输入交互',
  agent: 'Agent 能力',
  feedback: '工具与反馈',
  helper: '辅助能力',
};

/** 生成范围：每条对应 references 下的一个子目录与一个 wikis glob。 */
const GROUPS = [
  { key: 'components', label: '组件', pattern: 'components/*/*.md', grouped: true },
  { key: 'composables', label: 'Composables 组合式函数', pattern: 'composables/*.md', grouped: false },
  { key: 'types', label: '类型定义', pattern: 'types/*.md', grouped: false },
  { key: 'theme', label: '主题', pattern: 'theme/*.md', grouped: false },
];

const FENCE_RE = /^(\s*)(`{3,}|~{3,})(.*)$/;

/** 生成能力地图索引：组件按能力域分组，其余按组列出。 */
function buildIndexDoc(index) {
  const lines = [];
  lines.push('# @blueking/chat-x 能力地图（自动生成）');
  lines.push('');
  lines.push('> 由 `scripts/generate-references.mjs` 从 `wikis/` 生成，请勿手改。');
  lines.push('> 查某个能力时：先在本索引定位 slug，再读对应 `path` 的 reference 文档。');
  lines.push('');
  lines.push(`> 生成时间：${index.generatedAt}`);
  lines.push('');

  lines.push('## 组件（按能力域）');
  lines.push('');
  for (const domainKey of Object.keys(DOMAIN_LABELS)) {
    const list = index.components[domainKey];
    if (!list?.length) continue;
    lines.push(`### ${DOMAIN_LABELS[domainKey]}`);
    lines.push('');
    for (const entry of list.sort((a, b) => a.slug.localeCompare(b.slug))) {
      lines.push(`- **${entry.name}** — ${entry.description} → \`${entry.path}\``);
    }
    lines.push('');
  }

  for (const group of GROUPS) {
    if (group.grouped) continue;
    const list = index[group.key];
    if (!list?.length) continue;
    lines.push(`## ${group.label}`);
    lines.push('');
    for (const entry of list.sort((a, b) => a.slug.localeCompare(b.slug))) {
      lines.push(`- **${entry.name}** — ${entry.description} → \`${entry.path}\``);
    }
    lines.push('');
  }

  return lines.join('\n');
}

/** 组装单个 reference 文档：精简元信息头 + 关联组件 + 清洗后的完整正文。 */
function buildReferenceDoc(meta, cleanedBody) {
  const lines = [];
  lines.push(`# ${meta.name}`);
  lines.push('');

  const tags = [];
  if (meta.domainLabel) tags.push(`能力域：${meta.domainLabel}`);
  if (meta.symbol) tags.push(`导入：\`import { ${meta.symbol} } from '@blueking/chat-x'\``);
  if (meta.since) tags.push(`since ${meta.since}`);
  if (tags.length) {
    lines.push(`> ${tags.join(' ｜ ')}`);
    lines.push('');
  }

  if (meta.aiSummary) {
    lines.push(meta.aiSummary.trim());
    lines.push('');
  }

  if (meta.related.length) {
    lines.push(`**关联**：${meta.related.map(r => (r.relation ? `${r.slug}（${r.relation}）` : r.slug)).join('、')}`);
    lines.push('');
  }

  lines.push('---');
  lines.push('');
  lines.push(cleanedBody);
  lines.push('');

  return lines.join('\n');
}

/**
 * 清洗 wiki 正文：剥离 <script> demo 块、<div class="demo"> 演示块、内联 style，
 * 并合并多余空行。代码围栏内的内容原样保留。
 *
 * 围栏处理采用 CommonMark 规则：记录开围栏的字符与长度，只有「同字符、长度 >= 开围栏、
 * 且其后无信息串」的行才视为闭围栏。这样 ````vue 内的 ``` 会被当作内容，
 * 不会误把示例里的 <script setup> 当成需剥离的 VitePress demo。
 */
function cleanMarkdownBody(rawBody) {
  const lines = rawBody.split('\n');
  const out = [];
  let fence = null; // { char, len }
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];
    const fenceMatch = line.match(FENCE_RE);

    if (fenceMatch) {
      const marker = fenceMatch[2];
      const char = marker[0];
      const len = marker.length;
      const rest = fenceMatch[3].trim();

      if (!fence) {
        fence = { char, len };
      } else if (char === fence.char && len >= fence.len && rest === '') {
        fence = null;
      }
      out.push(line);
      i++;
      continue;
    }

    if (fence) {
      out.push(line);
      i++;
      continue;
    }

    // 以下分支仅在围栏外生效——剥离 VitePress 演示噪音
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

  return mergeBlankLines(out.join('\n')).trim();
}

function countDivDelta(line) {
  const opens = (line.match(/<div\b/gi) ?? []).length;
  const closes = (line.match(/<\/div>/gi) ?? []).length;
  return opens - closes;
}

/** frontmatter.name 形如 "ChatContainer 聊天容器"，首段若是合法标识符则视为导入符号。 */
function extractSymbol(name) {
  const first = String(name).trim().split(/\s+/)[0] ?? '';
  return /^[A-Za-z][A-Za-z0-9]*$/.test(first) ? first : '';
}

function main() {
  // 全量重建，避免删除/重命名后的残留
  rmSync(REFERENCES_DIR, { recursive: true, force: true });
  mkdirSync(REFERENCES_DIR, { recursive: true });

  const index = {
    generatedAt: new Date().toISOString(),
    components: {}, // domainKey -> entries[]
    composables: [],
    types: [],
    theme: [],
  };

  for (const group of GROUPS) {
    const files = glob.sync(join(WIKIS_DIR, group.pattern)).sort();
    const outDir = join(REFERENCES_DIR, group.key);
    mkdirSync(outDir, { recursive: true });

    for (const file of files) {
      const fileName = basename(file, '.md');
      if (fileName === 'index') continue;

      const rel = relative(WIKIS_DIR, file).replace(/\\/g, '/');
      const parsed = matter(readFileSync(file, 'utf-8'));
      const data = parsed.data ?? {};

      const slug = typeof data.slug === 'string' && data.slug.trim() ? data.slug.trim() : fileName;
      const name = typeof data.name === 'string' && data.name.trim() ? data.name.trim() : slug;
      const description = typeof data.description === 'string' ? data.description.trim() : '';
      const aiSummary =
        typeof data.aiSummary === 'string' && data.aiSummary.trim() ? data.aiSummary.trim() : description;
      const since = typeof data.sinceVersion === 'string' ? data.sinceVersion.trim() : '';
      const related = normalizeRelated(data.relatedComponents);
      const symbol = extractSymbol(name);

      // 组件能力域以目录为准：components/<domain>/<slug>.md
      let domainKey = '';
      let domainLabel = '';
      if (group.grouped) {
        domainKey = rel.split('/')[1] ?? 'helper';
        domainLabel = DOMAIN_LABELS[domainKey] ?? domainKey;
      }

      const cleanedBody = cleanMarkdownBody(parsed.content);
      const doc = buildReferenceDoc({ name, domainLabel, symbol, since, aiSummary, related }, cleanedBody);
      writeFileSync(join(outDir, `${slug}.md`), doc);

      const entry = { name, slug, description: description || aiSummary, path: `${group.key}/${slug}.md` };
      if (group.grouped) {
        (index.components[domainKey] ??= []).push({ ...entry, domainLabel });
      } else {
        index[group.key].push(entry);
      }
    }
  }

  writeFileSync(join(REFERENCES_DIR, '_index.md'), buildIndexDoc(index));

  const componentCount = Object.values(index.components).reduce((acc, list) => acc + list.length, 0);
  console.log(
    `生成完成：components ${componentCount}、composables ${index.composables.length}、` +
      `types ${index.types.length}、theme ${index.theme.length}`,
  );
}

function mergeBlankLines(text) {
  return text.replace(/\n{3,}/g, '\n\n');
}

function normalizeRelated(raw) {
  if (!Array.isArray(raw)) return [];
  return raw
    .filter(item => item && typeof item === 'object' && 'slug' in item)
    .map(item => ({ slug: String(item.slug), relation: 'relation' in item ? String(item.relation) : '' }));
}

function stripInlineStyles(line) {
  return line.replace(/\sstyle="[^"]*"/gi, '');
}

main();
