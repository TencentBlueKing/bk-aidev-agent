import assert from "node:assert/strict"
import { mkdtempSync, rmSync, writeFileSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"
import { test } from "node:test"

import { resolveDevRuntimeGlobalsScript } from "./dev-runtime-globals.js"

function withEnvDir(files, fn) {
  const envDir = mkdtempSync(join(tmpdir(), "docs-env-"))
  try {
    for (const [name, content] of Object.entries(files)) {
      writeFileSync(join(envDir, name), content)
    }
    return fn(envDir)
  } finally {
    rmSync(envDir, { recursive: true, force: true })
  }
}

test("development 从 .env* 读取 BK_AIDEV_URL / BK_AIDEV_API_URL，不依赖 process.env", () => {
  withEnvDir(
    {
      ".env.development": [
        "BK_AIDEV_URL = https://xxx.com",
        "BK_AIDEV_API_URL = https://api.example.com/",
        "",
      ].join("\n"),
    },
    envDir => {
      const script = resolveDevRuntimeGlobalsScript({
        mode: "development",
        envDir,
        processEnv: {},
      })

      assert.match(script, /window\.BK_AIDEV_URL="https:\/\/xxx.com"/)
      assert.match(script, /window\.BK_AIDEV_API_URL="https:\/\/api.example.com\/"/)
    },
  )
})

test("process.env 优先于 .env 文件", () => {
  withEnvDir(
    {
      ".env.development": "BK_AIDEV_URL = https://from-file.com\n",
    },
    envDir => {
      const script = resolveDevRuntimeGlobalsScript({
        mode: "development",
        envDir,
        processEnv: { BK_AIDEV_URL: "https://example.com" },
      })

      assert.match(script, /window\.BK_AIDEV_URL="https:\/\/example.com"/)
    },
  )
})

test("空值和模板占位符不注入", () => {
  withEnvDir(
    {
      ".env.development": [
        "BK_AIDEV_URL = ''",
        "BK_AIDEV_API_URL = '{{ BK_AIDEV_API_URL }}'",
        "",
      ].join("\n"),
    },
    envDir => {
      const script = resolveDevRuntimeGlobalsScript({
        mode: "development",
        envDir,
        processEnv: {},
      })

      assert.equal(script, "")
    },
  )
})

test("production 不内联，交给运行时注入", () => {
  const script = resolveDevRuntimeGlobalsScript({
    mode: "production",
    envDir: tmpdir(),
    processEnv: { BK_AIDEV_URL: "https://example.com" },
  })

  assert.equal(script, "")
})
