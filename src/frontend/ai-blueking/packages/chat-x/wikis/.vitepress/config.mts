import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { defineConfig } from 'vitepress';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const SSR_STUB = path.resolve(__dirname, 'ssr-stub.ts');
const SSR_STUB_PACKAGES = ['bkui-vue', 'mermaid', 'tippy.js', 'vue-tippy'];

/**
 * 仅在 SSR 模式下，把 bkui-vue / mermaid 等会在模块顶层访问 document/window
 * 的依赖重定向到 ssr-stub.ts，避免 vitepress build 时阻塞。
 * 浏览器水合阶段会重新加载真实模块，不影响最终运行。
 */
/**
 * vitepress build 会顺序跑 client + ssr 两次构建，且共用同一份 plugin 实例。
 * 通过 configResolved 的 build.ssr 标记区分当前阶段，仅在 SSR 构建时把
 * bkui-vue / mermaid / vue-tippy / tippy.js 重定向到本地 stub。
 *
 * 这些库会在模块顶层访问 document/window（如 bkui-vue 的
 * `document.addEventListener`、bkui-vue config-provider 的 `setPrefixVariable`
 * 同步访问 `document.documentElement`、mermaid 经 d3-selection 访问 document），
 * 在 Node SSR 环境中会立即抛 ReferenceError 阻塞 vitepress build。
 *
 * 只有包含真实 demo/SFC 的 Markdown 页面会延迟到 ClientOnly 渲染；
 * 纯文档页面保持 SSR 输出，避免静态 HTML 首屏正文为空。
 */
const createSsrStubPlugin = () => {
  let isSsr = false;
  return {
    name: 'chat-x-wiki:ssr-stub',
    enforce: 'pre' as const,
    configResolved(config: { build?: { ssr?: boolean | string } }) {
      isSsr = !!config?.build?.ssr;
    },
    resolveId(id: string) {
      if (!isSsr) return null;
      const matched = SSR_STUB_PACKAGES.some(pkg => id === pkg || id.startsWith(`${pkg}/`) || id.includes(`/${pkg}/`));
      return matched ? SSR_STUB : null;
    },
  };
};
const ssrStubPlugin = createSsrStubPlugin();
const FENCED_CODE_BLOCK_RE = /(^|\n)(`{3,}|~{3,})[^\n]*\n[\s\S]*?\n\2(?=\n|$)/g;
const CLIENT_ONLY_MARKERS = [/^<script\s+setup\b/m, /^<template\b/m, /<div\s+class=["']demo["']/];

const stripFencedCodeBlocks = (src: string) => src.replace(FENCED_CODE_BLOCK_RE, '\n');
const shouldRenderMarkdownInClientOnly = (src: string) => {
  const markdownBody = stripFencedCodeBlocks(src);
  return CLIENT_ONLY_MARKERS.some(marker => marker.test(markdownBody));
};

export default defineConfig({
  title: '蓝鲸 AI 对话组件库',
  description: '蓝鲸智云 AI Chat 组件库，专为构建 AI 对话交互界面设计',
  lang: 'zh-CN',

  srcExclude: ['README.md'],

  vite: {
    plugins: [ssrStubPlugin],
    resolve: {
      alias: {
        '@blueking/chat-x': path.resolve(__dirname, '../../src/index.ts'),
        'bkui-vue': path.resolve(__dirname, '../../node_modules/bkui-vue/lib/index.js'),
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
      { text: '搭建对话', link: '/components/setup/chat-container', activeMatch: '/components/setup/' },
      { text: '消息系统', link: '/components/message/message-render', activeMatch: '/components/message/' },
      {
        text: '内容渲染',
        link: '/components/rendering/content-render',
        activeMatch: '/components/rendering/|/components/medias/',
      },
      {
        text: '输入交互',
        link: '/components/input/chat-input',
        activeMatch: '/components/input/|/components/feedback/',
      },
      { text: 'Agent 能力', link: '/components/agent/toolcall-render', activeMatch: '/components/agent/|/ai/' },
      {
        text: '扩展开发',
        activeMatch:
          '/composables/|/directives/|/plugins/|/types/|/utils/|/edix/|/i18n/|/icons/|/theme/|/components/helper/',
        items: [
          { text: '组件总览', link: '/components/' },
          { text: '源码审计清单', link: '/components/inventory' },
          { text: 'MCP 服务', link: '/ai/mcp' },
          { text: '自定义消息类型', link: '/ai/custom-message' },
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
    config(md) {
      const defaultRender = md.render.bind(md);
      md.render = (src, env) => {
        const html = defaultRender(src, env);
        return shouldRenderMarkdownInClientOnly(src) ? `<ClientOnly>${html}</ClientOnly>` : html;
      };
    },
  },
});

/* ===================== 侧边栏配置 ===================== */

function sidebarAI() {
  return [
    {
      text: 'AI 专题',
      items: [
        { text: 'MCP 服务', link: 'mcp' },
        { text: '自定义消息类型', link: 'custom-message' },
        { text: '自定义侧栏 Tab 标签', link: 'custom-side-tab' },
        { text: '自定义侧栏内容', link: 'custom-side-content' },
        { text: '最佳实践', link: 'best-practices' },
      ],
    },
  ];
}

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
        { text: 'useArtifactPreview 文件产物预览', link: 'composables/use-artifact-preview' },
        { text: 'useFlowNodeActions 节点行尾操作', link: 'composables/use-flow-node-actions' },
        { text: 'useFullScreen 全屏控制', link: 'composables/use-full-screen' },
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
        { text: 'markdownItContainer', link: 'plugins/markdown-container' },
        { text: 'markdownItLatex', link: 'plugins/markdown-latex' },
        { text: 'markdownItMermaid', link: 'plugins/markdown-mermaid' },
      ],
    },
    {
      text: 'Types 类型定义',
      collapsed: false,
      items: [
        { text: '概览', link: 'types/' },
        { text: '常量枚举 Constants', link: 'types/constants' },
        { text: '中断类型 Interrupt', link: 'types/interrupt' },
        { text: '消息类型 Messages', link: 'types/messages' },
        { text: '用户问题 Schema', link: 'types/schema' },
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
      items: [
        { text: '组件总览', link: '' },
        { text: '源码审计清单', link: 'inventory' },
      ],
    },
    {
      text: '搭建对话',
      collapsed: false,
      items: [
        { text: 'ChatContainer 完整容器', link: 'setup/chat-container' },
        { text: 'MessageContainer 消息列表', link: 'setup/message-container' },
      ],
    },
    {
      text: '消息系统',
      collapsed: false,
      items: [
        { text: 'MessageRender 消息渲染器', link: 'message/message-render' },
        { text: 'AssistantMessage AI 助手消息', link: 'message/assistant-message' },
        { text: 'FileArtifactPanel 文件产物预览', link: 'message/file-artifact-panel' },
        { text: 'UserMessage 用户消息', link: 'message/user-message' },
        { text: 'ReasoningMessage 推理消息', link: 'message/reasoning-message' },
        { text: 'ToolMessage 工具消息', link: 'message/tool-message' },
        { text: 'ActivityMessage 活动消息', link: 'message/activity-message' },
        { text: 'InfoMessage 信息消息', link: 'message/info-message' },
        { text: 'LoadingMessage 加载消息', link: 'message/loading-message' },
      ],
    },
    {
      text: '内容渲染',
      collapsed: false,
      items: [
        { text: 'ContentRender 内容渲染器', link: 'rendering/content-render' },
        { text: 'MarkdownContent Markdown', link: 'rendering/markdown-content' },
        { text: 'CodeContent 代码块', link: 'rendering/code-content' },
        { text: 'LatexContent LaTeX 公式', link: 'rendering/latex-content' },
        { text: 'MermaidContent Mermaid 图表', link: 'rendering/mermaid-content' },
        { text: 'AnimationText 动画文本', link: 'rendering/animation-text' },
        { text: 'TextContent 文本内容', link: 'rendering/text-content' },
        { text: 'CiteContent 引用内容', link: 'rendering/cite-content' },
        { text: 'ReferenceContent 引用来源', link: 'rendering/reference-content' },
        { text: 'KeyValueContent 键值内容', link: 'rendering/key-value-content' },
        { text: 'DescPanel 描述面板', link: 'rendering/desc-panel' },
        { text: 'CommonErrorContent 错误内容', link: 'rendering/common-error-content' },
      ],
    },
    {
      text: '媒体文件',
      collapsed: false,
      items: [
        { text: 'AiImage 图片展示', link: 'medias/ai-image' },
        { text: 'ImagePreview 图片预览', link: 'medias/image-preview' },
        { text: 'ImagePreviewGroup 图片预览组', link: 'medias/image-preview-group' },
        { text: 'PreviewToolbar 预览工具栏', link: 'medias/preview-toolbar' },
        { text: 'FileContent 文件内容', link: 'medias/file-content' },
        { text: 'ImageContent 图片内容', link: 'medias/image-content' },
      ],
    },
    {
      text: '输入交互',
      collapsed: false,
      items: [
        { text: 'ChatInput 聊天输入框', link: 'input/chat-input' },
        { text: 'AiSlashInput 富文本命令输入', link: 'input/ai-slash-input' },
        { text: 'AiSlashEditor 富文本编辑器', link: 'input/ai-slash-editor' },
        { text: 'AiSlashMenu 资源菜单', link: 'input/ai-slash-menu' },
        { text: 'AiSkillList Skill 列表', link: 'input/ai-skill-list' },
        { text: 'AiPromptList Prompt 列表', link: 'input/ai-prompt-list' },
        { text: 'InputAttachment 输入附件区', link: 'input/input-attachment' },
        { text: 'ModelSelector 模型选择器', link: 'input/model-selector' },
        { text: 'InputInfoAlert 输入提示条', link: 'input/input-info-alert' },
        { text: 'FileUploadBtn 文件上传按钮', link: 'input/file-upload-btn' },
        { text: 'ShortcutRender 快捷指令表单', link: 'input/shortcut-render' },
        { text: 'ShortcutBtn 快捷指令按钮', link: 'input/shortcut-btn' },
        { text: 'ShortcutBtns 快捷指令按钮组', link: 'input/shortcut-btns' },
        { text: 'AiSelection 划词选择', link: 'input/ai-selection' },
        { text: 'SelectionFooter 多选操作栏', link: 'input/selection-footer' },
      ],
    },
    {
      text: 'Agent 能力',
      collapsed: false,
      items: [
        { text: 'ToolcallRender 工具调用渲染器', link: 'agent/toolcall-render' },
        { text: 'ToolApprovalCard 工具审批', link: 'agent/tool-approval-card' },
        { text: 'InterruptMessage 中断消息', link: 'agent/interrupt-message' },
        { text: 'UserQuestionCard 用户问题', link: 'agent/user-question-card' },
        { text: 'UserQuestionChoice 选择题', link: 'agent/user-question-choice' },
        { text: 'UserQuestionAnsweredCard 回答回显', link: 'agent/user-question-answered-card' },
        { text: 'UserQuestionOption 问题选项', link: 'agent/user-question-option' },
        { text: 'ExecutionSummary 执行摘要', link: 'agent/execution-summary' },
        { text: 'FlowAgentContent 执行内容', link: 'agent/flow-agent-content' },
        { text: 'FlowAgentNodeDetail 节点详情', link: 'agent/flow-agent-node-detail' },
        { text: 'KnowledgeRagContent 知识召回', link: 'agent/knowledge-rag-content' },
        { text: 'ReferenceDocContent 引用文档活动', link: 'agent/reference-doc-content' },
        { text: 'DetailSection 详情分段', link: 'agent/detail-section' },
        { text: 'SimpleTable 简易表格', link: 'agent/simple-table' },
      ],
    },
    {
      text: '工具与反馈',
      collapsed: false,
      items: [
        { text: 'MessageTools 消息工具栏', link: 'feedback/message-tools' },
        { text: 'ToolBtn 工具按钮', link: 'feedback/tool-btn' },
        { text: 'DeleteTool 删除确认', link: 'feedback/delete-tool' },
        { text: 'UserFeedback 用户反馈', link: 'feedback/user-feedback' },
        { text: 'ScrollBtn 滚动按钮', link: 'feedback/scroll-btn' },
      ],
    },
    {
      text: '辅助能力',
      collapsed: false,
      items: [
        { text: 'ActivityLayout 活动布局', link: 'helper/activity-layout' },
        { text: 'AiLoading 三点加载', link: 'helper/ai-loading' },
        { text: 'MessageLoading 品牌加载', link: 'helper/message-loading' },
        { text: 'HighlightKeyword 关键词高亮', link: 'helper/highlight-keyword' },
        { text: 'FileIcon 文件类型图标', link: 'helper/file-icon' },
        { text: 'VNodeRenderer VNode 渲染器', link: 'helper/vnode-renderer' },
        { text: 'QuestionsContainer 空占位', link: 'helper/questions-container' },
        { text: 'SelectionQuestion 空占位', link: 'helper/selection-question' },
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
