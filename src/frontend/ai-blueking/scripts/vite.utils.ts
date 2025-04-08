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
import { readFileSync } from 'fs';
import { resolve } from 'path';
import { LibraryFormats, type UserConfig, loadEnv, mergeConfig } from 'vite';
import cssInjectedByJsPlugin from 'vite-plugin-css-injected-by-js';

interface PackageJSON {
  name: string;
  private?: boolean;
  version?: string;
}
const LessCodeGlobalVar = 'lesscodeCustomComponentLibrary';
const env = loadEnv(process.env.NODE_ENV || 'production', process.cwd(), '');

export enum VueVersion {
  Vue2 = 'vue2',
  Vue3 = 'vue3',
}

export function getPackageInfo<T extends PackageJSON>(relativePth = '../package.json') {
  const pkgPath = resolve(__dirname, relativePth);
  const pkg = JSON.parse(readFileSync(pkgPath, 'utf-8')) as T;
  if (pkg.private) {
    throw new Error(`Package ${pkg.name} is private`);
  }

  return { pkg, pkgPath };
}
function getPrefix(version: VueVersion, formats: LibraryFormats[]) {
  const isVue3 = version === VueVersion.Vue3;
  const isIIFE = formats.includes('iife');
  return isVue3 && !isIIFE ? 'bk' : env.BKUI_PREFIX;
}

function getExternal(formats: LibraryFormats[], version: VueVersion) {
  return (id: string) => {
    const isVue3 = version === VueVersion.Vue3;
    if (formats.includes('iife')) {
      return isVue3 && /^vue$/.test(id);
    }
    if (
      /^dayjs[/]?\w*/.test(id) ||
      (isVue3 && (/^bkui-vue/.test(id) || /^vue$/.test(id))) ||
      (!isVue3 && /^@blueking\/bkui-library/.test(id)) ||
      /^highlight.js/.test(id) ||
      /^markdown-it/.test(id) ||
      /^markdown-it-code-copy/.test(id)
    ) {
      return true;
    }
    return false;
  };
}

export const createCommonConfig = (prefix = env.BKUI_PREFIX, isIIFE = false): UserConfig => ({
  css: {
    preprocessorOptions: {
      less: {
        javascriptEnabled: true,
        modifyVars: { 'bk-prefix': prefix },
      },
      scss: {
        additionalData: `$bk-prefix: ${prefix};`,
      },
    },
  },
  define: {
    BKUI_PREFIX: JSON.stringify(prefix),
    'process.env.NODE_ENV': JSON.stringify(env.NODE_ENV),
    'process.env.BK_API_URL_TMPL': JSON.stringify(env.BK_API_URL_TMPL),
    'process.env.BK_API_GATEWAY_NAME': JSON.stringify(env.BK_API_GATEWAY_NAME),
    'process.env.BK_LOGIN_URL': JSON.stringify(env.BK_LOGIN_URL),
  },
  mode: env.NODE_ENV,
  plugins: [vue(), isIIFE ? cssInjectedByJsPlugin() : undefined].filter(Boolean),
  assetsInclude: ['**/*.md'],
});

export const createBuildConfig = (
  version: VueVersion,
  formats: LibraryFormats[],
  emptyOutDir: boolean,
  userConfig?: UserConfig,
): UserConfig => {
  const isIIFE = formats.includes('iife');
  const prefix = getPrefix(version, formats);
  return mergeConfig<UserConfig, UserConfig>(
    {
      build: {
        copyPublicDir: true,
        cssCodeSplit: !isIIFE,
        emptyOutDir,
        lib: {
          entry: resolve(process.cwd(), `src/${version}.ts`),
          fileName: format => `index.${format}.min.js`,
          formats,
          name: LessCodeGlobalVar,
        },
        minify: true,
        rollupOptions: {
          external: getExternal(formats, version),
          output: {
            assetFileNames: isIIFE ? undefined : () => 'style.css',
            dir: resolve(process.cwd(), `dist/${version}`),
            exports: 'named',
            // 全局变量声明
            globals: {
              vue: 'Vue',
              '@blueking/ai-ui-sdk': 'BKAIUISDK',
              dayjs: 'dayjs',
              'highlight.js': 'hljs',
              'markdown-it': 'MarkdownIt',
              'markdown-it-code-copy': 'MarkdownItCodeCopy',
              'bkui-vue': 'BKUIVUE',
              '@blueking/bkui-library': 'BKUI',
            },
          },
        },
      },
      publicDir: 'public',
      resolve:
        version === VueVersion.Vue2 && !isIIFE
          ? { alias: [{ find: 'vue', replacement: '@blueking/bkui-library' }] }
          : undefined,
      ...createCommonConfig(prefix, isIIFE),
    },
    {
      ...userConfig,
    },
  );
};
