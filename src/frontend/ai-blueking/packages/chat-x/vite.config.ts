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
import vue from '@vitejs/plugin-vue';
import fs from 'node:fs';
import path from 'node:path';
import { defineConfig } from 'vite';
import { analyzer, unstableRolldownAdapter } from 'vite-bundle-analyzer';

import { vitePluginHighlightGithubDarkScope } from './vite-plugins/highlight-github-dark-scope';

const resolve = (dir: string) => path.resolve(__dirname, dir);
const packageJson = JSON.parse(fs.readFileSync(resolve('./package.json'), 'utf-8'));
const externals = Object.keys(packageJson.dependencies || {});
const BKUI_PREFIX = 'bk';
/**
 * 依赖默认 external，但 highlight.js 的样式需打入包内，
 * 以便走 `vitePluginHighlightGithubDarkScope` 做选择器收敛并合并进 dist/index.css。
 */
const isExternal = (id: string) => {
  const normalized = id.split('?')[0];
  if (normalized.includes('highlight.js/styles/') && normalized.endsWith('.css')) {
    return false;
  }
  return externals.some(dep => id === dep || id.startsWith(`${dep}/`));
};
// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  return {
    plugins: [
      vitePluginHighlightGithubDarkScope(),
      vue(),
      mode === 'preview' ? unstableRolldownAdapter(analyzer()) : undefined,
    ].filter(Boolean),
    root: resolve('./playground'),
    css: {
      preprocessorOptions: {
        scss: {
          additionalData: `$bk-prefix: ${BKUI_PREFIX};`,
        },
      },
    },
    build: {
      emptyOutDir: true,
      target: 'es2015',
      outDir: resolve('./dist'),
      sourcemap: mode === 'development' ? 'inline' : 'hidden',
      lib: {
        entry: resolve('./src/index.ts'),
        name: 'BkUIChatX',
        fileName: () => 'index.js',
        formats: ['es'],
        cssFileName: 'index',
      },
      minify: mode === 'production',
      rolldownOptions: {
        external: isExternal,
      },
    },
    server: {
      allowedHosts: ['localhost', '127.0.0.1', 'appdev.woa.com'],
    },
  };
});
