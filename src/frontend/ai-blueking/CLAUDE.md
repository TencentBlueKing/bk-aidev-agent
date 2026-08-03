# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

AI Blueking Monorepo 是一个 pnpm workspace monorepo，包含 AI 小鲸智能对话组件的完整生态。

## Project Structure

```
packages/
├── ai-blueking/          ← @blueking/ai-blueking v2.1.0 — 小鲸业务组件（Vue2/Vue3 双构建）
│   ├── src/              ← 源码（AIHeader、ChatBot、DraggableContainer 等）
│   ├── scripts/          ← Vite 构建脚本（Vue3 external / Vue2 从源码编译）
│   └── playground/       ← 开发调试
├── chat-x/               ← @blueking/chat-x v0.0.19 — 原子对话 UI 组件库（独立使用）
│   ├── src/              ← 对话能力组件（ChatInput、MessageContainer、ContentRender 等）
│   ├── mcp/              ← MCP 工具子模块
│   └── wikis/            ← VitePress 文档
├── chat-helper/          ← @blueking/chat-helper v0.0.1-beta.36 — 工具库（HTTP、消息管理）
├── mcp/                  ← MCP（保留）
├── playground/           ← Vue3 全局开发调试
└── vue2-playground/      ← Vue2 开发调试
```

## Dependency Graph

```
@blueking/ai-blueking
  ├─ peerDep: vue ^3.5.24, @blueking/chat-x >=0.0.19
  └─ dep: @blueking/chat-helper, bkui-vue, tippy.js, vue-draggable-resizable, vue-tippy

@blueking/chat-x
  └─ devDep: @blueking/chat-helper workspace:*
```

## Environment Setup

Node.js v20 + ppm. Always run before development:

```bash
nvm use v20    # Switch to Node.js v20
pnpm install   # Install dependencies
```

## Development Commands

```bash
# AI Blueking (小鲸组件)
pnpm dev:ai              # Start ai-blueking dev server
pnpm build:ai            # Build ai-blueking (Vue3 + Vue2)

# Chat X (对话组件库)
pnpm dev:ui              # Start chat-x dev server
pnpm build:ui            # Build chat-x
pnpm test:ui             # Test chat-x

# Chat Helper (工具库)
pnpm dev:helper          # Start chat-helper dev
pnpm build:helper        # Build chat-helper

# MCP
pnpm build:mcp           # Build MCP
pnpm dev:mcp             # Dev MCP

# Lint
pnpm lint:ui             # Lint chat-x
pnpm lint:ai             # Lint ai-blueking
```

## Architecture Notes

### Vue2/Vue3 Dual Build Strategy (packages/ai-blueking)

- **Vue3 构建**: `@blueking/chat-x` external，消费方自行安装，避免 mermaid 等重依赖撑大包体积
- **Vue2 构建**: `@blueking/chat-x` 从源码编译（alias `../../chat-x/src`），保证响应式同源
- **createVue2Wrapper**: 在 Vue2 Options API 组件内嵌 Vue3 `createApp` 渲染，桥接 props/emit/expose/slots
- **CSS 合并**: Vue3 通过 `import '../../chat-x/dist/index.css'` 合并进 `style.css`

### Key Patterns

- **Composition API**: Heavy use of Vue 3 composables
- **Type Safety**: Full TypeScript with strict configuration
- **chat-x is peerDep**: Must remain as peerDependency to control bundle size (mermaid, katex, etc.)
- **workspace:\***: chat-helper uses `workspace:*` protocol for local development
- **I18n**: Built-in internationalization with Chinese as primary language

## Skill 同步（必读）

对外语义变更后，必须更新仓库内两个 Skill 工作副本，再按需同步到 `skills-manager-backup`：

| Skill                     | 路径（相对本 monorepo）                                |
| ------------------------- | ------------------------------------------------------ |
| `ai-blueking-dev`         | `packages/ai-blueking/skills/ai-blueking-dev/`         |
| `ai-blueking-docs-update` | `packages/ai-blueking/skills/ai-blueking-docs-update/` |

详见仓库根 `.cursor/rules/ai-blueking-skill-sync.mdc` 与 `.cursor/skills/ai-blueking-skill-sync/`。
