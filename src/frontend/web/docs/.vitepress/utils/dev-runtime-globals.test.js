import assert from "node:assert/strict"
import { dirname, resolve } from "node:path"
import { test } from "node:test"
import { fileURLToPath } from "node:url"

import { resolveDevRuntimeGlobalsScript } from "./dev-runtime-globals.js"

const docsRoot = resolve(dirname(fileURLToPath(import.meta.url)), "../..")

test("development 从 docs/.env* 读取 BK_AIDEV_URL，不依赖 process.env", () => {
  const script = resolveDevRuntimeGlobalsScript({
    mode: "development",
    envDir: docsRoot,
    processEnv: {},
  })

  assert.match(script, /window\.BK_AIDEV_URL="https:\/\/xxx.com"/)
})

test("process.env 优先于 .env 文件", () => {
  const script = resolveDevRuntimeGlobalsScript({
    mode: "development",
    envDir: docsRoot,
    processEnv: { BK_AIDEV_URL: "https://example.com" },
  })

  assert.match(script, /window\.BK_AIDEV_URL="https:\/\/example.com"/)
})

test("production 不内联，交给运行时注入", () => {
  const script = resolveDevRuntimeGlobalsScript({
    mode: "production",
    envDir: docsRoot,
    processEnv: { BK_AIDEV_URL: "https://example.com" },
  })

  assert.equal(script, "")
})
