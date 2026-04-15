# 小鲸组件 V2 重构变更日志

## 版本 2.0.0 (2025-12-23)

### 🎉 重大更新

基于新的三层架构完成了小鲸组件的完整重构：

```
小鲸组件层 (V2)
    ↓
业务管理器层
    ↓
AG-UI SDK + 原子化组件
```

### ✨ 新增功能

#### 1. 全新架构设计

- **业务管理器层**: 引入 `SessionBusinessManager`、`ChatBusinessManager`、`UIStateManager`、`ShortcutManager` 等业务管理器
- **EventManager**: 统一的事件管理系统
- **Protocol 配置**: 自定义 Protocol 配置支持

#### 2. 两种使用方式

- **AIBlueking 完整组件**: 包含 Nimbus 悬浮球、选中文本弹窗、拖拽功能
- **ChatBot 核心组件**: 可嵌入到任意页面，纯聊天功能

#### 3. 模块化导出

```typescript
// 完整组件
export { AIBlueking } from '@blueking/ai-blueking/v2';

// 核心组件
export { ChatBot } from '@blueking/ai-blueking/v2';

// 业务管理器
export {
  SessionBusinessManager,
  ChatBusinessManager,
  UIStateManager,
  ShortcutManager,
  EventManager,
} from '@blueking/ai-blueking/v2';

// AG-UI SDK
export { useChatHelper } from '@blueking/chat-helper';
```

### 🔄 重构内容

#### 1. Manager 层重构

- ✅ 移除 `AIBluekingSDK` 与 `ComponentManager` 的强耦合
- ✅ `ComponentManager` 专注于 UI 组件协调
- ✅ 创建 `EventManager` 统一事件管理
- ✅ 创建业务管理器封装业务逻辑

#### 2. 组件重构

- ✅ 创建 `ChatBot` 核心组件，可独立使用
- ✅ 重构 `AIBlueking` 主组件，使用 `ChatBot` 作为内容区
- ✅ 保持 Props/Emits/Expose 接口兼容

#### 3. 配置和类型

- ✅ 创建 `createBluekingProtocol` 和 `BluekingProtocol` 类
- ✅ 更新类型定义，重导出 AG-UI SDK 类型
- ✅ 保持向后兼容

### 📁 目录结构

```
v2/
├── ai-blueking.vue              # AIBlueking 完整组件
├── components/                   # 核心组件
│   ├── chat-bot.vue             # ChatBot 核心组件
│   ├── types.ts                 # 组件类型
│   └── index.ts                 # 导出
├── manager/                      # 管理器层
│   ├── component-manager.ts     # UI 组件协调
│   ├── event-manager.ts         # 事件管理
│   ├── business/                # 业务管理器
│   │   ├── session-business-manager.ts
│   │   ├── chat-business-manager.ts
│   │   ├── ui-state-manager.ts
│   │   ├── shortcut-manager.ts
│   │   ├── types.ts
│   │   └── index.ts
│   ├── types.ts
│   └── index.ts
├── config/                       # 配置
│   ├── protocol-config.ts       # Protocol 配置
│   ├── prop-defaults.ts         # Props 默认值
│   └── index.ts
├── containers/                   # 容器组件
│   └── draggable-container.vue
├── examples/                     # 使用示例
│   ├── basic-usage.vue          # 基础使用
│   ├── chatbot-embedded.vue     # ChatBot 嵌入
│   └── advanced-usage.vue       # 高级用法
├── __tests__/                    # 单元测试
│   ├── session-business-manager.spec.ts
│   ├── chat-business-manager.spec.ts
│   ├── ui-state-manager.spec.ts
│   ├── event-manager.spec.ts
│   └── README.md
├── types.ts                      # 类型定义
├── index.ts                      # 导出入口
├── README.md                     # 使用文档
├── CHANGELOG.md                  # 本文档
└── ARCHITECTURE.md               # 架构设计文档
```

### 🧪 测试

- ✅ SessionBusinessManager 单元测试
- ✅ ChatBusinessManager 单元测试
- ✅ UIStateManager 单元测试
- ✅ EventManager 单元测试
- ✅ 测试指南文档

### 📚 文档

- ✅ README.md - 完整使用文档
- ✅ ARCHITECTURE.md - 架构设计文档
- ✅ 3 个使用示例
- ✅ 测试指南

### 🔧 配置文件

- ✅ protocol-config.ts - Protocol 配置
- ✅ prop-defaults.ts - Props 默认值

### 💥 破坏性变更

#### 1. SDK 使用方式变更

**旧版本:**
```typescript
import { AIBluekingSDK } from '@blueking/ai-blueking';
const sdk = new AIBluekingSDK({ ... });
```

**新版本:**
```typescript
import { useChatHelper } from '@blueking/chat-helper';
import { SessionBusinessManager, ChatBusinessManager } from '@blueking/ai-blueking/v2';

const chatHelper = useChatHelper({ ... });
const sessionManager = new SessionBusinessManager(...);
const chatManager = new ChatBusinessManager(...);
```

#### 2. 组件导入路径

**旧版本:**
```typescript
import { AIBlueking } from '@blueking/ai-blueking';
```

**新版本:**
```typescript
import { AIBlueking } from '@blueking/ai-blueking/v2';
```

### ✅ 兼容性

- ✅ Props 接口保持兼容
- ✅ Emits 接口保持兼容
- ✅ Expose 方法保持兼容
- ✅ IShortcut 类型保持兼容

### 📈 改进

1. **职责清晰**: AG-UI SDK 管数据，Manager 管业务，组件管 UI
2. **易于维护**: 每层职责单一，修改影响范围小
3. **高复用性**: ChatBot 可独立使用，也可被 AIBlueking 复用
4. **易扩展**: 新增功能只需在对应的 Manager 中添加
5. **类型安全**: 完整的 TypeScript 类型定义

### 🐛 Bug 修复

- 修复了类型兼容性问题
- 修复了事件传递问题
- 优化了状态管理

### 📝 待办事项

- [ ] 完善集成测试
- [ ] 性能优化（虚拟滚动等）
- [ ] 添加更多使用示例
- [ ] 编写迁移指南

### 🙏 致谢

感谢所有参与重构的开发者！

---

## 迁移指南

### 从 V1 迁移到 V2

#### 步骤 1: 更新导入

```typescript
// 旧版本
import { AIBlueking } from '@blueking/ai-blueking';

// 新版本
import { AIBlueking } from '@blueking/ai-blueking/v2';
```

#### 步骤 2: Props 保持不变

大部分 Props 保持兼容，无需修改：

```vue
<AIBlueking
  url="/api/ai"
  title="AI 助手"
  :shortcuts="shortcuts"
/>
```

#### 步骤 3: 使用新的业务管理器（可选）

如果之前使用了 SDK，需要改为使用业务管理器：

```typescript
// 旧版本
const sdk = new AIBluekingSDK({ ... });
await sdk.sessionManager.createSession();

// 新版本
const chatHelper = useChatHelper({ ... });
const sessionManager = new SessionBusinessManager(...);
await sessionManager.createSession();
```

#### 步骤 4: 测试

运行测试确保一切正常：

```bash
npm run test
```

### 常见问题

**Q: V1 和 V2 可以共存吗？**

A: 可以。V2 在 `/v2` 路径下，不影响 V1 的使用。

**Q: 何时应该迁移到 V2？**

A: 建议新项目直接使用 V2。旧项目可以逐步迁移。

**Q: V1 还会维护吗？**

A: V1 将进入维护模式，只修复严重 bug，不再添加新功能。

---

## 反馈

如果在使用过程中遇到问题，请提交 Issue。













