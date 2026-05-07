import { execSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(__dirname, '..');

function run(cmd) {
  console.log(`> ${cmd}`);
  execSync(cmd, { cwd: root, stdio: 'inherit' });
}

console.log('=== Building npm package for ai-blueking-docs ===\n');

// Step 1: VitePress build with placeholder base
console.log('[1/4] Building VitePress with __DOCS_BASE__/ placeholder...');
run('pnpm build');

// Step 2: Reorganize dist/ → dist/static/
console.log('[2/4] Reorganizing dist/ for npm package structure...');
const distDir = path.join(root, 'dist');
const tmpDir = path.join(root, 'dist-vitepress-tmp');

// Rename dist → dist-vitepress-tmp
fs.renameSync(distDir, tmpDir);
fs.mkdirSync(distDir, { recursive: true });
// Move dist-vitepress-tmp → dist/static
fs.renameSync(tmpDir, path.join(distDir, 'static'));

// Step 3: Compile middleware with esbuild
console.log('[3/4] Compiling middleware with esbuild...');
const esbuildCommon = [
  '--bundle',
  '--platform=node',
  '--external:koa',
  '--external:@koa/router',
  '--external:koa-send',
  '--external:node:fs',
  '--external:node:path',
].join(' ');
run(`esbuild src/index.ts ${esbuildCommon} --format=cjs --outfile=dist/index.cjs`);
run(`esbuild src/index.ts ${esbuildCommon} --format=esm --outfile=dist/index.mjs`);

// Step 4: Generate .d.ts
console.log('[4/4] Generating type declarations...');
try {
  run('tsc --emitDeclarationOnly --declaration --outDir dist');
} catch {
  console.log('  (tsc declaration generation failed, skipping)');
}

console.log('\n=== npm build complete ===');
console.log(`Output: ${distDir}`);
console.log('  dist/index.cjs   - CommonJS entry');
console.log('  dist/index.mjs   - ESM entry');
console.log('  dist/index.d.ts  - Type declarations');
console.log('  dist/static/     - VitePress static files');
