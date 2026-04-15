# @blueking/chat-x

蓝鲸智云 AI Chat 组件库，提供了一套完整的 AI 对话交互组件，支持流式消息渲染、Markdown 内容展示、代码高亮、LaTeX 公式、Mermaid 图表等功能。

## 特性

- 🚀 **流式渲染** - 支持 AI 响应的流式输出，实时展示生成内容
- 📝 **Markdown 支持** - 完整的 Markdown 渲染，支持表格、代码块、任务列表等
- 🎨 **代码高亮** - 基于 highlight.js 的代码语法高亮
- 📐 **LaTeX 公式** - 支持行内和块级数学公式渲染
- 📊 **Mermaid 图表** - 支持流程图、时序图、甘特图等
- 💬 **消息交互** - 完整的消息展示、工具调用、用户反馈等功能
- 🎯 **快捷指令** - 支持自定义快捷指令和表单交互
- 🔧 **高度可定制** - 组件支持插槽和事件自定义

## 安装

```bash
# npm
npm install @blueking/chat-x

# pnpm
pnpm add @blueking/chat-x

# yarn
yarn add @blueking/chat-x
```

## 快速开始

```vue
<template>
  <div class="chat-container">
    <MessageContainer
      :messages="messages"
      :message-status="messageStatus"
      :on-agent-action="handleAgentAction"
      :on-user-action="handleUserAction"
      @stop-streaming="handleStopStreaming"
    />
    <ChatInput
      v-model="inputValue"
      :message-status="messageStatus"
      :on-send-message="handleSendMessage"
      :on-stop-sending="handleStopSending"
    />
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import {
  ChatInput,
  MessageContainer,
  MessageStatus,
  MessageRole,
  type Message
} from '@blueking/chat-x';

const inputValue = ref('');
const messageStatus = ref(MessageStatus.Complete);
const messages = ref<Message[]>([]);

const handleSendMessage = async (value: string) => {
  // 添加用户消息
  messages.value.push({
    id: Date.now().toString(),
    messageId: Date.now(),
    role: MessageRole.User,
    content: value,
    status: MessageStatus.Complete
  });
  
  // 清空输入框
  inputValue.value = '';
  
  // 调用 AI API...
};

const handleStopSending = () => {
  // 停止发送逻辑
};

const handleStopStreaming = () => {
  // 停止流式输出
};

const handleAgentAction = (tool) => {
  // 处理 AI 消息工具操作
};

const handleUserAction = (tool) => {
  // 处理用户消息工具操作
};
</script>
```

## 文档目录

### 开始
- [简介](./introduction.md)
- [快速上手](./getting-started.md)

### 组件

#### 原子组件
基础 UI 单元，是构建复杂组件的最小单位：

**交互组件**
- [ScrollBtn 滚动按钮](./components/atomic/scroll-btn.md)
- [ToolBtn 工具按钮](./components/atomic/tool-btn.md)
- [ShortcutBtn 快捷指令按钮](./components/atomic/shortcut-btn.md)
- [ShortcutBtns 快捷指令按钮组](./components/atomic/shortcut-btns.md)

**内容渲染组件**
- [MarkdownContent Markdown 内容渲染](./components/atomic/markdown-content.md)
- [CodeContent 代码块渲染](./components/atomic/code-content.md)
- [MermaidContent Mermaid 图表渲染](./components/atomic/mermaid-content.md)
- [LatexContent LaTeX 公式渲染](./components/atomic/latex-content.md)
- [ImageContent 图片渲染](./components/atomic/image-content.md)
- [AnimationText 动画文本](./components/atomic/animation-text.md)

#### 分子组件
由原子组件组合而成的复杂组件：
- [ChatInput 聊天输入框](./components/molecular/chat-input.md)
- [MessageContainer 消息容器](./components/molecular/message-container.md)
- [MessageRender 消息渲染器](./components/molecular/message-render.md)
- [ContentRender 内容渲染器](./components/molecular/content-render.md)
- [MessageTools 消息工具栏](./components/molecular/message-tools.md)
- [MessageUserFeedback 用户反馈](./components/molecular/user-feedback.md)
- [AiSelection AI 选择弹窗](./components/molecular/ai-selection.md)
- [ShortcutRender 快捷指令渲染器](./components/molecular/shortcut-render.md)
- [ToolcallRender 工具调用渲染器](./components/molecular/toolcall-render.md)

### 通用

#### Composables 组合式函数
- [useClipboard 剪贴板](./composables/use-clipboard.md)
- [useContainerScroll 容器滚动](./composables/use-container-scroll.md)
- [useAnimationText 动画文本](./composables/use-animation-text.md)
- [useCommandSelection 命令选择](./composables/use-command-selection.md)
- [useMenuKeydown 菜单键盘事件](./composables/use-menu-keydown.md)
- [useObserverVisibleList 可见列表监听](./composables/use-observer-visible-list.md)
- [useParentScrolling 父容器滚动](./composables/use-parent-scrolling.md)
- [useGlobalConfig 全局配置](./composables/use-global-config.md)

#### 指令
- [OverflowTips 溢出提示](./directives/overflow-tips.md)

#### 插件
- [markdownItLatex LaTeX 解析插件](./plugins/markdown-latex.md)
- [markdownItMermaid Mermaid 解析插件](./plugins/markdown-mermaid.md)

### 主题
- [主题配置](./theme/theme.md)

### 类型定义
- [消息类型](./types/messages.md)
- [常量枚举](./types/constants.md)

### 图标
- [图标使用指南](./icons/README.md)

### 工具函数
- [工具函数](./utils/README.md)

### 国际化
- [国际化](./i18n/README.md)

### 编辑器引擎
- [Edix 编辑器引擎](./edix/README.md)

## 依赖说明

组件库依赖以下第三方库：

| 依赖 | 版本 | 说明 |
|------|------|------|
| vue | ^3.5.24 | Vue 3 核心库 |
| bkui-vue | ^2.0.1 | 蓝鲸 UI 组件库 |
| highlight.js | ^11.11.1 | 代码高亮 |
| katex | ^0.16.27 | LaTeX 公式渲染 |
| mermaid | ^11.12.2 | 图表渲染 |
| dompurify | ^3.3.1 | HTML 安全过滤 |

## 浏览器兼容性

支持所有现代浏览器：

| Chrome | Firefox | Safari | Edge |
|--------|---------|--------|------|
| ✅ 最新版 | ✅ 最新版 | ✅ 最新版 | ✅ 最新版 |

## 许可证

MIT License - 详见 [LICENSE](../LICENSE)
