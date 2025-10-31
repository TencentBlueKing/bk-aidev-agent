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
import vue from "@vitejs/plugin-vue"
import { readFileSync } from "fs"
import { resolve } from "path"
import { type LibraryFormats, type UserConfig, loadEnv, mergeConfig } from "vite"
import cssInjectedByJsPlugin from "vite-plugin-css-injected-by-js"

interface PackageJSON {
  name: string
  private?: boolean
  version?: string
}

const LessCodeGlobalVar = "lesscodeCustomComponentLibrary"
const env = loadEnv(process.env.NODE_ENV || "production", process.cwd(), "")

export enum VueVersion {
  Vue2 = "vue2",
  Vue3 = "vue3",
}

/**
 * 根据构建类型获取 AI_HELPER_BASE_URL
 * @param buildType 构建类型：'internal' | 'external' | undefined
 * @returns AI_HELPER_BASE_URL 字符串值
 */
function getAiHelperBaseUrl(buildType?: "internal" | "external"): string {
  if (buildType === "external") {
    // 外部版：强制使用空字符串，忽略所有环境变量和 .env 文件
    return ""
  }

  if (buildType === "internal") {
    // 内部版：必须从 .env 文件读取（临时删除环境变量，确保只从文件读取）
    const originalEnvValue = process.env.AI_HELPER_BASE_URL
    delete process.env.AI_HELPER_BASE_URL

    try {
      // 重新加载 .env 文件（此时环境变量已被删除，只会读取文件内容）
      const envFromFile = loadEnv(process.env.NODE_ENV || "production", process.cwd(), "")
      const baseUrl = envFromFile.AI_HELPER_BASE_URL

      // 恢复原始环境变量
      if (originalEnvValue !== undefined) {
        process.env.AI_HELPER_BASE_URL = originalEnvValue
      }

      if (!baseUrl || baseUrl.trim() === "") {
        throw new Error(
          "内部版构建失败：必须在 .env 文件中设置 AI_HELPER_BASE_URL 环境变量\n" +
            "请确保项目根目录存在 .env 文件，并包含：AI_HELPER_BASE_URL=你的AI服务地址"
        )
      }

      return baseUrl
    } catch (error) {
      // 确保恢复环境变量
      if (originalEnvValue !== undefined) {
        process.env.AI_HELPER_BASE_URL = originalEnvValue
      }
      throw error
    }
  }

  // 未指定构建类型：保持原有逻辑（向后兼容）
  return env.AI_HELPER_BASE_URL || ""
}

export function getPackageInfo<T extends PackageJSON>(relativePth = "../package.json") {
  const pkgPath = resolve(__dirname, relativePth)
  const pkg = JSON.parse(readFileSync(pkgPath, "utf-8")) as T
  if (pkg.private) {
    throw new Error(`Package ${pkg.name} is private`)
  }

  return { pkg, pkgPath }
}

function getExternal(formats: LibraryFormats[], version: VueVersion) {
  return (id: string) => {
    const isVue3 = version === VueVersion.Vue3
    if (formats.includes("iife")) {
      return isVue3 && /^vue$/.test(id)
    }
    if (/^dayjs[/]?\w*/.test(id) || (isVue3 && (/^bkui-vue/.test(id) || /^vue$/.test(id)))) {
      return true
    }
    return false
  }
}

function getPrefix(version: VueVersion, formats: LibraryFormats[]) {
  const isVue3 = version === VueVersion.Vue3
  const isIIFE = formats.includes("iife")
  return isVue3 && !isIIFE ? "bk" : env.BKUI_PREFIX
}

export const createCommonConfig = (prefix = env.BKUI_PREFIX, isIIFE = false, buildType?: "internal" | "external"): UserConfig => {
  const aiHelperBaseUrl = getAiHelperBaseUrl(buildType)

  return {
    css: {
      preprocessorOptions: {
        less: {
          javascriptEnabled: true,
          modifyVars: { "bk-prefix": prefix },
        },
        scss: {
          additionalData: `$bk-prefix: ${prefix};`,
        },
      },
    },
    define: {
      BKUI_PREFIX: JSON.stringify(prefix),
      AI_HELPER_BASE_URL: JSON.stringify(aiHelperBaseUrl),
      "process.env.NODE_ENV": JSON.stringify(env.NODE_ENV),
    },
    mode: env.NODE_ENV,
    plugins: [vue(), isIIFE ? cssInjectedByJsPlugin() : undefined].filter(Boolean),
  }
}

export const createBuildConfig = (
  version: VueVersion,
  formats: LibraryFormats[],
  emptyOutDir: boolean,
  userConfig?: UserConfig,
  buildType?: "internal" | "external"
): UserConfig => {
  const isIIFE = formats.includes("iife")
  const prefix = getPrefix(version, formats)
  const outputDir = resolve(process.cwd(), `dist/${version}`)
  return mergeConfig<UserConfig, UserConfig>(
    {
      build: {
        outDir: outputDir,
        copyPublicDir: false,
        cssCodeSplit: !isIIFE,
        emptyOutDir,
        lib: {
          entry: resolve(process.cwd(), `src/${version}.ts`),
          fileName: (format) => `index.${format}.min.js`,
          formats,
          name: LessCodeGlobalVar,
        },
        minify: false,
        rollupOptions: {
          external: getExternal(formats, version),
          output: {
            assetFileNames: isIIFE ? undefined : () => "style.css",
            dir: outputDir,
            exports: "named",
            globals: { vue: "Vue" },
          },
        },
      },
      publicDir: "public",
      ...createCommonConfig(prefix, isIIFE, buildType),
    },
    {
      ...userConfig,
    }
  )
}
