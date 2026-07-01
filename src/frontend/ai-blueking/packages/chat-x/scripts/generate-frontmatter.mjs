#!/usr/bin/env node

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import matter from 'gray-matter';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const WIKIS_ROOT = path.resolve(__dirname, '../wikis');

const DOMAIN_MAP = {
  'chat-container': 'setup', 'message-container': 'setup',
  'message-render': 'message',
  'assistant-message': 'message', 'user-message': 'message',
  'reasoning-message': 'message', 'tool-message': 'message',
  'activity-message': 'message', 'info-message': 'message',
  'loading-message': 'message', 'flow-message': 'message',
  'interrupt-message': 'agent', 'tool-approval-card': 'agent',
  'user-question-card': 'agent', 'user-question-answered-card': 'agent',
  'user-question-option': 'agent', 'toolcall-render': 'agent',
  'execution-summary': 'agent', 'flow-agent-content': 'agent',
  'flow-agent-node-detail': 'agent', 'detail-section': 'agent',
  'simple-table': 'agent', 'knowledge-rag-content': 'agent',
  'reference-doc-content': 'agent',
  'chat-input': 'input', 'ai-selection': 'input',
  'shortcut-render': 'input', 'shortcut-btn': 'input',
  'shortcut-btns': 'input', 'file-upload-btn': 'input',
  'selection-footer': 'input', 'ai-slash-input': 'input',
  'ai-slash-editor': 'input', 'ai-slash-menu': 'input',
  'ai-prompt-list': 'input', 'input-attachment': 'input',
  'input-info-alert': 'input',
  'content-render': 'rendering', 'markdown-content': 'rendering',
  'code-content': 'rendering', 'latex-content': 'rendering',
  'mermaid-content': 'rendering', 'animation-text': 'rendering',
  'text-content': 'rendering', 'cite-content': 'rendering',
  'reference-content': 'rendering', 'key-value-content': 'rendering',
  'common-error-content': 'rendering', 'desc-panel': 'rendering',
  'ai-image': 'media', 'image-preview': 'media',
  'image-preview-group': 'media', 'file-content': 'media',
  'image-content': 'media', 'preview-toolbar': 'media',
  'message-tools': 'feedback', 'tool-btn': 'feedback',
  'user-feedback': 'feedback', 'delete-tool': 'feedback',
  'scroll-btn': 'feedback',
  'activity-layout': 'helper', 'ai-loading': 'helper',
  'message-loading': 'helper', 'highlight-keyword': 'helper',
  'vnode-renderer': 'helper', 'questions-container': 'helper',
  'selection-question': 'helper',
};

const SCAN_DIRS = [
  { dir: 'components/setup', kind: 'component', hasDomain: true },
  { dir: 'components/message', kind: 'component', hasDomain: true },
  { dir: 'components/rendering', kind: 'component', hasDomain: true },
  { dir: 'components/input', kind: 'component', hasDomain: true },
  { dir: 'components/agent', kind: 'component', hasDomain: true },
  { dir: 'components/feedback', kind: 'component', hasDomain: true },
  { dir: 'components/media', kind: 'component', hasDomain: true },
  { dir: 'components/helper', kind: 'component', hasDomain: true },
  { dir: 'composables', kind: 'composable', hasDomain: false },
  { dir: 'directives', kind: 'directive', hasDomain: false },
  { dir: 'plugins', kind: 'plugin', hasDomain: false },
  { dir: 'types', kind: 'type', hasDomain: false },
  { dir: 'utils', kind: 'util', hasDomain: false },
  { dir: 'edix', kind: 'edix', hasDomain: false },
  { dir: 'i18n', kind: 'i18n', hasDomain: false },
  { dir: 'icons', kind: 'icon', hasDomain: false },
  { dir: 'theme', kind: 'theme', hasDomain: false },
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

function processFile(filePath, kind, hasDomain) {
  const raw = fs.readFileSync(filePath, 'utf-8');
  const parsed = matter(raw);

  if (parsed.data && Object.keys(parsed.data).length > 0) {
    console.log(`  SKIP (has frontmatter): ${filePath}`);
    return false;
  }

  const slug = path.basename(filePath, '.md');
  const isComponent = kind === 'component';
  const { heading, description } = extractHeadingAndDescription(raw);
  const name = extractName(heading, isComponent) || slug;

  const frontmatter = {
    name,
    slug,
    kind,
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
  console.log(`  DONE: ${filePath} → name="${name}", kind="${kind}"${hasDomain ? `, domain="${frontmatter.domain}"` : ''}`);
  return true;
}

let totalProcessed = 0;
let totalSkipped = 0;

for (const { dir, kind, hasDomain } of SCAN_DIRS) {
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

  console.log(`\n[${kind}] Scanning ${dir}/ (${files.length} files)`);

  for (const file of files) {
    const filePath = path.join(fullDir, file);
    const processed = processFile(filePath, kind, hasDomain);
    if (processed) totalProcessed++;
    else totalSkipped++;
  }
}

console.log(`\n=== Summary ===`);
console.log(`Processed: ${totalProcessed}`);
console.log(`Skipped:   ${totalSkipped}`);
console.log(`Total:     ${totalProcessed + totalSkipped}`);
