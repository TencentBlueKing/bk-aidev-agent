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
import { execSync } from "child_process"
import { existsSync, readFileSync, writeFileSync, unlinkSync } from "fs"
import { resolve } from "path"
import { createInterface } from "readline"

const PACKAGE_JSON_PATH = resolve(process.cwd(), "package.json")
const README_PATH = resolve(process.cwd(), "README.md")
const DIST_VUE3_PATH = resolve(process.cwd(), "dist/vue3/index.es.min.js")
const DIST_VUE2_PATH = resolve(process.cwd(), "dist/vue2/index.es.min.js")

const EXTERNAL_REGISTRY = "https://registry.npmjs.org/"
const INTERNAL_REGISTRY = "https://mirrors.tencent.com/npm/"

const INTERNAL_PACKAGE_NAME = "@tencent/bk-ai-helper"
const EXTERNAL_PACKAGE_NAME = "@blueking/bk-ai-helper"

interface PublishOptions {
  buildType: "internal" | "external"
  skipConfirm?: boolean
}

/**
 * 检查构建产物是否存在
 */
function checkBuildArtifacts(): void {
  if (!existsSync(DIST_VUE3_PATH)) {
    throw new Error("❌ 构建产物不存在！请先运行构建命令：pnpm run build:external 或 pnpm run build:internal")
  }
  if (!existsSync(DIST_VUE2_PATH)) {
    throw new Error("❌ Vue2 构建产物不存在！")
  }
  console.log("✅ 构建产物检查通过")
}

/**
 * 验证构建产物中的 baseUrl 值
 */
function verifyBaseUrl(buildType: "internal" | "external"): void {
  const vue3Content = readFileSync(DIST_VUE3_PATH, "utf-8")
  const vue2Content = readFileSync(DIST_VUE2_PATH, "utf-8")

  // 从构建产物中提取 baseUrl 默认值
  const extractBaseUrl = (content: string): string | null => {
    const match = content.match(/baseUrl:\s*\{\s*default:\s*"([^"]*)"/)
    return match ? match[1] : null
  }

  const vue3BaseUrl = extractBaseUrl(vue3Content)
  const vue2BaseUrl = extractBaseUrl(vue2Content)

  console.log(`📦 Vue3 baseUrl 默认值: "${vue3BaseUrl ?? "未找到"}"`)
  console.log(`📦 Vue2 baseUrl 默认值: "${vue2BaseUrl ?? "未找到"}"`)

  if (buildType === "external") {
    // 外部版：baseUrl 必须为空字符串
    if (vue3BaseUrl !== "" || vue2BaseUrl !== "") {
      throw new Error(
        `❌ 构建验证失败！外部版的 baseUrl 必须为空字符串，但检测到：\n` +
          `  Vue3: "${vue3BaseUrl}"\n` +
          `  Vue2: "${vue2BaseUrl}"\n` +
          `请确保使用 pnpm run build:external 进行构建`
      )
    }
    console.log("✅ 外部版验证通过：baseUrl 为空字符串")
  } else {
    // 内部版：baseUrl 必须不为空
    if (!vue3BaseUrl || vue3BaseUrl === "" || !vue2BaseUrl || vue2BaseUrl === "") {
      throw new Error(
        `❌ 构建验证失败！内部版的 baseUrl 不能为空，但检测到：\n` +
          `  Vue3: "${vue3BaseUrl}"\n` +
          `  Vue2: "${vue2BaseUrl}"\n` +
          `请确保使用 pnpm run build:internal 进行构建，并已设置 .env 文件`
      )
    }
    console.log(`✅ 内部版验证通过：baseUrl 为 "${vue3BaseUrl}"`)
  }
}

/**
 * 规范化 registry URL（去除尾部斜杠）
 */
function normalizeRegistry(registry: string): string {
  return registry.replace(/\/+$/, "")
}

/**
 * 检查 npm registry 配置
 */
function checkRegistry(buildType: "internal" | "external"): void {
  try {
    const registry = execSync("npm config get registry", { encoding: "utf-8" }).trim()
    const expectedRegistry = buildType === "external" ? EXTERNAL_REGISTRY : INTERNAL_REGISTRY

    // 规范化 registry URL（去除尾部斜杠以便比较）
    const normalizedRegistry = normalizeRegistry(registry)
    const normalizedExpected = normalizeRegistry(expectedRegistry)

    console.log(`📡 当前 npm registry: ${registry}`)
    console.log(`📡 预期 registry: ${expectedRegistry}`)

    if (normalizedRegistry !== normalizedExpected) {
      console.warn(
        `⚠️  警告：当前 npm registry 与预期不符！\n` +
          `  ${buildType === "external" ? "外部版" : "内部版"}应该使用: ${expectedRegistry}\n` +
          `  如果使用 --registry 参数发布，此警告可以忽略`
      )
    } else {
      console.log("✅ Registry 配置正确")
    }
  } catch (error) {
    console.warn("⚠️  无法检查 registry 配置，将使用发布命令中的 registry 参数")
  }
}

/**
 * 读取 package.json
 */
function readPackageJson(): {
  name: string
  version: string
  publishConfig?: { registry?: string; access?: string }
} {
  const content = readFileSync(PACKAGE_JSON_PATH, "utf-8")
  return JSON.parse(content)
}

/**
 * 移除 README 中的 BUILD_GUIDE.md 链接（该文件不在发布包中）
 */
function removeBuildGuideLink(content: string): string {
  return content.replace(/详细构建指南请参考 \[BUILD_GUIDE\.md\]\(\.\/BUILD_GUIDE\.md\)。?\n*/g, "")
}

/**
 * 修改 README 文件，为内部版添加默认值说明
 */
function modifyReadmeForInternal(): string {
  const originalContent = readFileSync(README_PATH, "utf-8")
  let modifiedContent = originalContent

  // 1. 替换包名 @blueking/bk-ai-helper -> @tencent/bk-ai-helper
  modifiedContent = modifiedContent.replace(/@blueking\/bk-ai-helper/g, "@tencent/bk-ai-helper")

  // 2. 修改 base-url 的说明，从"必填"改为"可选（有默认值）"
  modifiedContent = modifiedContent.replace(
    /\| `base-url`\s+\| `String`\s+\| -\s+\| \*\*必填\*\*，AI API 基础地址\s+\|/,
    "| `base-url`     | `String` | 内置默认值                                           | **可选**，AI API 基础地址（内部版已配置默认值，可不填） |"
  )

  // 3. 在代码示例中添加注释说明 base-url 可选（注释掉所有 base-url）
  modifiedContent = modifiedContent.replace(/(\s+)base-url="[^"]+"/g, '$1<!-- base-url="..." --> <!-- 可选，已有内置默认值 -->')

  // 4. 在快速开始部分添加说明
  modifiedContent = modifiedContent.replace(
    /(## 🚀 快速开始)/,
    `$1

> **内部版说明**：本包已内置腾讯内部 AI 服务地址，\`base-url\` 参数可以省略。如果你需要使用其他 AI 服务，可以通过 \`base-url\` 参数自定义。
`
  )

  // 5. 移除 BUILD_GUIDE.md 链接（该文件不在发布包中）
  modifiedContent = removeBuildGuideLink(modifiedContent)

  // 写入修改后的内容
  writeFileSync(README_PATH, modifiedContent, "utf-8")

  // 返回原始内容供恢复使用
  return originalContent
}

/**
 * 修改 README 文件，为外部版清理不需要的内容
 */
function modifyReadmeForExternal(): string {
  const originalContent = readFileSync(README_PATH, "utf-8")
  let modifiedContent = originalContent

  // 移除 BUILD_GUIDE.md 链接（该文件不在发布包中）
  modifiedContent = removeBuildGuideLink(modifiedContent)

  // 写入修改后的内容
  writeFileSync(README_PATH, modifiedContent, "utf-8")

  // 返回原始内容供恢复使用
  return originalContent
}

/**
 * 恢复 README 文件
 */
function restoreReadme(originalContent: string): void {
  writeFileSync(README_PATH, originalContent, "utf-8")
  console.log("📝 已恢复 README.md")
}

/**
 * 修改 package.json 中的包名和 publishConfig
 */
function modifyPackageForPublish(buildType: "internal" | "external"): {
  originalName: string
  originalRegistry?: string
  hadPublishConfig: boolean
  originalReadme?: string
} {
  const pkg = readPackageJson()
  const originalName = pkg.name
  const originalRegistry = pkg.publishConfig?.registry
  const hadPublishConfig = !!pkg.publishConfig
  let originalReadme: string | undefined

  // 根据构建类型设置包名
  const targetName = buildType === "internal" ? INTERNAL_PACKAGE_NAME : EXTERNAL_PACKAGE_NAME
  pkg.name = targetName

  // 删除 publishConfig.registry
  if (pkg.publishConfig) {
    delete pkg.publishConfig.registry
    // 如果 publishConfig 为空对象，删除整个 publishConfig
    if (Object.keys(pkg.publishConfig).length === 0) {
      delete pkg.publishConfig
    }
  }

  // 保存更新后的 package.json
  writeFileSync(PACKAGE_JSON_PATH, JSON.stringify(pkg, null, 2) + "\n", "utf-8")

  console.log(`📝 已修改包名: ${originalName} → ${targetName}`)

  // 修改 README
  if (buildType === "internal") {
    originalReadme = modifyReadmeForInternal()
    console.log("📝 已修改 README.md（添加内部版说明，移除构建指南链接）")
  } else {
    originalReadme = modifyReadmeForExternal()
    console.log("📝 已修改 README.md（移除构建指南链接）")
  }

  return { originalName, originalRegistry, hadPublishConfig, originalReadme }
}

/**
 * 恢复 package.json 中的包名和 publishConfig，以及 README
 */
function restorePackageJson(originalName: string, originalRegistry?: string, hadPublishConfig?: boolean, originalReadme?: string): void {
  const pkg = readPackageJson()

  // 恢复原始包名
  pkg.name = originalName

  if (originalRegistry) {
    // 恢复原始 registry
    if (!pkg.publishConfig) {
      pkg.publishConfig = {}
    }
    pkg.publishConfig.registry = originalRegistry
  } else if (hadPublishConfig && !pkg.publishConfig) {
    // 如果原来有 publishConfig（但 registry 为空），恢复空的 publishConfig
    pkg.publishConfig = {}
  }

  writeFileSync(PACKAGE_JSON_PATH, JSON.stringify(pkg, null, 2) + "\n", "utf-8")
  console.log(`📝 已恢复包名: ${originalName}`)

  // 恢复 README
  if (originalReadme) {
    restoreReadme(originalReadme)
  }
}

/**
 * 用户确认发布
 */
function confirmPublish(buildType: "internal" | "external"): Promise<boolean> {
  return new Promise((resolve) => {
    const rl = createInterface({
      input: process.stdin,
      output: process.stdout,
    })

    const pkg = readPackageJson()
    const registry = buildType === "external" ? EXTERNAL_REGISTRY : INTERNAL_REGISTRY
    const packageName = buildType === "internal" ? INTERNAL_PACKAGE_NAME : EXTERNAL_PACKAGE_NAME

    console.log("\n" + "=".repeat(60))
    console.log("📤 发布确认")
    console.log("=".repeat(60))
    console.log(`📦 包名: ${packageName}`)
    console.log(`📌 版本: ${pkg.version}`)
    console.log(`🏷️  构建类型: ${buildType === "external" ? "外部版（开源）" : "内部版（腾讯内部）"}`)
    console.log(`🌐 Registry: ${registry}`)
    console.log("=".repeat(60))
    console.log("⚠️  确认要发布吗？(yes/no): ")

    rl.question("", (answer) => {
      rl.close()
      resolve(answer.toLowerCase() === "yes" || answer.toLowerCase() === "y")
    })
  })
}

/**
 * 执行发布
 */
function publish(buildType: "internal" | "external"): void {
  const registry = buildType === "external" ? EXTERNAL_REGISTRY : INTERNAL_REGISTRY
  const packageName = buildType === "internal" ? INTERNAL_PACKAGE_NAME : EXTERNAL_PACKAGE_NAME
  console.log(`\n🚀 开始发布到 ${registry}...`)

  // 修改 package.json 中的包名和删除 publishConfig.registry，以及修改 README
  const { originalName, originalRegistry, hadPublishConfig, originalReadme } = modifyPackageForPublish(buildType)

  // 验证删除是否生效
  const pkg = readPackageJson()
  if (pkg.publishConfig?.registry) {
    throw new Error(
      `❌ 致命错误：package.json 中的 registry 删除失败！\n` + `  当前值: ${pkg.publishConfig?.registry}\n` + `  这可能导致发布到错误的 registry！`
    )
  }
  console.log(`✅ 已验证 package.json 中已无 publishConfig.registry`)

  try {
    // 使用 --registry 参数强制指定 registry
    // 同时设置环境变量确保 npm 使用正确的 registry
    const env = { ...process.env }
    env.npm_config_registry = registry

    console.log(`🔍 最终使用的 registry: ${registry}`)
    console.log(`📋 package.json 中的 registry: ${pkg.publishConfig?.registry || "已删除（将使用命令行参数）"}`)

    // 临时设置 npm config registry，确保使用正确的 registry
    const originalNpmRegistry = execSync("npm config get registry", { encoding: "utf-8" }).trim()
    // 保存原始的 scope registry 配置
    const scopeName = buildType === "internal" ? "@tencent" : "@blueking"
    let originalScopeRegistry: string | null = null
    try {
      originalScopeRegistry = execSync(`npm config get ${scopeName}:registry`, { encoding: "utf-8" }).trim()
      if (originalScopeRegistry === "undefined") {
        originalScopeRegistry = null
      }
    } catch (error) {
      // 如果没有设置 scope registry，忽略错误
    }

    try {
      execSync(`npm config set registry ${registry}`, { stdio: "pipe" })
      console.log(`📝 已临时设置 npm config registry: ${registry}`)

      // 设置 scope registry（这个优先级最高）
      execSync(`npm config set ${scopeName}:registry ${registry}`, { stdio: "pipe" })
      console.log(`📝 已临时设置 ${scopeName} scope registry: ${registry}`)

      // 验证 npm config 是否设置成功
      const currentNpmRegistry = execSync("npm config get registry", { encoding: "utf-8" }).trim()
      const currentScopeRegistry = execSync(`npm config get ${scopeName}:registry`, { encoding: "utf-8" }).trim()
      if (normalizeRegistry(currentNpmRegistry) !== normalizeRegistry(registry)) {
        throw new Error(`❌ npm config registry 设置失败！\n` + `  当前值: ${currentNpmRegistry}\n` + `  期望值: ${registry}`)
      }
      if (normalizeRegistry(currentScopeRegistry) !== normalizeRegistry(registry)) {
        throw new Error(`❌ ${scopeName} scope registry 设置失败！\n` + `  当前值: ${currentScopeRegistry}\n` + `  期望值: ${registry}`)
      }
      console.log(`✅ npm config registry 验证成功`)
      console.log(`✅ ${scopeName} scope registry 验证成功`)

      // 先打包，然后验证 tarball 中的 package.json registry 是否正确
      // 这样可以确保发布的内容中的 registry 配置是正确的
      const pkg = readPackageJson()
      const tarballName = `${pkg.name.replace("@", "").replace(/\//g, "-")}-${pkg.version}.tgz`
      const tarballPath = resolve(process.cwd(), tarballName)
      const verifyPkgPath = resolve(process.cwd(), ".verify-pkg.json")

      console.log(`📦 打包 tarball 以验证 registry 配置...`)
      try {
        execSync(`npm pack`, { stdio: "pipe", cwd: process.cwd() })
      } catch (error) {
        throw new Error(`❌ 打包失败，无法验证 registry 配置`)
      }

      // 验证 tarball 中的 package.json
      if (!existsSync(tarballPath)) {
        throw new Error(`❌ tarball 文件不存在: ${tarballName}`)
      }

      try {
        // 解压并读取 tarball 中的 package.json
        execSync(`tar -xzf "${tarballName}" package/package.json -O > "${verifyPkgPath}"`, {
          stdio: "pipe",
          cwd: process.cwd(),
        })

        if (!existsSync(verifyPkgPath)) {
          throw new Error(`❌ 无法从 tarball 中提取 package.json`)
        }

        const tarballPkg = JSON.parse(readFileSync(verifyPkgPath, "utf-8"))
        const tarballRegistry = tarballPkg.publishConfig?.registry

        console.log(`🔍 tarball 中的 registry: ${tarballRegistry || "未设置（正确）"}`)

        // 验证 tarball 中不应该有 publishConfig.registry（因为我们已删除）
        if (tarballRegistry) {
          unlinkSync(tarballPath)
          if (existsSync(verifyPkgPath)) {
            unlinkSync(verifyPkgPath)
          }
          throw new Error(
            `❌ 致命错误：tarball 中仍然包含 publishConfig.registry！\n` +
              `  tarball 中的 registry: ${tarballRegistry}\n` +
              `  这可能导致发布到错误的 registry！\n` +
              `  发布已取消。`
          )
        }

        console.log(`✅ tarball 中已确认无 publishConfig.registry（将使用命令行参数）`)

        // 清理验证文件
        if (existsSync(verifyPkgPath)) {
          unlinkSync(verifyPkgPath)
        }

        // 使用 tarball 发布，确保使用正确的 registry
        console.log(`🚀 使用已验证的 tarball 发布到 ${registry}...`)
        execSync(`npm publish "${tarballName}" --registry=${registry}`, {
          stdio: "inherit",
          cwd: process.cwd(),
          env: env,
        })

        // 清理 tarball
        if (existsSync(tarballPath)) {
          unlinkSync(tarballPath)
        }
        console.log("✅ 发布成功！")
      } catch (error) {
        // 清理文件
        if (existsSync(tarballPath)) {
          unlinkSync(tarballPath)
        }
        if (existsSync(verifyPkgPath)) {
          unlinkSync(verifyPkgPath)
        }
        throw error
      }
    } finally {
      // 恢复 npm config registry
      if (originalNpmRegistry) {
        execSync(`npm config set registry ${originalNpmRegistry}`, { stdio: "pipe" })
        console.log(`📝 已恢复 npm config registry: ${originalNpmRegistry}`)
      }
      // 恢复 scope registry
      if (originalScopeRegistry) {
        execSync(`npm config set ${scopeName}:registry ${originalScopeRegistry}`, { stdio: "pipe" })
        console.log(`📝 已恢复 ${scopeName} scope registry: ${originalScopeRegistry}`)
      } else {
        // 如果原来没有设置，删除临时设置的值
        try {
          execSync(`npm config delete ${scopeName}:registry`, { stdio: "pipe" })
          console.log(`📝 已删除临时的 ${scopeName} scope registry`)
        } catch (error) {
          // 忽略删除失败的错误
        }
      }
    }
  } catch (error) {
    console.error("❌ 发布失败！")
    throw error
  } finally {
    // 恢复原始配置
    restorePackageJson(originalName, originalRegistry, hadPublishConfig, originalReadme)
  }
}

/**
 * 清理构建产物
 */
function cleanDist(): void {
  console.log("\n🧹 清理构建产物...")
  try {
    execSync("rm -rf dist", { stdio: "inherit" })
    console.log("✅ 清理完成")
  } catch (error) {
    console.warn("⚠️  清理失败，请手动删除 dist 目录")
  }
}

/**
 * 执行构建
 */
function build(buildType: "internal" | "external"): void {
  console.log(`\n🔨 开始构建（${buildType === "external" ? "外部版" : "内部版"}）...\n`)
  try {
    execSync(`pnpm run build:${buildType}`, {
      stdio: "inherit",
      cwd: process.cwd(),
    })
    console.log("✅ 构建完成\n")
  } catch (error) {
    console.error("❌ 构建失败！")
    throw error
  }
}

/**
 * 主函数
 */
async function main() {
  const buildType = (process.env.BUILD_TYPE as "internal" | "external") || process.argv[2]

  if (!buildType || (buildType !== "internal" && buildType !== "external")) {
    console.error("❌ 错误：必须指定构建类型")
    console.error("用法: tsx scripts/publish.ts [internal|external]")
    console.error("或设置环境变量: BUILD_TYPE=internal tsx scripts/publish.ts")
    process.exit(1)
  }

  console.log(`\n🚀 开始发布流程（${buildType === "external" ? "外部版" : "内部版"}）...\n`)

  try {
    // 0. 清理旧的构建产物（可选）
    if (existsSync(resolve(process.cwd(), "dist"))) {
      console.log("🧹 清理旧的构建产物...")
      execSync("rm -rf dist", { stdio: "inherit" })
    }

    // 1. 构建
    build(buildType)

    // 2. 检查构建产物
    checkBuildArtifacts()

    // 3. 验证 baseUrl
    verifyBaseUrl(buildType)

    // 4. 检查 registry
    checkRegistry(buildType)

    // 5. 用户确认
    if (!process.env.SKIP_CONFIRM) {
      const confirmed = await confirmPublish(buildType)
      if (!confirmed) {
        console.log("❌ 发布已取消")
        cleanDist()
        process.exit(0)
      }
    }

    // 6. 发布
    publish(buildType)

    // 7. 清理 dist
    cleanDist()

    console.log("\n✨ 发布流程完成！")
  } catch (error) {
    console.error("\n❌ 发布流程失败：", error instanceof Error ? error.message : error)
    // 失败时也清理 dist，避免留下敏感信息
    cleanDist()
    process.exit(1)
  }
}

main()
