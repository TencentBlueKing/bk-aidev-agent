import fs from "node:fs"
import path from "node:path"
import { fileURLToPath } from "node:url"

const changelogPath = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "../../changelog.md",
)

/**
 * 从 docs/changelog.md 首条版本标题读取当前文档对应的组件版本。
 * 与 workspace / npm 依赖声明解耦，避免 PaaS 单模块部署时路径或版本不一致。
 */
export function resolveLatestChangelogVersion() {
  const content = fs.readFileSync(changelogPath, "utf8")
  const match = content.match(/^##\s+v(.+?)\s*$/m)
  if (!match) {
    throw new Error(
      "[ai-blueking-docs] 无法在 changelog.md 中解析版本号（期望首条 ## vX.Y.Z 标题）",
    )
  }
  return match[1].trim()
}

export const aiBluekingVersion = resolveLatestChangelogVersion()
