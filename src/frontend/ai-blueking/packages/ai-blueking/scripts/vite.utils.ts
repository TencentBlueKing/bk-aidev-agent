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
import { dirname, resolve } from 'path';
import { fileURLToPath } from 'url';
import { type LibraryFormats, type UserConfig, loadEnv, mergeConfig } from 'vite';

// ESM 模式下 __dirname 不可用，需要手动定义
const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
import cssInjectedByJsPlugin from 'vite-plugin-css-injected-by-js';

interface PackageJSON {
  name: string;
  private?: boolean;
  version?: string;
}

const LessCodeGlobalVar = 'AIBluekingV2';
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

function getExternal(formats: LibraryFormats[], version: VueVersion) {
  return (id: string) => {
    const isVue3 = version === VueVersion.Vue3;
    if (formats.includes('iife')) {
      return isVue3 && /^vue$/.test(id);
    }

    // ES/UMD: externalize chat-x JS（chat-x 与宿主共享同一 Vue3 运行时）
    // CSS 通过 vue3.ts 中 import '@blueking/chat-x/dist/index.css' 合并进 style.css
    // 注意：仅 Vue3 external chat-x；Vue2 需要打包 chat-x（vue 通过 alias 替换为 bkui-library）

    // tippy.js 为纯 JS，Vue2/Vue3 均可由消费方提供
    if (/^tippy\.js/.test(id)) {
      return true;
    }

    if (isVue3) {
      // Vue3: externalize vue、bkui-vue、vue-tippy
      // chat-x / chat-helper 通过 alias 从源码编译内联，确保版本一致（避免业务方依赖版本未同步导致的问题）
      // 其他所有第三方 npm 包（如 mermaid、highlight.js 等）继续 external，避免递归打包导致体积爆炸
      if (/^vue$/.test(id) || /^bkui-vue/.test(id) || /^vue-tippy/.test(id)) {
        return true;
      }
      // 同 monorepo 下的 @blueking 包从源码内联，确保版本一致
      if (id.startsWith('@blueking/chat-x') || id.startsWith('@blueking/chat-helper')) {
        return false;
      }
      // external 所有其他第三方 npm 包名（非相对路径、非绝对路径），包括 chat-x 的第三方依赖
      if (!id.startsWith('.') && !id.startsWith('/')) {
        return true;
      }
    } else {
      // Vue2: vue 通过 alias 替换为 @blueking/bkui-library，因此不 external vue 本身
      // bkui-vue、vue-tippy、@blueking/chat-helper 需打包进产物，使 import { ref } from 'vue' 统一走 bkui-library
      // （若 chat-helper external，其 ref 会解析到宿主 Vue2.7，与内嵌子应用响应式脱节）
      if (/^@blueking\/bkui-library/.test(id)) {
        return true;
      }
    }

    return false;
  };
}

function getPrefix(version: VueVersion, formats: LibraryFormats[]) {
  const isVue3 = version === VueVersion.Vue3;
  const isIIFE = formats.includes('iife');
  return isVue3 && !isIIFE ? 'bk' : env.BKUI_PREFIX || 'bk';
}

export const createCommonConfig = (prefix = 'bk', isIIFE = false): UserConfig => ({
  css: {
    preprocessorOptions: {
      scss: {
        additionalData: `$bk-prefix: ${prefix};`,
      },
    },
  },
  define: {
    BKUI_PREFIX: JSON.stringify(prefix),
    'process.env.NODE_ENV': JSON.stringify(env.NODE_ENV || 'production'),
  },
  mode: env.NODE_ENV || 'production',
  plugins: [vue(), isIIFE ? cssInjectedByJsPlugin() : undefined].filter(Boolean),
  resolve: {
    alias: [
      // Vue2 非IIFE: chat-x 不 external，需从源码编译以走 vue → bkui-library alias
      // Vue3: chat-x 不再 external，通过 alias 从源码内联打包，确保版本一致且 Tree Shaking 更友好
      {
        find: '@blueking/chat-x',
        replacement: resolve(__dirname, '../../chat-x/src'),
      },
      // chat-helper 同 chat-x，从源码编译内联打包，确保版本一致且 Tree Shaking 更友好
      {
        find: '@blueking/chat-helper',
        replacement: resolve(__dirname, '../../chat-helper/src'),
      },
    ],
  },
  // 包含 icon 资源文件
  assetsInclude: [
    '**/*.md',
    '**/*.png',
    '**/*.jpg',
    '**/*.jpeg',
    '**/*.svg',
    '**/*.woff',
    '**/*.woff2',
    '**/*.ttf',
    '**/*.eot',
    '**/*.json',
  ],
});

export const createBuildConfig = (
  version: VueVersion,
  formats: LibraryFormats[],
  emptyOutDir: boolean,
  userConfig?: UserConfig,
): UserConfig => {
  const isIIFE = formats.includes('iife');
  const isVue2 = version === VueVersion.Vue2;
  const prefix = getPrefix(version, formats);

  const vue2Alias = isVue2 && !isIIFE ? [{ find: 'vue', replacement: '@blueking/bkui-library' }] : [];

  // 注意：不能用 ...createCommonConfig() 展开，否则 commonConfig.resolve 会覆盖 buildConfig.resolve
  // 必须通过 mergeConfig 深度合并，确保 resolve.alias 数组被拼接而非覆盖
  const buildSpecificConfig: UserConfig = {
    build: {
      copyPublicDir: false,
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
          globals: {
            vue: 'Vue',
            'bkui-vue': 'BKUIVUE',
            '@blueking/chat-helper': 'ChatHelper',
            '@blueking/chat-x': 'BkUIChatX',
            '@blueking/bkui-library': 'BKUI',
            'tippy.js': 'tippy',
            'vue-tippy': 'VueTippy',
            dompurify: 'DOMPurify',
            'lodash/throttle': 'lodash',
            'lodash/debounce': 'lodash',
            'markdown-it-footnote': 'markdownItFootnote',
            'markdown-it-ins': 'markdownItIns',
            'markdown-it-mark': 'markdownItMark',
            'markdown-it-sub': 'markdownItSub',
            'markdown-it-sup': 'markdownItSup',
            'markdown-it-task-checkbox': 'markdownItTaskCheckbox',
            'highlight.js': 'hljs',
            'highlight.js/styles/github-dark.css': 'hljs',
            katex: 'katex',
            'katex/dist/katex.min.css': 'katex',
            zod: 'zod',
            'tippy.js/dist/tippy.css': 'tippy',
            'linkify-it': 'linkifyIt',
            mdurl: 'mdurl',
            'punycode.js': 'punycode',
            entities: 'entities',
            'uc.micro': 'ucMicro',
            'bkui-vue/lib/icon': 'BKUIVUE',
            'vue-draggable-resizable': 'VueDraggableResizable',
            'vue-draggable-resizable/style.css': 'VueDraggableResizable',
          },
        },
      },
    },
    resolve: {
      alias: [
        {
          find: '@',
          replacement: resolve(process.cwd(), 'src'),
        },
        ...vue2Alias,
      ],
    },
  };

  const merged = mergeConfig<UserConfig, UserConfig>(createCommonConfig(prefix, isIIFE), buildSpecificConfig);

  return mergeConfig<UserConfig, UserConfig>(merged, { ...userConfig });
};
