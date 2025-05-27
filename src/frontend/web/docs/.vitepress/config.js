import { defineConfig } from 'vitepress'
import { version } from '../../package.json'
import container from 'markdown-it-container'

export default defineConfig({
  title: 'AI 小鲸',
  description: '智能对话组件文档',
  lang: 'zh-CN',
  outDir: '../dist',
  themeConfig: {
    logo: '/ai-logo.svg',
    nav: [
      { text: '指南', link: '/guide/introductions', activeMatch: '/guide/' },
      { text: 'API 文档', link: '/api/props', activeMatch: '/api/' },
      { text: '示例', link: '/demos/basic-usage', activeMatch: '/demos/' },
      { text: '更新日志', link: '/changelog' },
      { text: '常见问题', link: '/faq' },
      { 
        text: version,
        items: [
          { text: '更新日志', link: '/changelog' },
          { text: '1.0迁移指南', link: '/guide/migration-1.0' },
          { text: 'Magic Box', link: 'https://magicbox.bk.tencent.com/static_api/v3/main/index.html' }
        ]
      }
    ],
    
    sidebar: {
      '/guide': [
        {
          text: '简介',
          items: [
            { text: '组件介绍', link: '/guide/introductions' },
            { text: '快速开始', link: '/guide/quick-start' },
          ]
        },
        {
          text: '核心功能',
          items: [
            { text: '聊天交互', link: '/guide/core-features/chat-interaction' },
            { text: '内容引用', link: '/guide/core-features/content-referencing' },
            { text: '提示词', link: '/guide/core-features/prompts' },
            { text: 'UI 定制', link: '/guide/core-features/ui-customization' }
          ]
        },
        {
          text: '高级用法',
          items: [
            { text: '自定义请求', link: '/guide/advanced-usage/custom-requests' },
            { text: '会话管理', link: '/guide/advanced-usage/session-access' },
            { text: '预设对话内容', link: '/guide/advanced-usage/default-messages' },
            { text: '编程控制', link: '/guide/advanced-usage/programmatic-control' }
          ]
        },
        {
          text: '版本迁移',
          items: [
            { text: '迁移到 1.0 版本', link: '/guide/migration-1.0' }
          ]
        },
        {
          text: '框架集成', link: '/guide/framework-integration'
        }, 
        { text: '使用示例', link: '/demos/basic-usage' }
      ],
      '/api': [
        {
          text: 'API 文档',
          items: [
            { text: '属性', link: '/api/props' },
            { text: '事件', link: '/api/events' },
            { text: '方法', link: '/api/methods' }
          ]
        }
      ],
      '/demos/': [
        {
          text: '示例',
          items: [
            { text: '基础使用', link: '/demos/basic-usage' },
            { text: '快捷操作', link: '/demos/shortcuts-demo' },
            { text: '提示词', link: '/demos/prompts-demo' },
          ]
        }
      ]
    },
    
    socialLinks: [
      { icon: 'github', link: 'https://github.com/TencentBlueKing/bk-aidev-agent' }
    ],
    
    footer: {
      message: 'All Rights Reserved. 腾讯蓝鲸 版权所有',
      copyright: 'Copyright © 2025 Blueking'
    },
    search: {
      provider: 'local',
    }
    
    // algolia: {
    //   appId: 'YOUR_APP_ID',
    //   apiKey: 'YOUR_API_KEY',
    //   indexName: 'ai-blueking'
    // }
  },
  markdown: {
    config(md) {
      md.use(container, 'demo', {
        validate(params) {
          return params.trim().match(/^demo\s*(.*)$/)
        },
        render(tokens, idx) {
          const m = tokens[idx].info.trim().match(/^demo\s*(.*)$/)
          if (tokens[idx].nesting === 1) {
            const description = m && m.length > 1 ? m[1] : ''
            return `<DemoContainer description="${md.utils.escapeHtml(description)}">`
          }
          return '</DemoContainer>'
        }
      })
    }
  },
  vite: {
    ssr: {
      // Add the problematic package(s) here
      // It seems @blueking/ai-blueking imports bkui-vue,
      // so it's often necessary to include both.
      noExternal: ['@blueking/ai-blueking', 'bkui-vue']
    },
    envPrefix: 'BK_',
    define: {
      'process.env.BK_STATIC_URL': JSON.stringify(process.env.BK_STATIC_URL),
      'process.env.BK_SITE_URL': JSON.stringify(process.env.BK_SITE_URL),
      'process.env.BK_API_URL_TMPL': JSON.stringify(process.env.BK_API_URL_TMPL),
      'process.env.BK_API_GATEWAY_NAME': JSON.stringify(process.env.BK_API_GATEWAY_NAME),
    }
  }
}) 