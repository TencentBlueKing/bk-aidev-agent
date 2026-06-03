---
name: MCP 服务
slug: mcp
category: ai
description: >
  @blueking/chat-x 内置 MCP Server，让 AI IDE（如 Cursor）直接查询组件文档。
aiSummary: >
  chat-x 提供基于 @modelcontextprotocol/sdk 的 MCP Server，暴露 list_components、
  get_component_doc、search_docs 三个工具。AI IDE 通过 MCP 协议即可查询组件列表、
  获取完整文档（含 AI 摘要）、按关键词搜索。需先运行 build-index 构建索引。
relatedComponents: []
sinceVersion: '1.0.0'
---

# MCP 服务

[Model Context Protocol（MCP）](https://modelcontextprotocol.io/) 是一套让 AI 助手通过标准协议调用本地工具、读取资源的规范。`@blueking/chat-x` 在包内提供基于 `@modelcontextprotocol/sdk` 的 **stdio MCP Server**，使 Cursor 等 IDE 能直接列出组件、拉取 Wiki 清洗后的文档并在文档内关键词搜索，减少「猜 API」与反复翻源码的成本。

## 快速接入

### Cursor 配置示例

仓库根目录的 `.cursor/mcp.json` 可参考如下写法（需已构建出 `dist/mcp/index.js`）：

```json
{
  "mcpServers": {
    "chat-x": {
      "command": "node",
      "args": ["packages/chat-x/dist/mcp/index.js"]
    }
  }
}
```

### 启动方式

- **IDE 集成**：按上述配置后，由 Cursor 在需要时拉起进程；传输层为 **stdio**（见 `packages/chat-x/mcp/src/index.ts` 中的 `StdioServerTransport`）。
- **本地调试**：在 `packages/chat-x` 下可使用 `pnpm mcp:dev`（以 `tsx` 直接运行源码入口）或 `pnpm mcp:start`（运行编译后的 `dist/mcp/index.js`）。

首次使用前请执行 **`pnpm mcp:build`**（`tsc` 编译 + 生成文档索引），保证存在 `dist/mcp/index.js` 与 `dist/mcp/generated/index.json`。

## 可用工具

工具在 `packages/chat-x/mcp/src/server.ts` 中注册，名称与实现如下。

### `list_components`

列出索引中的组件、composables 与类型定义条目（来自 `loadIndex()` 读取的 `index.json`）。

**参数（Zod schema）**

| 字段     | 类型 | 说明 |
| -------- | ---- | ---- |
| `kind`   | 枚举 | `'all'` \| `'component'` \| `'composable'` \| `'directive'` \| `'plugin'` \| `'type'` \| `'util'` \| `'edix'` \| `'i18n'` \| `'icon'` \| `'theme'`，默认 `'all'`。 |
| `domain` | 枚举 | `'all'` \| `'setup'` \| `'message'` \| `'rendering'` \| `'input'` \| `'agent'` \| `'feedback'` \| `'media'` \| `'helper'`，仅对 `kind: 'component'` 生效。 |

**返回值**

MCP 标准 `content` 数组，其中一条 `type: 'text'`，`text` 为 **JSON 字符串**，解析后结构大致为：

```json
{
  "components": [{ "name": "...", "slug": "...", "kind": "component", "domain": "message", "description": "..." }],
  "composables": [{ "name": "...", "slug": "...", "kind": "composable", "description": "..." }],
  "types": [{ "name": "...", "slug": "...", "kind": "type", "description": "..." }]
}
```

当 `kind` 为 `component` 时可继续用 `domain` 缩小能力域；其他 `kind` 不受 `domain` 影响。

**调用示例（语义）**

先调用 `list_components` 获取 `slug`，再传给 `get_component_doc`。

### `get_component_doc`

按 `slug` 读取 **已生成** 的 Markdown 文件内容（路径来自索引项中的 `docFile`）。

**参数**

| 字段   | 类型   | 说明                                                                        |
| ------ | ------ | --------------------------------------------------------------------------- |
| `slug` | string | 如 `chat-container`、`use-message-group`，可先通过 `list_components` 获取。 |

**返回值**

- 成功：`content[0].text` 为 **整篇文档字符串**（由 `readDocContent` 读取 `dist/mcp/generated/` 下文件；构建时会去掉 Wiki 中的 `<script setup>` 块，见 `build-index.ts` 的 `stripScriptSetup`）。
- 未找到：`isError: true`，`text` 为中文提示先调用 `list_components`。

文档中的 YAML frontmatter（若存在）会保留在生成文件中；**没有单独字段**拆分「AI 摘要」与正文，模型可直接从全文读取。

### `search_docs`

在 **所有索引条目** 的合并文本中做子串匹配（不区分大小写）。

**参数**

| 字段    | 类型   | 说明                                 |
| ------- | ------ | ------------------------------------ |
| `query` | string | 关键词，如「消息」「上传」「流式」。 |
| `limit` | number | 最大返回条数，默认 `5`。             |

**返回值**

`content[0].text` 为 JSON 字符串，结构示例：

```json
{
  "query": "消息",
  "resultCount": 3,
  "results": [
    {
      "name": "...",
      "slug": "...",
      "kind": "component",
      "domain": "message",
      "matches": ["...关键词附近的片段（最多 3 段）..."]
    }
  ]
}
```

`matches` 由 `extractMatchContext` 从清洗后的文档中截取关键词前后约 80 字符的上下文。

## 构建索引

在 **`packages/chat-x`** 目录执行（推荐与 `package.json` 脚本一致）：

```bash
pnpm mcp:build:index
```

等价于使用 `tsx` 运行 `mcp/scripts/build-index.ts`。完整发布前通常执行：

```bash
pnpm mcp:build
```

脚本会：

1. 扫描 `wikis/components/*/*.md`、`wikis/composables/*.md`、`wikis/types/*.md` 等索引目录（见 `build-index.ts` 中的 `GLOB_PATTERNS`）。
2. 去掉 `<script setup>...</script>`，将清洗后的正文写入 `dist/mcp/generated/docs/<slug>.md`。
3. 写入 **`dist/mcp/generated/index.json`**。

**`index.json` 结构（与 `doc-loader.ts` 中 `DocIndex` 一致）**

```json
{
  "version": "1.0.0",
  "generatedAt": "ISO-8601 时间戳",
  "components": [
    {
      "name": "从首行 # 标题解析",
      "slug": "文件名去掉 .md",
      "kind": "component",
      "domain": "setup | message | rendering | input | agent | feedback | media | helper",
      "description": "标题行内联描述或首段摘要",
      "docFile": "docs/<slug>.md"
    }
  ],
  "composables": [
    /* 同上，kind 为 composable */
  ],
  "types": [
    /* 同上，kind 为 type */
  ]
}
```

运行时 `loadIndex()` 会缓存该 JSON；`getAllEntries()` 合并三个数组供 `search_docs` 使用。

## 开发者指南

1. **新增可被 MCP 索引的文档**：在上述 **glob 覆盖的目录** 中新增 `.md`（文件名即 `slug`，勿与现有条目冲突）。`build-index.ts` 用正文里第一个 `#` 标题解析 `name` 与 `description`（不是单独解析 YAML 字段）。
2. **重新生成**：修改 Wiki 后执行 `pnpm mcp:build:index`（或 `pnpm mcp:build`），再重启 IDE 中的 MCP 进程以便重新读盘。
3. **`wikis/ai/` 等未纳入 glob 的页面**：当前 **不会** 进入 `index.json`；若希望 AI 能检索本页，需扩展 `mcp/scripts/build-index.ts` 的 `patterns`，或将内容同步到已扫描目录。
