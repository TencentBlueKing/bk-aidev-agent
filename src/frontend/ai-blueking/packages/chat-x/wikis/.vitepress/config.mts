import path from 'path';
import { fileURLToPath } from 'url';
import { defineConfig } from 'vitepress';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  title: '蓝鲸 AI 对话组件库',
  description: '蓝鲸智云 AI Chat 组件库，专为构建 AI 对话交互界面设计',
  lang: 'zh-CN',

  srcExclude: ['README.md'],

  vite: {
    resolve: {
      alias: {
        '@blueking/chat-x': path.resolve(__dirname, '../../src/index.ts'),
      },
    },
  },

  themeConfig: {
    siteTitle: '@blueking/chat-x',

    nav: [
      {
        text: '指南',
        link: '/introduction',
        activeMatch: '/introduction|/getting-started|/architecture|/design-philosophy|/recipes',
      },
      { text: '组件', link: '/components/', activeMatch: '/components/' },
      { text: 'AI 专题', link: '/ai/mcp', activeMatch: '/ai/' },
      {
        text: 'API 参考',
        activeMatch: '/composables/|/directives/|/plugins/|/types/|/utils/|/edix/|/i18n/|/icons/|/theme/',
        items: [
          { text: 'Composables 组合式函数', link: '/composables/' },
          { text: 'Directives 指令', link: '/directives/' },
          { text: 'Plugins 插件', link: '/plugins/' },
          { text: 'Types 类型定义', link: '/types/' },
          { text: 'Utils 工具函数', link: '/utils/' },
          { text: 'Edix 编辑器引擎', link: '/edix/' },
          { text: 'I18n 国际化', link: '/i18n/' },
          { text: 'Icons 图标', link: '/icons/' },
          { text: 'Theme 主题', link: '/theme/' },
        ],
      },
    ],

    sidebar: {
      // 指南
      '/introduction': { base: '/', items: sidebarGuide() },
      '/getting-started': { base: '/', items: sidebarGuide() },
      '/architecture': { base: '/', items: sidebarGuide() },
      '/design-philosophy': { base: '/', items: sidebarGuide() },
      '/recipes': { base: '/', items: sidebarGuide() },

      // 组件
      '/components/': { base: '/components/', items: sidebarComponents() },

      // AI 专题
      '/ai/': { base: '/ai/', items: sidebarAI() },

      // API 参考各模块共享侧边栏
      '/composables/': { base: '/', items: sidebarAPI() },
      '/directives/': { base: '/', items: sidebarAPI() },
      '/plugins/': { base: '/', items: sidebarAPI() },
      '/types/': { base: '/', items: sidebarAPI() },
      '/utils/': { base: '/', items: sidebarAPI() },
      '/edix/': { base: '/', items: sidebarAPI() },
      '/i18n/': { base: '/', items: sidebarAPI() },
      '/icons/': { base: '/', items: sidebarAPI() },
      '/theme/': { base: '/', items: sidebarAPI() },
    },

    search: {
      provider: 'local',
      options: {
        translations: {
          button: { buttonText: '搜索文档', buttonAriaLabel: '搜索文档' },
          modal: {
            noResultsText: '无法找到相关结果',
            resetButtonTitle: '清除查询条件',
            footer: { selectText: '选择', navigateText: '切换', closeText: '关闭' },
          },
        },
      },
    },

    outline: {
      label: '页面导航',
      level: [2, 3],
    },

    docFooter: {
      prev: '上一页',
      next: '下一页',
    },

    lastUpdated: {
      text: '最后更新于',
    },

    returnToTopLabel: '回到顶部',
    sidebarMenuLabel: '菜单',
    darkModeSwitchLabel: '主题',
    lightModeSwitchTitle: '切换到浅色模式',
    darkModeSwitchTitle: '切换到深色模式',
  },
  markdown: {
    theme: 'github-dark',
  },
});

/* ===================== 侧边栏配置 ===================== */

function sidebarAPI() {
  return [
    {
      text: 'Composables 组合式函数',
      collapsed: false,
      items: [
        { text: '概览', link: 'composables/' },
        { text: 'useClipboard 剪贴板', link: 'composables/use-clipboard' },
        { text: 'useContainerScroll 滚动控制', link: 'composables/use-container-scroll' },
        { text: 'useAnimationText 文本动画', link: 'composables/use-animation-text' },
        { text: 'useMessageGroup 消息分组', link: 'composables/use-message-group' },
        { text: 'useCustomTab 自定义 Tab', link: 'composables/use-custom-tab' },
        { text: 'useCommandSelection 命令选择', link: 'composables/use-command-selection' },
        { text: 'useMenuKeydown 菜单键盘', link: 'composables/use-menu-keydown' },
        { text: 'useObserverVisibleList 可见列表', link: 'composables/use-observer-visible-list' },
        { text: 'useParentScrolling 父级滚动', link: 'composables/use-parent-scrolling' },
        { text: 'useGlobalConfig 全局配置', link: 'composables/use-global-config' },
      ],
    },
    {
      text: 'Directives 指令',
      collapsed: false,
      items: [
        { text: '概览', link: 'directives/' },
        { text: 'v-overflow-tips', link: 'directives/overflow-tips' },
      ],
    },
    {
      text: 'Plugins Markdown 插件',
      collapsed: false,
      items: [
        { text: '概览', link: 'plugins/' },
        { text: 'markdownItLatex', link: 'plugins/markdown-latex' },
        { text: 'markdownItMermaid', link: 'plugins/markdown-mermaid' },
      ],
    },
    {
      text: 'Types 类型定义',
      collapsed: false,
      items: [
        { text: '概览', link: 'types/' },
        { text: '消息类型 Messages', link: 'types/messages' },
        { text: '常量枚举 Constants', link: 'types/constants' },
      ],
    },
    {
      text: 'Utils 工具函数',
      items: [{ text: '工具函数', link: 'utils/' }],
    },
    {
      text: 'Edix 编辑器引擎',
      items: [{ text: '编辑器引擎', link: 'edix/' }],
    },
    {
      text: 'I18n 国际化',
      items: [{ text: '国际化', link: 'i18n/' }],
    },
    {
      text: 'Icons 图标',
      items: [{ text: '图标', link: 'icons/' }],
    },
    {
      text: 'Theme 主题',
      items: [
        { text: '概览', link: 'theme/' },
        { text: '主题配置', link: 'theme/theme' },
      ],
    },
  ];
}

function sidebarComponents() {
  return [
    {
      text: '概览',
      items: [{ text: '组件总览', link: '' }],
    },
    {
      text: '消息展示',
      collapsed: false,
      items: [
        { text: 'MessageContainer 消息容器', link: 'molecular/message-container' },
        { text: 'MessageRender 消息渲染器', link: 'molecular/message-render' },
        { text: 'AssistantMessage AI 助手消息', link: 'molecular/assistant-message' },
        { text: 'UserMessage 用户消息', link: 'molecular/user-message' },
        { text: 'ReasoningMessage 推理消息', link: 'molecular/reasoning-message' },
        { text: 'ToolMessage 工具消息', link: 'molecular/tool-message' },
        { text: 'ActivityMessage 活动消息', link: 'molecular/activity-message' },
        { text: 'InfoMessage 信息消息', link: 'molecular/info-message' },
        { text: 'LoadingMessage 加载消息', link: 'molecular/loading-message' },
      ],
    },
    {
      text: '输入交互',
      collapsed: false,
      items: [
        { text: 'ChatInput 聊天输入框', link: 'molecular/chat-input' },
        { text: 'AiSelection AI 选择弹窗', link: 'molecular/ai-selection' },
        { text: 'ShortcutRender 快捷指令渲染器', link: 'molecular/shortcut-render' },
        { text: 'ShortcutBtn 快捷指令按钮', link: 'atomic/shortcut-btn' },
        { text: 'ShortcutBtns 快捷指令按钮组', link: 'atomic/shortcut-btns' },
        { text: 'ChatContainer 聊天容器', link: 'molecular/chat-container' },
      ],
    },
    {
      text: '内容渲染',
      collapsed: false,
      items: [
        { text: 'ContentRender 内容渲染器', link: 'molecular/content-render' },
        { text: 'MarkdownContent Markdown', link: 'atomic/markdown-content' },
        { text: 'CodeContent 代码块', link: 'atomic/code-content' },
        { text: 'LatexContent LaTeX 公式', link: 'atomic/latex-content' },
        { text: 'MermaidContent Mermaid 图表', link: 'atomic/mermaid-content' },
        { text: 'AnimationText 动画文本', link: 'atomic/animation-text' },
      ],
    },
    {
      text: '文件与图片',
      collapsed: false,
      items: [
        { text: 'AiImage 图片展示', link: 'atomic/ai-image' },
        { text: 'ImagePreview 图片预览', link: 'molecular/image-preview' },
        { text: 'ImagePreviewGroup 图片预览组', link: 'molecular/image-preview-group' },
        { text: 'FileContent 文件内容', link: 'molecular/file-content' },
        { text: 'ImageContent 图片内容', link: 'atomic/image-content' },
        { text: 'FileUploadBtn 文件上传按钮', link: 'atomic/file-upload-btn' },
      ],
    },
    {
      text: '工具与反馈',
      collapsed: false,
      items: [
        { text: 'MessageTools 消息工具栏', link: 'molecular/message-tools' },
        { text: 'ToolBtn 工具按钮', link: 'atomic/tool-btn' },
        { text: 'UserFeedback 用户反馈', link: 'molecular/user-feedback' },
        { text: 'ToolcallRender 工具调用渲染器', link: 'molecular/toolcall-render' },
        { text: 'DeleteTool 删除确认按钮', link: 'molecular/delete-tool' },
      ],
    },
    {
      text: '辅助组件',
      collapsed: false,
      items: [
        { text: 'ScrollBtn 滚动按钮', link: 'atomic/scroll-btn' },
        { text: 'DescPanel 描述面板', link: 'atomic/desc-panel' },
        { text: 'HighlightKeyword 关键词高亮', link: 'atomic/highlight-keyword' },
        { text: 'CiteContent 引用内容', link: 'atomic/cite-content' },
        { text: 'TextContent 文本内容', link: 'atomic/text-content' },
        { text: 'KeyValueContent 键值对内容', link: 'atomic/key-value-content' },
        { text: 'ReferenceContent 引用文档', link: 'atomic/reference-content' },
        { text: 'CommonErrorContent 错误内容', link: 'atomic/common-error-content' },
        { text: 'AiLoading 加载动画', link: 'atomic/ai-loading' },
        { text: 'ExecutionSummary 执行摘要', link: 'molecular/execution-summary' },
        { text: 'SelectionFooter 选择操作栏', link: 'atomic/selection-footer' },
      ],
    },
  ];
}

function sidebarGuide() {
  return [
    {
      text: '基础',
      items: [
        { text: '简介', link: 'introduction' },
        { text: '快速上手', link: 'getting-started' },
      ],
    },
    {
      text: '深入',
      items: [
        { text: '架构总览', link: 'architecture' },
        { text: '设计理念', link: 'design-philosophy' },
        { text: '用例食谱', link: 'recipes' },
      ],
    },
  ];
}

function sidebarAI() {
  return [
    {
      text: 'AI 专题',
      items: [
        { text: 'MCP 服务', link: 'mcp' },
        { text: '自定义消息类型', link: 'custom-message' },
        { text: '最佳实践', link: 'best-practices' },
      ],
    },
  ];
}
