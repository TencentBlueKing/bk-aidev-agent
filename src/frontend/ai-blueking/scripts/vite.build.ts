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
import { mkdir, writeFile } from 'fs/promises';
import { resolve } from 'path';
// import { minify } from 'terser';
import { LibraryFormats, UserConfig, build } from 'vite';
import { zip } from 'zip-a-folder';

import bkuiHack from './bkui-hack';
import { VueVersion, createBuildConfig, getPackageInfo } from './vite.utils';
interface LesscodeConfig {
  displayName: string;
  events?: {
    name: string;
    tips: string;
  }[];
  framework?: VueVersion;
  name: string;
  props?: Record<string, { options: string | string[]; tips: string; type: 'string'; val: string }>;
  type: string;
}

const buildLib = async (
  version: VueVersion,
  formats: LibraryFormats[],
  emptyOutDir = false,
  userConfig?: UserConfig,
  // uglyfiy = false,
) => {
  await build({
    ...createBuildConfig(version, formats, emptyOutDir, userConfig),
  });
  const { pkg } = getPackageInfo<LesscodeConfig>('../lesscode/config.json');
  pkg.framework = version;
  await writeFile(resolve(__dirname, `../dist/${version}`, './config.json'), JSON.stringify(pkg));
};
(async () => {
  await buildLib(VueVersion.Vue3, ['es', 'umd'], true);
  await buildLib(VueVersion.Vue3, ['iife']);
  await buildLib(VueVersion.Vue2, ['es', 'umd'], true);
  await buildLib(VueVersion.Vue2, ['iife']);
  bkuiHack();
  await mkdir(resolve(__dirname, '../lesscode-dist')).catch(() => false);
  await zip(resolve(__dirname, '../dist/vue3/'), resolve(__dirname, '../lesscode-dist/vue3.zip'), {
    destPath: 'dist/',
  });
  await zip(resolve(__dirname, '../dist/vue2/'), resolve(__dirname, '../lesscode-dist/vue2.zip'), {
    destPath: 'dist/',
  });
})();
