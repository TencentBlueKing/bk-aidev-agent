import { existsSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const binDirs = [
  resolve(__dirname, 'node_modules/.bin'),
  resolve(__dirname, 'node_modules/@blueking/bkui-lint/node_modules/.bin'),
];
const bin = cmd => {
  for (const dir of binDirs) {
    const p = resolve(dir, cmd);
    if (existsSync(p)) return p;
  }
  return cmd;
};

export default {
  'src/frontend/ai-blueking/*.(ts|tsx|js)': [
    `${bin('biome')} check --write --files-ignore-unknown=true --no-errors-on-unmatched --colors=force --max-diagnostics=1000 --diagnostic-level=warn`,
    `${bin('eslint')} --cache --fix`,
  ],
  'src/frontend/ai-blueking/src/**/*.(vue|scss|css|sass)': [`${bin('stylelint')} --cache --fix`],
  'src/frontend/ai-blueking/*.json': [`${bin('biome')} check --write`],
  'src/frontend/ai-blueking/*.{md,yml}': [`${bin('prettier')} --ignore-unknown --write`],
};
