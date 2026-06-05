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
import { LibraryFormats, UserConfig, build } from 'vite';

import { VueVersion, createBuildConfig } from './vite.utils';

const buildLib = async (
  version: VueVersion,
  formats: LibraryFormats[],
  emptyOutDir = false,
  userConfig?: UserConfig,
) => {
  await build({
    ...createBuildConfig(version, formats, emptyOutDir, userConfig),
  });
};

(async () => {
  // 构建 Vue3 版本
  await buildLib(VueVersion.Vue3, ['es', 'umd'], true);
  await buildLib(VueVersion.Vue3, ['iife']);

  // 构建 Vue2 版本：vue 被 alias 到 @blueking/bkui-library，bkui-vue/vue-tippy 等打包进产物
  await buildLib(VueVersion.Vue2, ['es', 'umd'], true);
  await buildLib(VueVersion.Vue2, ['iife']);

  // Standalone：内联 Vue3 + chat-x，供非 Vue 宿主 mount / 同源 render
  await buildLib(VueVersion.Standalone, ['es', 'umd'], false);
  await buildLib(VueVersion.Standalone, ['iife'], false);
})();
