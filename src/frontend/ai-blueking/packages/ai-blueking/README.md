<p align="center">
  <img src="./assets/ai-logo.svg" alt="AI 小鲸" width="128" height="128">
</p>

<h1 align="center">@blueking/ai-blueking</h1>

<p align="center">
  AI 小鲸 V2 - 基于新架构的智能对话组件
</p>

<p align="center">
  <a href="https://github.com/blueking/ai-blueking"><img src="https://img.shields.io/badge/版本-2.1.0-blue" alt="版本"></a>
  <a href="./LICENSE"><img src="https://img.shields.io/badge/许可证-MIT-green" alt="许可证"></a>
</p>

## 简介

AI-Blueking V2 是小鲸组件的重构版本，采用全新的三层架构设计，提供了更灵活、更易维护的智能对话解决方案。

### 核心特性

- **模块化设计** - 清晰的职责划分，易于维护和扩展
- **两种使用方式** - 完整组件（AIBlueking）和可嵌入的 ChatBot
- **业务管理器** - 统一的业务逻辑封装
- **类型安全** - 完整的 TypeScript 类型定义
- **事件驱动** - 灵活的事件系统

## 本地开发

### 前置条件

- Node.js 18+
- pnpm 8+

### 1. 安装依赖

在 monorepo 根目录（`bkui-chat-x/`）执行：

```bash
pnpm install
```

### 2. 配置环境变量

在 `packages/ai-blueking/` 目录下创建 `.env.local` 文件（该文件已被 `.gitignore` 忽略，不会提交）：

```bash
# packages/ai-blueking/.env.local
VITE_API_URL=https://your-api-endpoint.com/api/
```

> `VITE_API_URL` 是 AI Agent 后端服务的 API 地址，Playground 页面会读取此变量。

### 3. 启动开发服务器

在 monorepo 根目录执行：

```bash
pnpm dev:ai
```

该命令会按顺序执行：

1. **构建 `@blueking/chat-helper`** — ai-blueking 依赖 chat-helper 的构建产物
2. **启动 Vite Dev Server** — 运行 Playground 页面

启动后访问 `http://localhost:8001/`，Playground 包含两个 Tab：

| Tab | 说明 |
|-----|------|
| **AIBlueking（集成模式）** | 完整组件，含悬浮球、拖拽、划词弹窗等 |
| **ChatBot（独立模式）** | 仅聊天功能，可嵌入任意页面 |

### 4. 其他常用命令

所有命令均在 monorepo 根目录执行：

```bash
# 构建 ai-blueking
pnpm build:ai

# 代码检查（ESLint + Stylelint）
pnpm lint:ai

# 构建 chat-helper（ai-blueking 的依赖）
pnpm build:helper

# 开发 chat-x UI 组件库
pnpm dev:ui

# 构建 chat-x
pnpm build:ui

# chat-x 单元测试
pnpm test:ui
```

### Playground 文件结构

```
playground/
├── index.html    # 入口 HTML
├── main.js       # Vue 应用挂载
└── App.vue       # Playground 页面（Tab 切换 AIBlueking / ChatBot）
```

Playground 的 Vite 配置位于 `scripts/vite.dev.ts`，其中 `envDir: '..'` 指向包根目录以加载 `.env.local`。

### 开发注意事项

- **修改 chat-helper 后**需重新执行 `pnpm build:helper`，因为 ai-blueking 引用的是 chat-helper 的构建产物
- **修改 chat-x 后**会由 Vite 自动热更新（workspace 链接，无需手动构建）
- **修改 ai-blueking 自身代码**会自动热更新

## 架构设计

```
┌─────────────────────────────────────────┐
│         小鲸组件层（V2）                  │
│  ┌─────────────┐    ┌─────────────┐    │
│  │ AIBlueking  │    │  ChatBot    │    │
│  │ (完整版)     │    │  (核心版)    │    │
│  └─────────────┘    └─────────────┘    │
│           │                 │           │
│  ┌────────────────────────────────┐    │
│  │      业务管理器层               │    │
│  │  SessionBusiness | ChatBusiness │    │
│  │  UIState | Shortcut            │    │
│  └────────────────────────────────┘    │
└─────────────────────────────────────────┘
           │                  │
┌──────────┴──────┐   ┌──────┴──────────┐
│  原子化组件层    │   │   AG-UI SDK     │
│  (chat-x)       │   │  (chat-helper)  │
│  MessageRender  │   │  session/message │
│  ChatInput      │   │  agent/http     │
└─────────────────┘   └─────────────────┘
```

### 依赖关系

- `@blueking/chat-helper` - AG-UI SDK，提供数据管理和 Agent 交互能力
- `@blueking/chat-x` - 原子化 UI 组件库
- `bkui-vue` - 蓝鲸 Vue3 组件库
- `vue` - Vue 3.5+
- `tippy.js` / `vue-tippy` - Tooltip 功能

## 使用方式

### 方式一：完整组件（AIBlueking）

包含悬浮球、选中文本弹窗、拖拽功能的完整解决方案。

```vue
<template>
  <AIBlueking
    :url="apiUrl"
    :shortcuts="shortcuts"
    :enable-popup="true"
    @show="handleShow"
    @close="handleClose"
  />
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { AIBlueking } from '@blueking/ai-blueking';

const apiUrl = ref('https://your-api-endpoint.com');
const shortcuts = ref([
  { label: '快捷操作1', value: '帮我分析这段代码' },
]);

const handleShow = () => {
  console.log('AIBlueking shown');
};

const handleClose = () => {
  console.log('AIBlueking closed');
};
</script>
```

### 方式二：核心组件（ChatBot）

仅聊天功能，可嵌入到任意页面。支持两种模式：

- **独立模式**：传入 `url`，组件内部创建 chatHelper
- **集成模式**：传入 `chatHelper` 实例，复用父组件的状态

```vue
<template>
  <ChatBot
    :url="apiUrl"
    height="600px"
    max-width="800px"
    @send-message="handleSendMessage"
    @error="handleError"
  />
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { ChatBot } from '@blueking/ai-blueking';

const apiUrl = ref('https://your-api-endpoint.com');

const handleSendMessage = (message: string) => {
  console.log('Message sent:', message);
};

const handleError = (error: Error) => {
  console.error('Error:', error);
};
</script>
```

## Props

### AIBlueking Props

| 属性 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `url` | `string` | - | API 端点 URL |
| `shortcuts` | `Shortcut[]` | `[]` | 快捷操作列表 |
| `enablePopup` | `boolean` | `true` | 是否启用选中文本弹窗 |
| `hideNimbus` | `boolean` | `false` | 是否隐藏悬浮球 |
| `draggable` | `boolean` | `true` | 是否可拖拽 |
| `defaultWidth` | `number` | `400` | 默认宽度 |
| `defaultHeight` | `number` | `600` | 默认高度 |

### ChatBot Props

| 属性 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `url` | `string` | - | API 端点 URL（独立模式） |
| `chatHelper` | `IChatHelper` | - | ChatHelper 实例（集成模式） |
| `height` | `string \| number` | - | 组件高度 |
| `maxWidth` | `string \| number` | - | 最大宽度 |
| `shortcuts` | `Shortcut[]` | `[]` | 快捷操作列表 |
| `shortcutLimit` | `number` | `10` | 快捷方式数量限制 |
| `placeholder` | `string` | - | 输入框占位符 |
| `autoLoad` | `boolean` | `true` | 是否自动加载会话 |
| `sessionCode` | `string` | - | 指定会话编码 |
| `enableSelection` | `boolean` | `false` | 是否启用消息选择（仅集成模式，独立模式自动管理） |
| `shareLoading` | `boolean` | `false` | 分享操作加载中（仅集成模式，独立模式自动管理） |
| `helloText` | `string` | - | 欢迎语 |
| `prompts` | `string[]` | - | 预设提示词列表 |
| `resources` | `IAiSlashMenuItem[]` | - | 资源列表（@ 触发） |

> **分享功能说明**：ChatBot 在独立模式下内置了完整的消息分享能力（进入选择模式 → 调用 API → 复制分享链接 → Toast 提示），无需外部额外处理。集成模式下，`enableSelection` 和 `shareLoading` 由父组件（如 AIBlueking）通过 props 控制。

## Events

### AIBlueking Events

| 事件名 | 参数 | 说明 |
|--------|------|------|
| `show` | - | 组件显示时触发 |
| `close` | - | 组件关闭时触发 |
| `send-message` | `message: string` | 发送消息时触发 |
| `receive-start` | - | 开始接收消息时触发 |
| `receive-end` | - | 接收消息结束时触发 |
| `error` | `error: Error` | 发生错误时触发 |
| `share` | - | 分享按钮被点击 |
| `share-messages` | `userMessageIds: string[]` | 分享完成 |

### ChatBot Events

| 事件名 | 参数 | 说明 |
|--------|------|------|
| `agent-info-loaded` | `chatHelper: IChatHelper` | 独立模式初始化完成（与 `whenReady` 成功时机一致） |
| `send-message` | `message: string` | 发送消息时触发 |
| `session-switched` | `session: ISession` | 会话切换完成 |
| `shortcut-click` | `{ shortcut, source }` | 快捷指令被点击 |
| `feedback` | `tool, message, reasonList, otherReason` | 用户反馈 |
| `request-share` | - | 请求进入分享选择模式 |
| `cancel-share` | - | 取消分享（退出选择模式） |
| `confirm-share` | `messages: Message[]` | 确认分享选中的消息 |
| `error` | `error: Error` | 发生错误时触发 |

### ChatBot Expose

| 方法/属性 | 类型 | 说明 |
|-----------|------|------|
| `whenReady` | `() => Promise<void>` | 等待初始化完成（独立模式含 sessionList） |
| `isReady` | `boolean` | 是否已完成初始化 |
| `switchSession` | `(sessionCode: string) => Promise<void>` | 切换会话 |
| `sendMessage` | `(message: string) => Promise<void>` | 发送消息 |
| `getChatHelper` | `() => IChatHelper \| null` | 获取 chatHelper 实例 |

## 目录结构

```
packages/ai-blueking/
├── playground/               # 本地开发 Playground
│   ├── index.html
│   ├── main.js
│   └── App.vue
├── scripts/                  # 构建/开发脚本
│   ├── vite.dev.ts          #   开发服务器配置
│   ├── vite.build.ts        #   生产构建配置
│   └── vite.utils.ts        #   共享配置
├── src/
│   ├── ai-blueking.vue      # 主组件入口（应用层）
│   ├── index.ts             # 模块导出
│   ├── vue2.ts              # Vue2 入口（兼容层）
│   ├── vue3.ts              # Vue3 入口
│   ├── types.ts             # 全局类型定义
│   ├── components/          # UI 组件层
│   │   ├── chat-bot.vue    #   ChatBot 核心聊天组件
│   │   ├── ai-header/      #   头部组件（含历史会话下拉）
│   │   ├── selection-footer/#   选择模式底部操作栏
│   │   └── types.ts
│   ├── composables/         # 可复用组合式逻辑
│   │   ├── use-chat-bootstrap.ts
│   │   ├── use-event-bridge.ts
│   │   ├── use-history-panel.ts
│   │   └── ...
│   ├── config/              # 配置文件
│   │   ├── prop-defaults.ts
│   │   └── protocol-config.ts
│   ├── containers/          # 容器组件（拖拽等）
│   ├── manager/             # 管理器层
│   │   ├── component-manager.ts
│   │   ├── event-types.ts
│   │   └── business/       # 业务管理器
│   │       ├── chat-business-manager.ts
│   │       ├── session-business-manager.ts
│   │       └── shortcut-manager.ts
│   ├── styles/              # 样式文件
│   ├── utils/               # 工具函数
│   └── views/               # 视图组件
│       └── nimbus.vue      #   悬浮球
├── .env.local               # 本地环境变量（git 忽略）
└── package.json
```

## 划词选择功能

划词选择功能使用 `@blueking/chat-x` 的 `AiSelection` 组件实现：

```vue
<template>
  <AIBlueking
    :url="apiUrl"
    :shortcuts="shortcuts"
    :enable-popup="true"
    :shortcut-limit="3"
  />
</template>
```

### 快捷指令优先级

快捷指令通过 `ShortcutManager` 统一管理，优先级如下：

1. **开发者传入的 shortcuts**（通过 props）
2. **Agent info 接口返回的 commands**
3. 空数组

划词点击快捷指令时，会自动：
- 打开小鲸面板
- 显示对应的快捷指令表单
- 将选中文本填充到 `fillBack` 字段

## 构建产物

构建后的文件位于 `dist/` 目录：

```
dist/
├── vue3/                    # Vue3 版本
│   ├── index.es.min.js     # ES Module
│   ├── index.umd.min.js    # UMD
│   ├── index.iife.min.js   # IIFE
│   └── style.css           # 样式文件
├── vue2/                    # Vue2 版本（兼容层）
│   └── ...
├── vue3.d.ts               # Vue3 类型声明
└── vue2.d.ts               # Vue2 类型声明
```

## 版本兼容

- **Vue 3.5+**: 完全支持（推荐）
- **Vue 2.x**: 需要额外的兼容层

## License

MIT
