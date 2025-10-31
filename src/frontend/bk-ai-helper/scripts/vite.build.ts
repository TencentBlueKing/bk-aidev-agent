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
import { execSync } from 'child_process';
import { existsSync, readFileSync, writeFileSync } from 'fs';
import { resolve } from 'path';
import { type LibraryFormats, type UserConfig, build } from 'vite';

import { createBuildConfig, VueVersion } from './vite.utils';

const buildLib = async (
  version: VueVersion,
  formats: LibraryFormats[],
  emptyOutDir = false,
  userConfig?: UserConfig,
  buildType?: 'internal' | 'external',
) => {
  await build({
    ...createBuildConfig(version, formats, emptyOutDir, userConfig, buildType),
  });
};

/**
 * 生成类型声明文件
 */
const generateTypes = () => {
  console.log('\n📝 生成类型声明文件...');

  try {
    // 运行 vue-tsc 生成类型文件到 dist/typings 目录
    execSync('vue-tsc --project tsconfig.dts.json', {
      stdio: 'inherit',
      cwd: process.cwd(),
    });

    // 检查生成的类型文件
    const typingsDir = resolve(process.cwd(), 'dist/typings');
    if (!existsSync(typingsDir)) {
      throw new Error('❌ 类型文件生成失败：dist/typings 目录不存在');
    }

    const distDir = resolve(process.cwd(), 'dist');

    // 为 Vue3 和 Vue2 生成入口类型文件
    const vue3TypesPath = resolve(typingsDir, 'vue3.d.ts');
    const vue2TypesPath = resolve(typingsDir, 'vue2.d.ts');

    if (existsSync(vue3TypesPath)) {
      const content = readFileSync(vue3TypesPath, 'utf-8');
      writeFileSync(resolve(distDir, 'vue3.d.ts'), content);
      console.log('✅ 已生成 dist/vue3.d.ts');
    } else {
      // 如果不存在 vue3.d.ts，从 index.vue.d.ts 创建
      const indexVuePath = resolve(typingsDir, 'index.vue.d.ts');
      if (existsSync(indexVuePath)) {
        writeFileSync(
          resolve(distDir, 'vue3.d.ts'),
          `export { default } from './typings/index.vue';\nexport * from './typings/index.vue';\n`
        );
        console.log('✅ 已生成 dist/vue3.d.ts（从 index.vue.d.ts）');
      } else {
        console.warn('⚠️  未找到 vue3.d.ts 或 index.vue.d.ts');
      }
    }

    if (existsSync(vue2TypesPath)) {
      const content = readFileSync(vue2TypesPath, 'utf-8');
      writeFileSync(resolve(distDir, 'vue2.d.ts'), content);
      console.log('✅ 已生成 dist/vue2.d.ts');
    } else {
      // 如果不存在 vue2.d.ts，从 index.vue.d.ts 创建
      const indexVuePath = resolve(typingsDir, 'index.vue.d.ts');
      if (existsSync(indexVuePath)) {
        writeFileSync(
          resolve(distDir, 'vue2.d.ts'),
          `export { default } from './typings/index.vue';\nexport * from './typings/index.vue';\n`
        );
        console.log('✅ 已生成 dist/vue2.d.ts（从 index.vue.d.ts）');
      } else {
        console.warn('⚠️  未找到 vue2.d.ts 或 index.vue.d.ts');
      }
    }

    console.log('✅ 类型声明文件生成完成\n');
  } catch (error) {
    console.error('❌ 类型文件生成失败：', error instanceof Error ? error.message : error);
    throw error;
  }
};

(async () => {
  // 从环境变量读取构建类型
  const buildType = process.env.BUILD_TYPE as 'internal' | 'external' | undefined;

  // Build Vue3 version
  await buildLib(VueVersion.Vue3, ['es', 'umd'], true, undefined, buildType);
  await buildLib(VueVersion.Vue3, ['iife'], false, undefined, buildType);

  // Build Vue2 version
  await buildLib(VueVersion.Vue2, ['es', 'umd'], false, undefined, buildType);
  await buildLib(VueVersion.Vue2, ['iife'], false, undefined, buildType);

  // 生成类型声明文件
  generateTypes();
})();
