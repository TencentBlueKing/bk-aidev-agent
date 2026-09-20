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
 *   2. 按「使用方」需要的范围生成（组件全量 + composables/types/utils/directives/plugins/icons/theme），
 *      并产出能力地图索引；
 *   3. 「导入」行以 src/index.ts 的真实导出为准，未导出的组件明确标注为内部实现，
 *      避免使用方抄到跑不通的 import。
 *
 * 运行（在 packages/chat-x 下，依赖 glob / gray-matter 已在 devDependencies）：
 *   node skills/blueking-chat-x/scripts/generate-references.mjs
 */

import { glob } from 'glob';
import matter from 'gray-matter';
import { existsSync, mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { basename, dirname, join, relative, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

// scripts/ -> blueking-chat-x -> skills -> chat-x
const WIKIS_DIR = resolve(__dirname, '../../../wikis');
const REFERENCES_DIR = resolve(__dirname, '../references');
const SRC_DIR = resolve(__dirname, '../../../src');
const SRC_ENTRY = join(SRC_DIR, 'index.ts');

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

/**
 * 生成范围：每条对应 references 下的一个子目录与一个 wikis glob。
 *
 * allowIndex：该组的 `index.md` 是否也要生成。utils / directives / plugins / icons / types
 * 的实际 API 内容就写在 index.md 里（不是导航页），跳过它等于整组能力对使用方不可见。
 * components 与 composables 的 index.md 是纯导航，已由 `_index.md` 承担，继续跳过。
 */
const GROUPS = [
  { key: 'components', label: '组件', pattern: 'components/*/*.md', grouped: true, allowIndex: false },
  { key: 'composables', label: 'Composables 组合式函数', pattern: 'composables/*.md', allowIndex: false },
  { key: 'types', label: '类型定义', pattern: 'types/*.md', allowIndex: true },
  { key: 'utils', label: 'Utils 工具函数', pattern: 'utils/*.md', allowIndex: true },
  { key: 'directives', label: 'Directives 指令', pattern: 'directives/*.md', allowIndex: true },
  { key: 'plugins', label: 'Plugins Markdown 插件', pattern: 'plugins/*.md', allowIndex: true },
  { key: 'icons', label: 'Icons 图标', pattern: 'icons/*.md', allowIndex: true },
  { key: 'theme', label: '主题', pattern: 'theme/*.md', allowIndex: false },
];

const FENCE_RE = /^(\s*)(`{3,}|~{3,})(.*)$/;

/** barrel 导出解析用（正则足够覆盖本项目的 barrel 写法，无需引入 TS parser） */
const NAMED_EXPORT_RE = /export\s+(type\s+)?\{([^}]*)\}(?:\s*from\s*['"]([^'"]+)['"])?/g;
const STAR_EXPORT_RE = /export\s+\*\s+(?:as\s+(\w+)\s+)?from\s*['"]([^'"]+)['"]/g;
const DECL_EXPORT_RE =
  /export\s+(?:declare\s+)?(const|let|var|async\s+function|function|abstract\s+class|class|enum|interface|type)\s+(\w+)/g;
const TYPE_DECL_KEYWORDS = new Set(['interface', 'type']);

/** 生成能力地图索引：组件按能力域分组，其余按组列出。 */
function buildIndexDoc(index) {
  const lines = [];
  lines.push('# @blueking/chat-x 能力地图（自动生成）');
  lines.push('');
  lines.push('> 由 `scripts/generate-references.mjs` 从 `wikis/` 生成，请勿手改。');
  lines.push('> 查某个能力时：先在本索引定位 slug，再读对应 `path` 的 reference 文档。');
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
  if (meta.importSymbols?.length) {
    tags.push(`导入：\`import { ${meta.importSymbols.join(', ')} } from '@blueking/chat-x'\``);
  } else if (meta.internal) {
    // 同名类型是最容易踩的坑：能 import 到，但拿到的不是组件
    if (meta.typeOnly) {
      tags.push('未从包入口导出：内部组件（入口的同名导出是 TS 类型，不是组件）');
    } else {
      tags.push(meta.domainLabel ? '未从包入口导出：内部组件，请通过上层组件使用' : '未从包入口导出：内部实现');
    }
  }
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

    if (/<div[^>]*\bclass=["']?demo["']?[^>]*>/i.test(line)) {
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

/**
 * 把 `A`、`A as B`、`default as B`、`type A as B` 归一到对外暴露的名字，
 * 并标出它是否只是类型导出（决定能不能真的 import 成组件用）。
 */
function parseExportClause(clause) {
  const trimmed = clause.trim();
  if (!trimmed) return null;

  const typeOnly = /^type\s+/.test(trimmed);
  const parts = trimmed.replace(/^type\s+/, '').split(/\s+as\s+/);
  const symbol = (parts[1] ?? parts[0]).trim();

  return /^[A-Za-z_$][\w$]*$/.test(symbol) ? { symbol, typeOnly } : null;
}

/** 解析相对导入说明符到实际文件；兼容 edix 里 `./types.js` 这类带 .js 后缀的 TS 写法。 */
function resolveModuleFile(fromFile, spec) {
  if (!spec.startsWith('.')) return '';
  const base = resolve(dirname(fromFile), spec.replace(/\.(js|ts)$/, ''));
  for (const candidate of [`${base}.ts`, `${base}.tsx`, join(base, 'index.ts')]) {
    if (existsSync(candidate)) return candidate;
  }
  return '';
}

/**
 * 从 src/index.ts 出发递归解析 barrel，得到包入口真实对外暴露的符号集。
 *
 * 存在的意义：文档标题里的组件名与真实导出并不总是一致——既有大小写漂移，也有大量只在库内
 * 使用、压根不导出的内部组件；更隐蔽的是 UserMessage 这类「同名导出其实是 TS 类型而非组件」。
 * 因此值导出与类型导出必须分开收集，只有值导出才能生成「导入」行。
 */
function collectPackageExports() {
  const visited = new Set();
  const valueSymbols = new Set();
  const typeSymbols = new Set();
  const unresolved = [];

  const visit = file => {
    if (!file || visited.has(file)) return;
    visited.add(file);

    let code;
    try {
      code = readFileSync(file, 'utf-8');
    } catch {
      unresolved.push(relative(SRC_DIR, file));
      return;
    }

    for (const match of code.matchAll(NAMED_EXPORT_RE)) {
      const statementIsType = Boolean(match[1]);
      for (const clause of match[2].split(',')) {
        const parsed = parseExportClause(clause);
        if (!parsed) continue;
        const target = statementIsType || parsed.typeOnly ? typeSymbols : valueSymbols;
        target.add(parsed.symbol);
      }
    }

    for (const match of code.matchAll(STAR_EXPORT_RE)) {
      // export * as NS from '...' 暴露的是命名空间本身，不需要继续深入
      if (match[1]) {
        valueSymbols.add(match[1]);
        continue;
      }
      const next = resolveModuleFile(file, match[2]);
      if (next) {
        visit(next);
        continue;
      }
      unresolved.push(`${relative(SRC_DIR, file)} → ${match[2]}`);
    }

    for (const match of code.matchAll(DECL_EXPORT_RE)) {
      const target = TYPE_DECL_KEYWORDS.has(match[1]) ? typeSymbols : valueSymbols;
      target.add(match[2]);
    }
  };

  visit(SRC_ENTRY);
  return { valueSymbols, typeSymbols, unresolved };
}

/**
 * 判定文档对应的导入符号。
 *
 * 依次尝试：frontmatter.exportSymbol 显式声明 → 名称首词精确命中值导出 → 忽略大小写命中
 * （纠正 ToolcallRender / commonErrorContent 这类漂移）→ 前缀命中（useXxx 的
 * Provider / Consumer 成对导出）→ 只命中类型导出（同名类型不是组件）→ 判定为不导出。
 */
function resolveImportHint(name, override, exports) {
  if (typeof override === 'string' && override.trim()) {
    return { symbols: [override.trim()], explicit: true };
  }

  const guess = String(name).trim().split(/\s+/)[0] ?? '';
  // exportSymbol: false 表示文档已确认「就是内部组件」，据此标注且不再告警
  if (override === false) return { symbols: [], missing: guess, similar: [] };
  // 首词不是标识符（如「类型定义」「工具函数」）说明这篇不是单个符号的文档
  if (!/^[A-Za-z][A-Za-z0-9]*$/.test(guess)) return { symbols: [], skip: true };

  const { valueSymbols, typeSymbols } = exports;
  if (valueSymbols.has(guess)) return { symbols: [guess] };

  const lower = guess.toLowerCase();
  const caseHit = [...valueSymbols].find(symbol => symbol.toLowerCase() === lower);
  if (caseHit) return { symbols: [caseHit], drifted: guess };

  const prefixHits = [...valueSymbols].filter(symbol => symbol.startsWith(guess)).sort();
  if (prefixHits.length) return { symbols: prefixHits, derived: guess };

  if ([...typeSymbols].some(symbol => symbol.toLowerCase() === lower)) {
    return { symbols: [], missing: guess, typeOnly: true, similar: [] };
  }

  const similar = [...valueSymbols].filter(symbol => symbol.toLowerCase().includes(lower)).sort();
  return { symbols: [], missing: guess, similar };
}

/** 无 frontmatter 的文档（utils / icons 等 index.md）从首个 H1 与首段推导标题与描述。 */
function extractHeadingMeta(body) {
  const titleMatch = body.match(/^#\s+(.+)$/m);
  if (!titleMatch) return { name: '', description: '' };

  const name = titleMatch[1].trim();
  const after = body.slice(body.indexOf(titleMatch[0]) + titleMatch[0].length);
  // 只取 H1 与下一个标题之间的内容，避免描述串到后面的小节里
  const intro = after.split(/\n#{1,6}\s/)[0] ?? '';
  const paragraph =
    intro
      .split(/\n\s*\n/)
      .map(block => block.trim())
      // 排除代码围栏、HTML、引用、表格与列表；以行内代码（反引号）开头的正文段落要保留
      .find(block => block && !/^(?:```|~~~|[<>|])/.test(block) && !/^(?:[-*+]\s|\d+\.\s)/.test(block)) ?? '';

  const description = paragraph.replace(/\s+/g, ' ').slice(0, 80);
  // 截断可能切在行内代码中间，去掉落单的反引号，避免污染索引里的 markdown
  const balanced =
    (description.match(/`/g) ?? []).length % 2 === 0 ? description : description.replace(/`[^`]*$/, '').trim();

  return { name, description: balanced };
}

function main() {
  // 全量重建，避免删除/重命名后的残留
  rmSync(REFERENCES_DIR, { recursive: true, force: true });
  mkdirSync(REFERENCES_DIR, { recursive: true });

  const { valueSymbols, typeSymbols, unresolved } = collectPackageExports();

  const index = { components: {} }; // components: domainKey -> entries[]
  for (const group of GROUPS) {
    if (!group.grouped) index[group.key] = [];
  }

  const warnings = [];
  let internalCount = 0;
  let typeOnlyCount = 0;

  for (const group of GROUPS) {
    const files = glob.sync(join(WIKIS_DIR, group.pattern)).sort();
    const outDir = join(REFERENCES_DIR, group.key);
    mkdirSync(outDir, { recursive: true });

    const seenSlugs = new Map();

    for (const file of files) {
      const fileName = basename(file, '.md');
      if (fileName === 'index' && !group.allowIndex) continue;

      const rel = relative(WIKIS_DIR, file).replace(/\\/g, '/');
      const parsed = matter(readFileSync(file, 'utf-8'));
      const data = parsed.data ?? {};
      const heading = extractHeadingMeta(parsed.content);

      const slug = typeof data.slug === 'string' && data.slug.trim() ? data.slug.trim() : fileName;
      const name =
        typeof data.name === 'string' && data.name.trim() ? data.name.trim() : heading.name || slug;
      const description =
        typeof data.description === 'string' && data.description.trim()
          ? data.description.trim()
          : heading.description;
      const aiSummary =
        typeof data.aiSummary === 'string' && data.aiSummary.trim() ? data.aiSummary.trim() : description;
      // YAML 里 `sinceVersion: 2.1` 会解析成数字，统一转字符串避免静默丢失
      const since = data.sinceVersion === undefined ? '' : String(data.sinceVersion).trim();
      const related = normalizeRelated(data.relatedComponents);

      // 同一 slug 会写到同一个输出文件，静默覆盖比报错更难查
      if (seenSlugs.has(slug)) {
        warnings.push(`slug 冲突：${rel} 与 ${seenSlugs.get(slug)} 都输出到 ${group.key}/${slug}.md`);
      }
      seenSlugs.set(slug, rel);

      // 组件能力域以目录为准：components/<domain>/<slug>.md
      let domainKey = '';
      let domainLabel = '';
      if (group.grouped) {
        domainKey = rel.split('/')[1] ?? 'helper';
        domainLabel = DOMAIN_LABELS[domainKey] ?? domainKey;
      }

      const hint = resolveImportHint(name, data.exportSymbol, { valueSymbols, typeSymbols });
      if (hint.drifted) {
        warnings.push(`${rel}：文档名 ${hint.drifted} 与真实导出 ${hint.symbols[0]} 不一致，已按真实导出输出`);
      }
      if (hint.missing) {
        internalCount += 1;
        if (hint.typeOnly) typeOnlyCount += 1;
        if (hint.similar.length) {
          warnings.push(
            `${rel}：${hint.missing} 未从包入口导出，但存在相似导出 ${hint.similar.join(' / ')}；` +
              '如确为同一物，请在 frontmatter 补 exportSymbol',
          );
        }
      }

      const cleanedBody = cleanMarkdownBody(parsed.content);
      const doc = buildReferenceDoc(
        {
          name,
          domainLabel,
          importSymbols: hint.symbols,
          internal: Boolean(hint.missing),
          typeOnly: Boolean(hint.typeOnly),
          since,
          aiSummary,
          related,
        },
        cleanedBody,
      );
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
  const counts = [`components ${componentCount}`];
  for (const group of GROUPS) {
    if (!group.grouped) counts.push(`${group.key} ${index[group.key].length}`);
  }
  console.log(`生成完成：${counts.join('、')}`);
  console.log(
    `包入口值导出 ${valueSymbols.size} 个、类型导出 ${typeSymbols.size} 个；` +
      `标注为内部实现的文档 ${internalCount} 篇（其中 ${typeOnlyCount} 篇存在同名类型导出）`,
  );

  for (const item of unresolved) {
    console.warn(`[warn] barrel 未能解析：${item}`);
  }
  for (const warning of warnings) {
    console.warn(`[warn] ${warning}`);
  }
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
