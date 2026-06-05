# AI Blueking Monorepo

AI 小鲸智能对话组件的完整生态，基于 pnpm workspace 的 monorepo 架构。

## 项目概览

| 包名                                               | 版本          | 说明                               |
| -------------------------------------------------- | ------------- | ---------------------------------- |
| [`@blueking/ai-blueking`](./packages/ai-blueking/) | 2.1.0-beta.4  | 小鲸业务组件（Vue2/Vue3 双构建）   |
| [`@blueking/chat-x`](./packages/chat-x/)           | 0.0.19        | 原子对话 UI 组件库                 |
| [`@blueking/chat-helper`](./packages/chat-helper/) | 0.0.1-beta.36 | AG-UI SDK 工具库（HTTP、消息管理） |

## 架构设计

```
┌─────────────────────────────────────────┐
│         小鲸组件层（ai-blueking）          │
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

```
@blueking/ai-blueking
  ├─ peerDep: vue ^3.5.24, @blueking/chat-x >=0.0.19
  └─ dep: @blueking/chat-helper, bkui-vue, tippy.js, vue-draggable-resizable, vue-tippy

@blueking/chat-x
  └─ devDep: @blueking/chat-helper workspace:*
```

## 项目结构

```
packages/
├── ai-blueking/          ← 小鲸业务组件（Vue2/Vue3 双构建）
│   ├── src/              ← 源码（AIHeader、ChatBot、DraggableContainer 等）
│   ├── scripts/          ← Vite 构建脚本（Vue3 external / Vue2 从源码编译）
│   ├── playground/       ← 开发调试
│   └── dist/             ← 构建产物
├── chat-x/               ← 原子对话 UI 组件库（独立使用）
│   ├── src/              ← 原子组件（ChatInput、MessageBubble、MarkdownRenderer 等）
│   ├── mcp/              ← MCP 工具子模块
│   └── wikis/            ← VitePress 文档
├── chat-helper/          ← AG-UI SDK 工具库（HTTP、消息管理）
├── mcp/                  ← MCP（保留）
├── playground/           ← Vue3 全局开发调试
└── vue2-playground/      ← Vue2 开发调试
```

## 环境准备

- **Node.js**: v20+
- **pnpm**: 8+

```bash
nvm use v20    # 切换到 Node.js v20
pnpm install   # 安装依赖
```

## 开发命令

```bash
# AI Blueking (小鲸组件)
pnpm dev:ai              # 启动 ai-blueking 开发服务器
pnpm build:ai            # 构建 ai-blueking (Vue3 + Vue2)

# Chat X (原子组件库)
pnpm dev:ui              # 启动 chat-x 开发服务器
pnpm build:ui            # 构建 chat-x
pnpm test:ui             # 运行 chat-x 单元测试

# Chat Helper (工具库)
pnpm dev:helper          # 启动 chat-helper 开发
pnpm build:helper        # 构建 chat-helper

# MCP
pnpm build:mcp           # 构建 MCP
pnpm dev:mcp             # 开发 MCP

# Lint
pnpm lint:ui             # 检查 chat-x
pnpm lint:ai             # 检查 ai-blueking
```

## 构建策略（Vue2/Vue3 双构建）

`@blueking/ai-blueking` 支持 Vue2 和 Vue3 双版本构建：

- **Vue3 构建**: `@blueking/chat-x` 作为 external，消费方自行安装，避免 mermaid 等重依赖撑大包体积
- **Vue2 构建**: `@blueking/chat-x` 从源码编译（alias `../../chat-x/src`），保证响应式同源
- **createVue2Wrapper**: 在 Vue2 Options API 组件内嵌 Vue3 `createApp` 渲染，桥接 props/emit/expose/slots
- **CSS 合并**: Vue3 通过 `import '../../chat-x/dist/index.css'` 合并进 `style.css`

### 导入方式

```typescript
// Vue3 (默认)
import { AIBlueking, ChatBot } from '@blueking/ai-blueking';

// Vue2
import AIBlueking from '@blueking/ai-blueking/vue2';
```

## 关键设计模式

| 模式                  | 说明                                                        |
| --------------------- | ----------------------------------------------------------- |
| **Composition API**   | 大量使用 Vue 3 composables                                  |
| **Type Safety**       | 完整 TypeScript 严格配置                                    |
| **chat-x as peerDep** | 必须保持为 peerDependency 以控制包体积（mermaid、katex 等） |
| **workspace:\***      | chat-helper 使用 `workspace:*` 协议进行本地开发             |
| **I18n**              | 内置国际化，中文为主要语言                                  |
| **事件驱动**          | 跨组件通信使用 ComponentManager 事件系统                    |

## 开发注意事项

- **修改 chat-helper 后**需重新执行 `pnpm build:helper`，因为 ai-blueking 引用的是 chat-helper 的构建产物
- **修改 chat-x 后**会由 Vite 自动热更新（workspace 链接，无需手动构建）
- **修改 ai-blueking 自身代码**会自动热更新
- **HTTP 层方法**须在业务层 `use-message.ts` 中透传/封装后，组件才能通过 `chatHelper.message` 调用
- **requestOptions.data** 对 POST/PUT/PATCH/DELETE 合并进 body；对 GET/HEAD/OPTIONS 合并进 query（params）

## 技术栈

| 类别      | 技术                                     |
| --------- | ---------------------------------------- |
| 框架      | Vue 3 + Composition API                  |
| 语言      | TypeScript                               |
| 构建工具  | Vite (rolldown-vite)                     |
| 状态管理  | Vue Reactivity（ref/computed）           |
| UI 组件库 | bkui-vue                                 |
| SDK       | @blueking/chat-helper（AG-UI SDK）       |
| 代码规范  | @blueking/bkui-lint (ESLint + Stylelint) |

## 相关文档

- [ai-blueking 使用文档](./packages/ai-blueking/README.md)
- [ai-blueking 架构设计](./packages/ai-blueking/src/ARCHITECTURE.md)
- [ai-blueking 迁移指南](./packages/ai-blueking/MIGRATION.md)
- [ai-blueking 变更日志](./packages/ai-blueking/src/CHANGELOG.md)

## License

MIT
