import { createRequire } from "node:module"
import { defineConfig } from "vitepress"
import express from "express"
import { version } from "../../../ai-blueking/packages/ai-blueking/package.json"
import container from "markdown-it-container"

const base = process.env.VITEPRESS_BASE || '__DOCS_BASE__/'
const require = createRequire(import.meta.url)
const { createMockAguiRouter } = require("./mock-agui-routes.cjs")

export default defineConfig({
  title: "AI 小鲸",
  description: "智能对话组件文档 — v2.1",
  lang: "zh-CN",
  base,
  /** 文档内嵌 bkui-vue / chat-x 等组件仅针对浅色主题调优，固定浅色避免深色模式样式错乱 */
  appearance: false,
  outDir: "../dist",
  themeConfig: {
    logo: "/ai-logo.svg",
    nav: [
      { text: "指南", link: "/guide/introductions", activeMatch: "/guide/" },
      { text: "API 文档", link: "/api/overview", activeMatch: "/api/" },
      { text: "示例", link: "/demos/full-panel", activeMatch: "/demos/" },
      { text: "更新日志", link: "/changelog" },
      { text: "常见问题", link: "/faq" },
      {
        text: version,
        items: [
          { text: "更新日志", link: "/changelog" },
          { text: "v1.x → v2.0 迁移指南", link: "/guide/migration-2.0" },
        ],
      },
    ],

    sidebar: {
      "/guide/": [
        {
          text: "开始",
          items: [
            { text: "组件介绍", link: "/guide/introductions" },
            { text: "快速开始", link: "/guide/quick-start" },
          ],
        },
        {
          text: "集成模式",
          items: [
            { text: "AIBlueking 浮窗模式", link: "/guide/integration-modes/aiblueking-floating" },
            { text: "ChatBot 页面嵌入模式", link: "/guide/integration-modes/chatbot-embedded" },
            { text: "原子组件组装", link: "/guide/integration-modes/atomic-composition" },
          ],
        },
        {
          text: "功能说明",
          items: [
            { text: "聊天交互", link: "/guide/core-features/chat-interaction" },
            { text: "内容引用", link: "/guide/core-features/content-referencing" },
            { text: "快捷指令", link: "/guide/core-features/shortcuts" },
            { text: "提示词与资源", link: "/guide/core-features/prompts" },
            { text: "会话管理", link: "/guide/core-features/session-management" },
            { text: "消息分享", link: "/guide/core-features/sharing" },
            { text: "消息自定义渲染", link: "/guide/core-features/custom-message-rendering" },
            { text: "UI 定制", link: "/guide/core-features/ui-customization" },
            { text: "Skill 指引", link: "/guide/core-features/skill-guide" },
          ],
        },
        {
          text: "高级用法",
          items: [
            { text: "自定义会话列表", link: "/guide/advanced-usage/external-session-list" },
            { text: "自定义请求", link: "/guide/advanced-usage/custom-requests" },
            { text: "编程式控制", link: "/guide/advanced-usage/programmatic-control" },
            { text: "多 Agent 切换", link: "/guide/advanced-usage/multi-agent-switching" },
          ],
        },
        {
          text: "架构与内部设计",
          collapsed: true,
          items: [
            { text: "架构概览", link: "/guide/architecture" },
            { text: "Manager 模式", link: "/guide/internals/manager-pattern" },
            { text: "事件系统", link: "/guide/internals/event-system" },
            { text: "初始化生命周期", link: "/guide/internals/chat-bootstrap" },
            { text: "消息属性系统", link: "/guide/internals/message-property" },
          ],
        },
        {
          text: "版本迁移",
          items: [{ text: "从 v1.x 迁移到 v2.0", link: "/guide/migration-2.0" }],
        },
      ],
      "/api/": [
        { text: "API 概览", link: "/api/overview" },
        {
          text: "@blueking/ai-blueking",
          collapsed: false,
          items: [
            { text: "ChatBot 组件", link: "/api/ai-blueking/chatbot" },
            { text: "AIBlueking 组件", link: "/api/ai-blueking/aiblueking" },
            { text: "业务管理器", link: "/api/ai-blueking/managers" },
            { text: "类型定义", link: "/api/ai-blueking/types" },
          ],
        },
        {
          text: "@blueking/chat-x",
          collapsed: false,
          items: [
            { text: "UI 组件", link: "/api/chat-x/components" },
            { text: "类型定义", link: "/api/chat-x/types" },
          ],
        },
        {
          text: "@blueking/chat-helper",
          collapsed: false,
          items: [
            { text: "SDK 模块", link: "/api/chat-helper/sdk" },
            { text: "类型定义", link: "/api/chat-helper/types" },
          ],
        },
      ],
      "/demos/": [
        {
          text: "示例",
          items: [
            { text: "AIBlueking 浮窗模式", link: "/demos/full-panel" },
            { text: "ChatBot 页面嵌入", link: "/demos/basic-usage" },
            { text: "原子组件组装", link: "/demos/atomic-assembly" },
          ],
        },
      ],
    },

    socialLinks: [{ icon: "github", link: "https://github.com/TencentBlueKing/bk-aidev-agent" }],

    footer: {
      message: "All Rights Reserved. 腾讯蓝鲸 版权所有",
      copyright: "Copyright © 2025 Blueking",
    },
    search: {
      provider: "local",
    },
  },
  markdown: {
    config(md) {
      md.use(container, "demo", {
        validate(params) {
          return params.trim().match(/^demo\s*(.*)$/)
        },
        render(tokens, idx) {
          const m = tokens[idx].info.trim().match(/^demo\s*(.*)$/)
          if (tokens[idx].nesting === 1) {
            const description = m && m.length > 1 ? m[1] : ""
            return `<DemoContainer description="${md.utils.escapeHtml(description)}">`
          }
          return "</DemoContainer>"
        },
      })
    },
  },
  vite: {
    plugins: [
      {
        name: "mock-agui-api",
        configureServer(server) {
          const mount = express.Router()
          mount.use(express.json())
          mount.use(createMockAguiRouter())
          server.middlewares.use("/mock-agui/api", mount)
        },
      },
    ],
    ssr: {
      noExternal: [
        "@blueking/ai-blueking",
        "@blueking/chat-x",
        "@blueking/chat-helper",
        "bkui-vue",
      ],
    },
    envPrefix: "BK_",
    define: {
      "process.env.BK_STATIC_URL": JSON.stringify(process.env.BK_STATIC_URL),
      "process.env.BK_SITE_URL": JSON.stringify(process.env.BK_SITE_URL),
      "process.env.BK_API_URL_TMPL": JSON.stringify(process.env.BK_API_URL_TMPL),
      "process.env.BK_API_GATEWAY_NAME": JSON.stringify(process.env.BK_API_GATEWAY_NAME),
      "process.env.BK_AIDEV_URL": JSON.stringify(process.env.BK_AIDEV_URL),
    },
  },
})
