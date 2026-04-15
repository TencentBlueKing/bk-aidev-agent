---
layout: home

hero:
  name: '@blueking/chat-x'
  text: AI 优先的对话组件库
  tagline: 基于 Vue 3 + TypeScript，为 AI Agent 和人类开发者共同设计。结构化元数据 + MCP 服务让 AI 在 1-2 次调用内选组件，流式渲染 + 20+ 消息角色 + 多级内容管线让人类快速构建专业对话界面
  actions:
    - theme: brand
      text: 快速上手
      link: /getting-started
    - theme: alt
      text: 组件文档
      link: /components/

features:
  - icon: 🤖
    title: AI 优先设计
    details: 每个组件均携带结构化 frontmatter 和 AI 专用摘要（aiSummary），内置 MCP Server 让 AI IDE 通过标准协议直接查询文档，AI Agent 无需阅读全文即可精准选择组件
  - icon: 🧠
    title: MCP 服务
    details: 内置 list_components（按功能域过滤）、get_component_doc（含 AI 摘要）、search_docs 三个工具，Cursor 等 AI IDE 可即插即用
  - icon: ⚡
    title: 流式渲染
    details: 原生支持 AI 响应的实时流式输出，逐字渲染并自动补全 Markdown 语法，MessageStatus 管理消息完整生命周期
  - icon: 💬
    title: 20+ 消息角色
    details: 覆盖 User、Assistant、Tool、Reasoning、Activity、Info、Loading 等全部 AI 对话场景，支持 declare global 零侵入扩展自定义角色
  - icon: 📝
    title: 多级内容管线
    details: ContentRender → MarkdownContent → CodeContent / LatexContent / MermaidContent，按 token 类型自动分发，支持 180+ 语言代码高亮
  - icon: 🧩
    title: 渐进式组合
    details: 最小组合 ChatInput + MessageContainer，完整方案 ChatContainer 一行搞定。原子/分子分层设计，按需引入
  - icon: 🔧
    title: 快捷指令与斜杠命令
    details: 内置 / 和 @ 触发的命令系统，支持文本、数字、下拉、复选等表单组件，一键发起结构化对话
  - icon: ✂️
    title: 划词选择
    details: AiSelection 监听页面文本选中，弹出快捷操作浮窗，支持解释、翻译、总结等自定义划词操作
  - icon: 🖼️
    title: 图片与文件
    details: 文件上传、图片展示、全屏预览、多图管理，内置下载与错误重试，ImagePreviewGroup 通过 provide/inject 管理
---
