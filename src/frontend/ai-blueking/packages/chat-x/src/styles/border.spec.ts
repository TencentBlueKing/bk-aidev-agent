import { createRequire } from 'node:module';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import * as sass from 'sass-embedded';
import { describe, expect, it } from 'vitest';

const stylesDir = path.dirname(fileURLToPath(import.meta.url));
const require = createRequire(import.meta.url);

async function minifyCss(css: string): Promise<string> {
  const lightningcssPath = require.resolve('lightningcss', {
    paths: [path.dirname(require.resolve('vite/package.json'))],
  });
  const { transform } = await import(lightningcssPath);
  const result = transform({
    filename: 'border.css',
    code: Buffer.from(css),
    minify: true,
  });
  return result.code.toString();
}

describe('linear-gradient-border mixin', () => {
  it('经 lightningcss 压缩后仍保留 mask 挖空，避免渐变铺满整块', async () => {
    const compiled = sass.compileString(
      `@use 'border' as border;
       .t::before { @include border.linear-gradient-border(180deg, #6cbaff, #3a84ff); }`,
      { loadPaths: [stylesDir], syntax: 'scss' },
    ).css;

    const minified = await minifyCss(compiled);

    expect(minified).toMatch(/mask-composite:\s*exclude/);

    // mask / -webkit-mask 简写会重置 composite；若仍输出简写，composite 必须写在其后
    const webkitShorthandLast = minified.lastIndexOf('-webkit-mask:');
    if (webkitShorthandLast !== -1) {
      expect(minified.slice(webkitShorthandLast)).toMatch(
        /-webkit-mask-composite:\s*xor|mask-composite:\s*exclude/,
      );
    }
  });
});
