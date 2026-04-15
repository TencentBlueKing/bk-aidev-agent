#!/usr/bin/env node

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import matter from 'gray-matter';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const WIKIS_ROOT = path.resolve(__dirname, '../wikis');

const DOMAIN_MAP = {
  'message-container': 'message', 'message-render': 'message',
  'assistant-message': 'message', 'user-message': 'message',
  'reasoning-message': 'message', 'tool-message': 'message',
  'activity-message': 'message', 'info-message': 'message',
  'loading-message': 'message', 'flow-message': 'message',
  'chat-input': 'input', 'ai-selection': 'input',
  'shortcut-render': 'input', 'shortcut-btn': 'input',
  'shortcut-btns': 'input', 'chat-container': 'input',
  'content-render': 'content', 'markdown-content': 'content',
  'code-content': 'content', 'latex-content': 'content',
  'mermaid-content': 'content', 'animation-text': 'content',
  'ai-image': 'media', 'image-preview': 'media',
  'image-preview-group': 'media', 'file-content': 'media',
  'image-content': 'media', 'file-upload-btn': 'media',
  'message-tools': 'tools', 'tool-btn': 'tools',
  'user-feedback': 'tools', 'toolcall-render': 'tools',
  'delete-tool': 'tools',
};

const SCAN_DIRS = [
  { dir: 'components/atomic', category: 'atomic', hasDomain: true },
  { dir: 'components/molecular', category: 'molecular', hasDomain: true },
  { dir: 'composables', category: 'composable', hasDomain: false },
  { dir: 'directives', category: 'directive', hasDomain: false },
  { dir: 'plugins', category: 'plugin', hasDomain: false },
  { dir: 'types', category: 'type', hasDomain: false },
  { dir: 'utils', category: 'util', hasDomain: false },
  { dir: 'edix', category: 'edix', hasDomain: false },
  { dir: 'i18n', category: 'i18n', hasDomain: false },
  { dir: 'icons', category: 'icon', hasDomain: false },
  { dir: 'theme', category: 'theme', hasDomain: false },
];

function extractHeadingAndDescription(content) {
  const lines = content.split('\n');
  let heading = null;
  let headingIndex = -1;

  for (let i = 0; i < lines.length; i++) {
    const match = lines[i].match(/^#\s+(.+)$/);
    if (match) {
      heading = match[1].trim();
      headingIndex = i;
      break;
    }
  }

  let description = '';
  if (headingIndex >= 0) {
    let inScript = false;
    for (let i = headingIndex + 1; i < lines.length; i++) {
      const line = lines[i].trim();
      if (line.match(/^<script[\s>]/i)) { inScript = true; continue; }
      if (inScript) {
        if (line.match(/^<\/script>/i)) inScript = false;
        continue;
      }
      if (!line) continue;
      if (line.startsWith('#') || line.startsWith('```')) break;
      description = line;
      break;
    }
  }

  return { heading, description };
}

function extractName(heading, isComponent) {
  if (!heading) return null;
  if (isComponent) return heading;
  return heading.split(/\s+/)[0];
}

function processFile(filePath, category, hasDomain) {
  const raw = fs.readFileSync(filePath, 'utf-8');
  const parsed = matter(raw);

  if (parsed.data && Object.keys(parsed.data).length > 0) {
    console.log(`  SKIP (has frontmatter): ${filePath}`);
    return false;
  }

  const slug = path.basename(filePath, '.md');
  const isComponent = category === 'atomic' || category === 'molecular';
  const { heading, description } = extractHeadingAndDescription(raw);
  const name = extractName(heading, isComponent) || slug;

  const frontmatter = {
    name,
    slug,
    category,
    description: description || 'TODO: 补充描述',
    aiSummary: 'TODO: 补充 AI 摘要',
    relatedComponents: [],
    sinceVersion: '1.0.0',
  };

  if (hasDomain) {
    frontmatter.domain = DOMAIN_MAP[slug] || 'helper';
  }

  const output = matter.stringify(raw, frontmatter);
  fs.writeFileSync(filePath, output, 'utf-8');
  console.log(`  DONE: ${filePath} → name="${name}", category="${category}"${hasDomain ? `, domain="${frontmatter.domain}"` : ''}`);
  return true;
}

let totalProcessed = 0;
let totalSkipped = 0;

for (const { dir, category, hasDomain } of SCAN_DIRS) {
  const fullDir = path.join(WIKIS_ROOT, dir);
  if (!fs.existsSync(fullDir)) {
    console.log(`\nDIR NOT FOUND: ${dir} — skipping`);
    continue;
  }

  const files = fs.readdirSync(fullDir)
    .filter(f => f.endsWith('.md') && f !== 'index.md')
    .sort();

  if (files.length === 0) {
    console.log(`\nNO FILES: ${dir}`);
    continue;
  }

  console.log(`\n[${category}] Scanning ${dir}/ (${files.length} files)`);

  for (const file of files) {
    const filePath = path.join(fullDir, file);
    const processed = processFile(filePath, category, hasDomain);
    if (processed) totalProcessed++;
    else totalSkipped++;
  }
}

console.log(`\n=== Summary ===`);
console.log(`Processed: ${totalProcessed}`);
console.log(`Skipped:   ${totalSkipped}`);
console.log(`Total:     ${totalProcessed + totalSkipped}`);
