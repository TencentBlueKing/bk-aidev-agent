## [1.2.5] - 2025-09-04

> ⚠️ **重要提醒**：小鲸 1.2.5 版本必须与后端 SDK 版本 1.0.0b38 或更高版本匹配使用，否则可能出现兼容性问题

### ✨ 新增功能

#### 会话初始化优化
- **新增 `loadRecentSessionOnMount` 属性**: 支持组件挂载时自动加载最近会话，优化会话初始化体验
- **会话重命名增强**: 优化会话重命名功能，支持自动生成会话名称，提升用户体验

#### 权限和错误处理
- **新增 403 错误页面**: 完善权限控制和无权限访问的处理，提供更好的错误提示体验
- **路由配置更新**: 更新路由配置以支持无权限访问的处理

#### 交互体验增强
- **人工反馈功能**: 新增人工反馈功能，允许用户进行手动反馈操作
- **SaaS 请求支持**: 新增 `saasUrl` 请求功能，支持 SaaS 模式下的接口调用
- **Tooltip 支持**: 新增 `hasSessionContents` 属性，支持为无会话内容的菜单项提供 tooltip 提示
- **选择模式**: 新增选择模式功能，支持消息的选择和多选操作

#### 快捷操作优化
- **组件简化**: 移除 `ai-selected-box` 组件，简化快捷方式点击事件的处理
- **过滤器增强**: 优化快捷操作过滤器逻辑，增强快捷操作的灵活性和可定制性

#### 开发体验提升
- **ESLint 配置重构**: 重构 ESLint 配置，统一代码规范，提升代码质量
- **TypeScript 构建优化**: 新增 `tsconfig.build.json` 配置文件，优化 TypeScript 构建流程
- **环境配置简化**: 移除开发环境配置中的 `BK_API_URL_TMPL` 和 `BKUI_PREFIX` 变量，简化环境配置

#### 依赖升级
- **@blueking/ai-ui-sdk 升级**: 升级依赖到 `0.1.16-beta.3`，获取更多底层能力支持和功能增强

#### 图标和样式完善
- **图标字体库更新**: 进一步完善图标字体库，新增和优化多个图标
- **视觉样式优化**: 改进视觉样式和交互效果，提升整体用户体验

### 🎯 使用示例

#### loadRecentSessionOnMount 配置
```vue
<template>
  <AIBlueking
    :load-recent-session-on-mount="true"
    :url="apiUrl"
  />
</template>
```

#### hasSessionContents 属性使用
```vue
<template>
  <AIBlueking
    :has-session-contents="sessionContents.length > 0"
    :url="apiUrl"
  />
</template>
```

### ⚠️ 注意事项

- **环境配置变更**: 开发环境配置已移除 `BK_API_URL_TMPL` 和 `BKUI_PREFIX` 变量，请更新相关配置
- **依赖升级**: 升级了 `@blueking/ai-ui-sdk` 到最新版本，请确保兼容性
- **快捷操作**: 快捷操作逻辑已优化，简化了事件处理流程

## [1.2.4] - 2025-09-03

### ✨ 新增功能

- **beforeRequest 钩子支持**: 支持在发送请求前对请求参数进行处理，增强请求的灵活性和可控制性
- **划选过滤增强**: 改进划选文本检测逻辑，优化在 shadow DOM 中的文本选择支持
- **监控体验优化**: 优化组件的监控和错误处理机制，提供更稳定的用户体验

### 🎨 优化改进

- **快捷操作过滤器增强**:
  - 更新 `shortcutFilter` 函数签名，支持访问选中文本内容
  - 函数签名从 `(shortcut: IShortcut) => boolean` 更新为 `(shortcut: IShortcut, selectedText: string) => boolean`
- **结构化引用数据支持**:
  - 优化引用组件，增加内容溢出处理和快捷操作支持
  - 新增结构化引用数据显示组件
- **表单提交逻辑优化**:
  - 优化表单提交逻辑，新增处理和过滤表单数据的辅助函数
  - 支持引用数据的传递，区分完整表单数据和用于引用显示的过滤数据

### 🐛 BUG修复

- 修复划选文本检测的时序问题，提升划选操作的响应速度和准确性
- 修复在某些场景下快捷操作事件重复触发的问题

## [1.2.4-beta.3] - 2025-08-20

### ✨ 新增功能

- **快捷操作组件隐藏支持**: 新增 `hide` 属性，支持动态控制快捷操作表单组件的显示/隐藏
  - 在 `IShortcut` 的 `components` 配置中新增 `hide` 属性
  - 当设置为 `true` 时，该组件将不会在表单中显示，同时其数据也不会包含在提交的表单数据中
  - 支持根据条件动态显示/隐藏表单字段，实现更灵活的表单交互

```javascript
{
  id: 'dynamic_form',
  name: '动态表单',
  icon: 'bkai-icon bkai-form',
  components: [
    {
      type: 'select',
      key: 'userType',
      name: '用户类型',
      options: [
        { label: '普通用户', value: 'normal' },
        { label: 'VIP用户', value: 'vip' }
      ],
      placeholder: '请选择用户类型'
    },
    {
      type: 'input',
      key: 'vipCode',
      name: 'VIP码',
      placeholder: '请输入VIP码',
      // 只有当用户类型为VIP时才显示此字段
      hide: true // 初始隐藏，可根据条件动态控制
    }
  ]
}
```

## [1.2.4-beta.2] - 2025-08-20

### ✨ 新增功能

- **快捷操作过滤器**: 新增 `shortcutFilter` 属性，支持根据选中文本内容动态过滤快捷操作的显示
  - 当用户选中文本时，每个快捷操作的组件会自动获得 `selectedText` 属性
  - 开发者可以通过 `shortcutFilter` 函数访问选中文本内容，实现更智能的快捷操作过滤
  - 支持根据选中文本特征（如代码、长度等）动态控制快捷操作的可见性

```vue
<template>
  <AIBlueking
    :shortcuts="shortcuts"
    :shortcut-filter="shortcutFilter"
  />
</template>

<script setup>
  const shortcuts = [
    {
      id: 'explain_code',
      name: '解释代码',
      icon: 'bkai-icon bkai-code',
      components: [
        {
          type: 'textarea',
          key: 'code',
          name: '代码内容',
          fillBack: true,
          placeholder: '请输入或选中需要解释的代码',
        },
      ],
    },
  ];

  const shortcutFilter = shortcut => {
    // 获取选中的文本内容
    const selectedText = shortcut.components?.find(c => c.selectedText)?.selectedText || '';

    // 根据快捷操作类型和选中文本内容进行过滤
    switch (shortcut.id) {
      case 'explain_code':
        // 只有当选中的文本包含代码特征时才显示
        return (
          selectedText.includes('function') ||
          selectedText.includes('const') ||
          selectedText.includes('let') ||
          selectedText.includes('var')
        );
      default:
        return true;
    }
  };
</script>
```

## [1.2.3] - 2025-08-12

### ✨ 新增功能

- **会话自动命名**: 新增会话自动命名功能，首次提问后将自动为会话生成标题，提升会话辨识度。
- **快捷指令增强**:
  - 支持快捷指令选择和自定义表单，优化复杂指令的交互体验。
  - 弹窗触发的快捷操作支持自动提交，简化操作步骤。
- **意图识别**: 初步支持意图识别功能，为未来更智能的交互奠定基础。
- **样式扩展**: 新增 `extCls` 属性，方便用户自定义组件样式。

### 🎨 优化改进

- **会话管理**: 优化会话列表 (`sessionList`) 的管理和切换逻辑。
- **UI/UX 优化**:
  - 优化了开场白和问候语的显示逻辑。
  - 改进了聊天输入框的占位符提示。
- **代码质量**:
  - 修复了部分场景下的导包问题。
  - 更新了蓝鲸插件版本依赖。

### 🐛 BUG修复

- 修复了 markdown 复制代码按钮的显示问题。
- 修复了搜索功能失效的问题。
- 修复了开场白过长导致的UI截断问题。

## [1.2.2] - 2025-08-06

### ✨ 新增功能

- **编程式会话管理**: 新增 `addNewSession`, `updateSessionName`, `switchToSession`, `getSessionList` 等方法，允许外部程序化控制会话。
- **初始会话指定**: 新增 `initialSessionCode` 和 `autoSwitchToInitialSession` 属性，支持组件加载时直接进入特定会话。

### 🎨 优化改进

- **文档重构**: 优化文档结构，将编程控制相关内容整合为“基础控制”、“会话生命周期”和“高级工作流”三个层次。
- **响应性修复**: 修复了更新会话名称后，历史列表UI不刷新的问题。
- **BUG修复**: 修复了切换会话时偶现的 `switchSession` 方法不存在的错误。

## [1.1.0-beta.2] - 2025-06-02

### 修复

- **修复自定义输入 `textarea` 背景色异常的问题**

## [1.1.0-beta.1] - 2025-06-01

### 新增功能

- **自定义表单输入功能**：
  - 添加自定义表单输入能力，支持快捷指令自定义表单交互
  - 支持文本输入框、下拉选择框、数字输入框和多行文本域等多种表单组件
  - 优化快捷操作接口定义，增强扩展性

### 变更

- **快捷操作接口升级**：
  - 重构快捷操作的数据结构，从 `ShortCut` 升级为更加灵活的 `IShortcut`
  - 支持通过自定义组件配置实现复杂的用户输入交互
  - 增加表单数据的收集和提交能力
  - **重要**: 快捷操作不再使用前端拼接 prompt 的方式，而是将表单数据作为上下文直接发送到后端，**需要后端进行适配**

```typescript
// 新的快捷操作接口定义
interface IShortcut {
  id: string; // 快捷操作ID
  name: string; // 快捷操作名称
  icon?: string; // 图标类名
  // 组件配置，用于定义表单项
  components: Array<{
    type: string; // 组件类型：'input', 'select', 'textarea', 'number' 等
    name?: string; // 表单项名称
    key: string; // 表单项键名
    placeholder?: string; // 占位文本
    default?: any; // 默认值
    required?: boolean; // 是否必填
    fillBack?: boolean; // 是否自动填充选中文本
    fillRegx?: string | RegExp; // 填充的正则匹配表达式
    rows?: number; // 输入框行数（textarea类型）
    min?: number; // 最小值（number类型）
    max?: number; // 最大值（number类型）
    options?: Array<{
      // 下拉选项（select类型）
      label: string;
      value: string | number;
    }>;
  }>;
}
```

### 后端数据格式

后端将接收到以下格式的数据：

```javascript
// 后端接收到的数据结构示例
{
  "property": {
    "extra": {
      "command": "translate", // 快捷操作ID，对应 IShortcut 的 id
      "context": [
        { "key": "text", "value": "这是需要翻译的文本" },
        { "key": "targetLang", "value": "en" },
        // ... 其他表单数据
      ]
    }
  }
}
```

# 更新日志

## [1.1.5] - 2025-07-09

### ✨ 新增功能

#### URL 协议自动适配

- **智能协议匹配**：新增 `normalizeUrl` 工具函数，自动匹配当前页面协议
- **安全性提升**：HTTPS 页面下自动将 HTTP API 转换为 HTTPS，提升安全性
- **多种路径支持**：支持相对路径、绝对路径、协议相对路径的智能识别和处理

```vue
<template>
  <!-- 支持多种URL格式 -->
  <AIBlueking :url="'/api/chat'" />
  <!-- 相对路径 -->
  <AIBlueking :url="//api.example.com/chat" />
  <!-- 协议相对路径 -->
  <AIBlueking :url="http://api.example.com/chat" />
  <!-- 完整URL，HTTPS页面下自动转换为HTTPS -->
</template>
```

#### 上下文支持

- **静态上下文**：支持传递静态对象作为上下文信息
- **动态上下文**：支持传递函数，实现动态上下文获取
- **灵活配置**：可以是单个对象或对象数组

```vue
<template>
  <!-- 静态上下文 -->
  <AIBlueking
    :url="apiUrl"
    :request-options="{
      context: { userId: '123', department: 'IT' },
    }"
  />

  <!-- 动态上下文 -->
  <AIBlueking
    :url="apiUrl"
    :request-options="{
      context: () => ({
        userId: getCurrentUserId(),
        timestamp: Date.now(),
      }),
    }"
  />
</template>

<script setup>
  const getCurrentUserId = () => {
    // 动态获取用户ID的逻辑
    return store.state.user.id;
  };
</script>
```

### 🎨 优化改进

#### URL 处理优化

- **智能识别**：自动识别不同类型的URL格式
- **协议转换**：在HTTPS环境下自动升级HTTP请求为HTTPS
- **错误处理**：完善的URL处理错误捕获和降级机制

#### 类型定义改进

- **TypeScript 优化**：改进 `debounce` 函数的类型定义
- **上下文类型**：新增 `IContext` 类型定义，支持对象和对象数组
- **开发体验**：提升IDE智能提示和类型检查

#### 代码质量提升

- **格式化**：统一代码格式，提升可读性
- **性能优化**：优化URL处理和上下文传递的性能
- **错误处理**：增强错误处理机制

### 🔧 新增配置项

| 配置项                   | 类型                           | 描述                               |
| ------------------------ | ------------------------------ | ---------------------------------- |
| `requestOptions.context` | `IContext \| (() => IContext)` | 上下文信息，支持静态对象或动态函数 |

其中 `IContext` 类型定义为：

```typescript
type IContext = Record<string, string> | Record<string, string>[];
```

### 📝 使用示例

#### 完整的上下文配置示例

```vue
<template>
  <AIBlueking
    ref="aiBlueking"
    :url="apiUrl"
    :request-options="requestOptions"
  />
</template>

<script setup>
  import { ref, computed } from 'vue';
  import { AIBlueking } from '@blueking/ai-blueking';

  const aiBlueking = ref(null);
  const apiUrl = '/api/ai/chat'; // 相对路径，会自动转换为完整URL

  // 动态上下文配置
  const requestOptions = computed(() => ({
    headers: {
      Authorization: `Bearer ${getToken()}`,
    },
    context: () => ({
      userId: getCurrentUser().id,
      sessionId: getSessionId(),
      timestamp: Date.now().toString(),
      userAgent: navigator.userAgent,
    }),
  }));

  const getToken = () => {
    // 获取认证token
    return localStorage.getItem('auth_token');
  };

  const getCurrentUser = () => {
    // 获取当前用户信息
    return JSON.parse(localStorage.getItem('user_info') || '{}');
  };

  const getSessionId = () => {
    // 获取会话ID
    return sessionStorage.getItem('session_id');
  };
</script>
```

#### URL 协议适配示例

```vue
<template>
  <div>
    <!-- 这些URL在不同协议环境下会自动适配 -->
    <AIBlueking :url="httpUrl" />
    <!-- HTTP环境：保持HTTP，HTTPS环境：自动转换为HTTPS -->
    <AIBlueking :url="httpsUrl" />
    <!-- 任何环境：保持HTTPS -->
    <AIBlueking :url="relativeUrl" />
    <!-- 自动使用当前页面的协议和域名 -->
    <AIBlueking :url="protocolRelativeUrl" />
    <!-- 自动使用当前页面的协议 -->
  </div>
</template>

<script setup>
  const httpUrl = 'http://api.example.com/chat';
  const httpsUrl = 'https://api.example.com/chat';
  const relativeUrl = '/api/chat';
  const protocolRelativeUrl = '//api.example.com/chat';
</script>
```

### ⚠️ 注意事项

- **协议转换**：在HTTPS页面中使用HTTP API时会自动转换为HTTPS，请确保目标服务器支持HTTPS
- **上下文函数**：动态上下文函数会在每次发送消息时调用，请避免在函数中执行耗时操作
- **类型安全**：使用TypeScript时，上下文对象的值必须是字符串类型

## [1.1.2] - 2025-07-08

### ✨ 新增功能

#### 可配置压缩边距

- **新增 `miniPadding` 属性**：支持自定义压缩状态下的边距

```vue
<template>
  <AIBlueking
    :url="apiUrl"
    :mini-padding="20"
  />
</template>
```

### 🎨 用户体验优化

#### 高度切换逻辑优化

- **智能恢复**：恢复默认高度时使用用户设置的初始位置和尺寸
- **保持配置**：不再使用固定的 `window.innerHeight`，而是根据用户的初始配置恢复
- **状态管理改进**：更好地保持用户自定义的初始位置、高度等配置

### 🔧 新增属性

| 属性/方法名   | 类型     | 默认值 | 描述                         |
| ------------- | -------- | ------ | ---------------------------- |
| `miniPadding` | `Number` | `0`    | 压缩状态下的边距，单位为像素 |

### 📝 使用示例

```vue
<template>
  <div>
    <!-- 自定义压缩边距 -->
    <AIBlueking
      :url="apiUrl"
      :mini-padding="20"
      :default-width="500"
      :default-height="600"
      :default-top="100"
      :default-left="200"
    />

    <!-- 无边距压缩（默认行为） -->
    <AIBlueking
      :url="apiUrl"
      :mini-padding="0"
    />
  </div>
</template>

<script setup>
  import { AIBlueking } from '@blueking/ai-blueking';

  const apiUrl = 'your-ai-service-url';
</script>
```

### 🔧 技术改进

- **初始状态保存**：新增 `initialTop`、`initialHeight`、`initialWidth` 等状态保存用户设置的初始值
- **恢复逻辑优化**：`toggleCompression` 函数在恢复时使用保存的初始值而非固定值
- **参数化配置**：将硬编码的 `miniPadding` 改为可配置参数，提升组件灵活性

## [1.1.1] - 2025-07-08

### ✨ 新增功能

#### 自定义占位符文本

- **新增 `placeholder` 属性**：支持自定义输入框占位符文本
- **灵活配置**：可以根据不同场景设置不同的提示文本
- **向下兼容**：默认保持原有的提示文本

```vue
<template>
  <AIBlueking
    :url="apiUrl"
    placeholder="请输入您的问题..."
  />
</template>
```

#### 输入框聚焦优化

- **自动聚焦**：面板打开时自动聚焦到输入框，提升用户体验
- **程序式聚焦**：新增 `focusInput` 方法，支持外部调用聚焦输入框

```vue
<template>
  <AIBlueking
    ref="aiBlueking"
    :url="apiUrl"
  />
  <button @click="focusInput">聚焦输入框</button>
</template>

<script setup>
  import { ref } from 'vue';

  const aiBlueking = ref(null);

  const focusInput = () => {
    aiBlueking.value?.focusInput();
  };
</script>
```

### 🎨 用户体验优化

#### Prompt 列表显示优化

- **智能显示**：只有在有 Prompt 数据且输入包含 '/' 时才显示 Prompt 列表
- **减少干扰**：避免空列表时的无意义显示，提供更清爽的界面
- **交互改进**：优化 Prompt 触发逻辑，提升使用体验

### 🔧 新增属性和方法

| 属性/方法名    | 类型     | 默认值                                                    | 描述                 |
| -------------- | -------- | --------------------------------------------------------- | -------------------- |
| `placeholder`  | `String` | `'输入 "/" 唤出 Prompt\n通过 Shift + Enter 进行换行输入'` | 输入框占位符文本     |
| `focusInput()` | `Method` | -                                                         | 程序式聚焦输入框方法 |

### 📝 使用示例

```vue
<template>
  <div>
    <!-- 自定义占位符 -->
    <AIBlueking
      ref="aiBlueking"
      :url="apiUrl"
      placeholder="有什么可以帮助您的吗？"
    />

    <!-- 外部控制聚焦 -->
    <button @click="handleFocus">聚焦输入框</button>
  </div>
</template>

<script setup>
  import { ref } from 'vue';
  import { AIBlueking } from '@blueking/ai-blueking';

  const aiBlueking = ref(null);
  const apiUrl = 'your-ai-service-url';

  const handleFocus = () => {
    aiBlueking.value?.focusInput();
  };
</script>
```

## [1.1.0] - 2025-07-07

### ✨ 重大更新 - 多会话管理功能

全新的会话管理体验，支持多个聊天会话的创建、切换、管理，让您的AI对话更加有序和高效。

### 🎯 核心新功能

#### 多会话管理

- **🆕 会话创建**：支持创建多个独立的聊天会话，每个会话保持独立的对话上下文
- **🔄 会话切换**：在不同会话间快速切换，无缝继续之前的对话
- **📝 会话重命名**：直接在历史面板中编辑会话名称，便于识别和管理
- **🗑️ 会话删除**：支持删除不需要的会话，提供确认机制防止误操作
- **🧠 智能切换**：删除当前会话时自动切换到最近的会话或创建新会话

#### 历史会话面板

- **📊 时间分组**：按"今天"、"昨天"、"之前"自动分组显示历史会话
- **🔍 搜索功能**：支持在历史面板中搜索会话，快速定位目标对话
- **🎨 视觉优化**：现代化的面板设计，清晰的会话状态指示
- **📱 响应式设计**：适配不同屏幕尺寸，提供一致的用户体验

#### 界面增强

- **🆕 新聊天按钮**：头部新增新建聊天按钮，一键创建新的对话会话
- **📋 动态标题**：头部标题现在显示当前会话名称，提供更好的上下文感知
- **⚙️ 图标控制**：新增属性控制历史和新聊天图标的显示
- **🔄 加载状态**：会话内容加载时提供视觉反馈

### 🔧 新增属性

```html
<template>
  <AIBlueking
    :show-history-icon="true"     <!-- 控制历史会话图标显示 -->
    :show-new-chat-icon="true"    <!-- 控制新聊天图标显示 -->
  />
</template>
```

| 属性名            | 类型      | 默认值 | 描述                       |
| ----------------- | --------- | ------ | -------------------------- |
| `showHistoryIcon` | `Boolean` | `true` | 控制头部历史会话图标的显示 |
| `showNewChatIcon` | `Boolean` | `true` | 控制头部新聊天图标的显示   |

### 🎨 用户体验优化

- **流畅切换**：优化会话切换动画和加载体验
- **状态保持**：每个会话独立保存对话历史和上下文
- **错误处理**：完善的错误处理机制，确保会话操作的稳定性
- **性能优化**：优化大量会话时的渲染性能

### 🌐 多语言支持

为所有新增功能提供完整的中英文支持：

- 历史会话、新增聊天、编辑、删除等操作的多语言文本
- 时间分组标签的本地化显示
- 确认对话框和提示信息的多语言支持

### 🔄 架构升级

- **会话存储重构**：全新的会话状态管理架构，支持复杂的多会话场景
- **组件模块化**：新增多个专用组件，提高代码可维护性
- **API 优化**：内部API重构，为未来功能扩展奠定基础

### 📝 使用示例

```vue
<template>
  <div>
    <!-- 基础多会话使用 -->
    <AIBlueking
      :url="apiUrl"
      :show-history-icon="true"
      :show-new-chat-icon="true"
    />

    <!-- 隐藏部分图标的使用 -->
    <AIBlueking
      :url="apiUrl"
      :show-history-icon="false"  <!-- 隐藏历史图标 -->
      :show-new-chat-icon="true"
    />
  </div>
</template>

<script setup>
import { AIBlueking } from '@blueking/ai-blueking';

const apiUrl = 'your-ai-service-url';
</script>
```

### ⚠️ 注意事项

- 多会话功能需要后端API支持，请确保您的AI服务支持会话管理
- 会话数据存储在浏览器本地，清除浏览器数据会丢失会话历史
- 建议在生产环境中配置适当的会话数量限制

## [1.0.3] - 2025-07-03

### 新增功能

- **支持动态更新 `requestOptions`**：
  - `requestOptions` 属性现在支持动态更新，允许在运行时修改请求参数。
  - 这使得开发者可以根据应用状态变化，灵活调整发送给 AI 的数据。

```html
<template>
  <AIBlueking :request-options="dynamicOptions" />
</template>

<script setup>
  import { ref, reactive } from 'vue';

  const dynamicOptions = reactive({
    data: {
      param1: 'initial_value',
    },
  });

  // 在运行时更新
  setTimeout(() => {
    dynamicOptions.data.param1 = 'new_value';
  }, 2000);
</script>
```

## [1.0.2] - 2025-06-25

### 新增功能

- **新增 Nimbus 尺寸调整功能**：
  - 新增 `nimbusSize` 属性，支持 `small`, `normal`, `large` 三种尺寸。
  - 用户可以根据需求调整 Nimbus 悬浮图标的大小，以适应不同的界面环境。
  - 默认值为 `normal`。

```html
<template>
  <AIBlueking nimbus-size="small" />
</template>
```

### 优化

- **优化 Nimbus 最小化按钮尺寸**：
  - 根据 `nimbusSize` 属性动态调整最小化按钮的大小和位置。
  - 修复了在 `small` 尺寸下最小化按钮显得过大的问题，提升了视觉协调性。

## [1.0.1] - 2025-05-28

### 新增功能

- **新增输入框禁用控制**：
  - 新增 `disabledInput` 属性，用于控制输入框是否可用
  - 当设置为 `true` 时，输入框将处于禁用状态，用户无法输入文本
  - 默认值为 `false`，即默认可输入

```html
<template>
  <AIBlueking :disabled-input="true" />
</template>
```

### 优化

- **优化输入框禁用状态的样式**：
  - 提供更明确的禁用状态视觉反馈
  - 禁用状态下输入框呈灰色，且鼠标悬停显示禁用光标

### 修复

- **修复输入组件状态管理问题**：
  - 修复了某些场景下输入组件状态管理不正确的问题
  - 优化了输入框与发送按钮的状态联动

## [1.0.0] - 2025-05-27

### ✨ 重大更新 - AI 小鲸 1.0 全新架构

全新升级，搭配 AIDev 智能体一站式体验，更流畅的交互和更丰富的功能。

### 优化

- **优化可调整容器高度的逻辑**：
  - 通过添加异步处理，修复了窗口尺寸调整时的计算问题
  - 提高了屏幕尺寸变化时容器高度适配的稳定性

```javascript
// 优化后的高度调整逻辑
setTimeout(() => {
  height.value = window.innerHeight - top.value;
}, 0);
```

#### 交互体验优化

- ✅ **改进拖拽体验**：更流畅的窗口拖拽感觉
- ✅ **动态调整大小**：优化窗口大小调整的交互体验
- ✅ **布局优化**：更合理的空间利用和内容展示

### ⚠️ 破坏性变动 (Breaking Changes)

- ❌ **API 方法变更**：不再暴露 `sendChat` 方法，请使用新的 `sendMessage` 方法
- ❌ **预设对话变更**：预设对话内容不再支持自定义，改为从接口统一获取
- ❌ **事件机制变更**：修改了部分事件名称和参数结构，请参考最新文档
- ❌ **组件属性调整**：部分组件属性名称和用法发生变化

## [0.5.6] - 2025-05-20

### 修复

- **修复消息发送逻辑**：
  - 修复在加载状态下仍可发送消息的问题
  - 优化消息发送逻辑，防止在AI响应过程中重复发送消息

```javascript
// 优化后的消息发送逻辑
const sendMessage = () => {
  if (!inputValue.value.trim() || props.loading) return; // 增加loading状态检查
  handleSend();
};
```

## [0.5.5] - 2025-05-15

### 新增功能

- **优化位置交互计算方式**：
  - 改进组件定位算法，提高组件在各种场景下的定位精度
  - 增强拖拽与调整大小时的流畅性体验

### 修复

- **修复初始位置调整问题**：
  - 修复初始位置调整导致位置交互错位的问题
  - 解决组件初始渲染时的位置计算错误
- **修复Vue2组件兼容性问题**：
  - 修复Vue2部分属性不生效的问题
  - 增强Vue2与Vue3组件间的API一致性
- **修复宽度计算问题**：
  - 修复组件默认宽度计算错误的问题
  - 优化`maxWidth`的计算方式，确保界面在不同屏幕尺寸下正确显示

```html
<template>
  <AIBlueking
    :default-top="50"
    :draggable="true"
  />
</template>
```

## [0.5.4] - 2025-04-28

### 新增功能

- **增强可拖拽功能**：
  - 新增 `draggable` 属性，控制组件是否可拖拽（默认true）
  - 当设置为 `false` 时，组件将固定位置不可拖动
- **支持自定义初始位置和尺寸**：
  - 新增 `defaultWidth` 属性：设置组件初始宽度
  - 新增 `defaultHeight` 属性：设置组件初始高度
  - 新增 `defaultTop` 属性：设置组件初始顶部位置
  - 新增 `defaultLeft` 属性：设置组件初始左侧位置
  - 这些属性可以配合使用，实现组件初始状态的精确控制

```html
<template>
  <AIBlueking
    :draggable="false"
    :default-width="600"
    :default-height="400"
    :default-top="100"
    :default-left="200"
  />
</template>
```

## [0.5.3] - 2025-04-20

### 新增功能

- **支持预设对话内容**：
  - 新增 `defaultMessages` 属性，允许预设初始化对话内容
  - 可通过此属性实现对话的预加载和状态恢复

```html
<template>
  <AIBlueking
    :default-messages="[
    { role: 'user', content: '你好' },
    { role: 'assistant', content: '您好！有什么我可以帮助您的吗？' }
  ]"
  />
</template>
```

- **新增消息交互事件**：
  - 新增 `receive-start` 事件：AI 开始接收响应时触发
  - 新增 `receive-text` 事件：接收到文本片段时触发
  - 新增 `receive-end` 事件：响应接收完成时触发
  - 新增 `send-message` 事件：发送消息时触发
  - 提供完整的消息传递生命周期钩子

```html
<template>
  <AIBlueking
    @receive-start="handleReceiveStart"
    @receive-text="handleReceiveText"
    @receive-end="handleReceiveEnd"
    @send-message="handleSendMessage"
  />
</template>
```

### 从 Beta 版本合并的功能

- **增强 Vue2 组件 API 支持**：
  - 完善 Vue2 组件对 Vue3 组件暴露的 API 的支持，确保所有方法和属性都能被正确访问
  - 包括 `sessionContents`, `handleClose`, `handleSendMessage`, `handleDelete`, `handleRegenerate`, `handleResend` 等
  - 使用 `Object.defineProperty` 保持 `sessionContents` 属性的响应式特性
- **完善 Vue2 与 Vue3 组件的兼容性**
- **图标系统升级**：将所有图标类名从 `icon-*` 更新为 `bkai-*` 前缀
- **支持自定义标题和欢迎语**：新增 `title` 和 `helloText` 属性
- **支持组件关闭事件**：新增 `close` 事件
- **支持 mermaid 图表渲染**
- **支持自定义传送目标元素**：新增 `teleportTo` 属性
- **支持设置 Nimbus 初始最小化状态**：新增 `defaultMinimize` 属性
- **支持自定义请求选项**：通过 `requestOptions` 传递自定义选项到发送请求
- **支持访问会话内容**：新增 `sessionContents` 属性

### 修复

- 修复框选内容在输入时没有立即消失的问题
- 修复输入框组件可能引起的 xml 攻击风险
- 修复 `minimize` 下点击无法显示面板的问题

## [0.5.3-beta.6] - 2025-04-16

### 优化

- **增强 Vue2 组件 API 支持**：
  - 完善 Vue2 组件对 Vue3 组件暴露的 API 的支持，确保所有方法和属性都能被正确访问
  - 包括 `sessionContents`, `handleClose`, `handleSendMessage`, `handleDelete`, `handleRegenerate`, `handleResend` 等
  - 使用 `Object.defineProperty` 保持 `sessionContents` 属性的响应式特性
- **完善 Vue2 与 Vue3 组件的兼容性**：
  - 优化 Vue2 组件的代码结构，提升与 Vue3 组件间的交互效率
  - 确保 Vue2 环境下的功能和 Vue3 一致

## [0.5.3-beta.5] - 2025-04-15

### 优化

- **图标系统升级**：
  - 将所有图标类名从 `icon-*` 更新为 `bkai-*` 前缀，统一组件图标风格
  - 优化停止生成和滚动到底部功能的图标展示

## [0.5.3-beta.4] - 2025-04-10

### 新增功能

- **支持自定义标题和欢迎语**：
  - 新增 `title` 属性，支持自定义标题
  - 新增 `helloText` 属性，支持自定义欢迎语

## [0.5.3-beta.3] - 2025-04-03

### 新增功能

- **支持组件关闭事件**：
  - 新增 `close` 事件，响应组件关闭
  - 事件返回完整的关闭信息：`{ type, label, cite, prompt }`

```html
<AIBlueking @close="handleClose" />
```

## [0.5.3-beta.2] - 2025-04-02

### 新增功能

- **支持 mermaid 图表渲染**：

## [0.5.3-beta.1] - 2025-04-02

### 新增功能

- **支持自定义传送目标元素**：
  - 新增 `teleportTo` 属性，控制组件内容传送到的 DOM 节点
  - 可以将组件内容渲染到任意 DOM 位置，避免嵌套组件的样式和定位问题
  - 默认值为 `body`，将组件渲染到 body 元素下

```html
<template>
  <!-- 将组件内容传送到 id 为 ai-container 的元素内 -->
  <AIBlueking :teleport-to="#ai-container" />
</template>
```

### 修复

- 修复框选内容在输入时没有立即消失的问题
- 修复输入框组件可能引起的 xml 攻击风险
- 修复 `minimize` 下点击无法显示面板的问题

## [0.5.2] - 2025-04-01

### 新增功能与支持

- **支持设置 Nimbus 初始最小化状态**：
  - 新增 `defaultMinimize` 属性，控制 Nimbus 组件初始是否处于最小化状态
  - 当设置为 `true` 时，Nimbus 组件会以最小化状态启动
  - 默认值为 `false`，以正常状态显示

```html
<template>
  <AIBlueking :default-minimize="true" />
  <!-- Nimbus 组件初始以最小化状态显示 -->
</template>
```

### 支持 Chat 接口添加自定义参数

- 支持 `requestOptions` 传递自定义选项到发送请求

```html
<template>
  <AIBlueking
    :request-options="{
    headers: {
      preset: 'QA',
    },
    data: {
      preset: 'QA',
    },
  }"
  />
</template>
```

这将使得发送请求时，会携带 `preset` 参数，headers 的数据会合并到请求头中， 请求体数据会合并到请求体中

```diff
{
  inputs: {},
  chat_history: [],
  input: 'xxx',
+  preset: "QA"
}
```

### 支持 `sessionContents` 暴露当前会话内容

- 新增 `sessionContents` 属性，暴露当前会话内容
- 通过 `sessionContents` 属性，可以获取当前会话内容，方便外部访问和操作

```html
<template>
  <AIBlueking ref="aiBlueking" />
</template>

<script
  setup
  lang="ts"
>
  import { ref } from 'vue';
  import AIBlueking from '@blueking/ai-blueking';

  const aiBluekingRef = ref<InstanceType<typeof AIBlueking>>();
  const sessionContents = aiBluekingRef.value?.sessionContents; // 获取当前会话内容
</script>
```

## [0.5.0] - 2025-03-28

### ✨ 重大更新 - 全新版 AI 小鲸

全新架构设计，UI 界面彻底重构，带来更加流畅的交互体验和开箱即用的能力。

#### 界面与交互升级

- ✅ **全新 UI 设计**：重新设计的用户界面，更加现代化和美观
- ✅ **可拖拽可调整大小界面**：窗口可自由拖拽和调整大小
- ✅ **适配不同尺寸**：优化响应式设计，适应不同屏幕尺寸
- ✅ **优化字体大小**：基础字体从 12px 调整至 14px，提升可读性

#### 新增功能

- ✅ **Nimbus 支持**：内置弹出式交互，开箱即用，开发者接入更加便捷
- ✅ **预设提示词列表**：添加 `PromptList` 组件，支持快速选择常用提示词
- ✅ **删除确认功能**：增加消息删除前的确认机制，避免误操作
- ✅ **文本区域高度自适应**：输入框会根据内容自动调整高度

#### 架构与性能优化

- ✅ **代码架构重构**：优化组件结构，提升代码可维护性
- ✅ **状态管理优化**：改进会话和消息状态管理
- ✅ **开箱即用**：简化接入流程，只需传入 Agent 地址即可快速集成

#### 用户体验改进

- ✅ **增强的消息渲染**：优化消息渲染逻辑，支持更丰富的内容展示
- ✅ **引用内容交互优化**：改进选中文本引用的交互体验
- ✅ **自定义滚动条**：增加自定义滚动条样式，提升视觉体验
- ✅ **优化引用内容交互**：改进框选引用和输入内容的交互流程

### ⚠️ 破坏性变动 (Breaking Changes)

- 组件 API 结构调整，请参考最新文档进行升级
- 各业务升级请务必做好全量测试，有问题随时反馈，新版本会持续迭代优化

### 使用示例

```vue
<template>
  <div>
    <button @click="showAI">打开 AI 小鲸</button>

    <AIBlueking
      ref="aiBlueking"
      :url="apiUrl"
      :prompts="customPrompts"
      @show="handleShow"
      @close="handleClose"
    />
  </div>
</template>
```

## [0.4.3] - 2025-03-03

### 修复

- 参考文档 `preview_path` 字段
- Vue2 组件导出 `isThinking` 工具函数

## [0.4.2] - 2024-02-28

### 修复

- Vue2 组件对 `shortcut-click` 事件的响应问题

## [0.4.1] - 2024-02-27

### 新增

- 支持自定义快捷操作 shortcuts 配置

### 修复

- 修复 popup 快捷键点击内容为空的问题
- 修复翻译问题
- 修复多余的控制台日志

## [0.4.0] - 2024-02-21

### ✨ 重要新特性 - AI 思考状态展示

> 现在您可以实时查看 AI 的思考过程，增强用户体验和交互透明度！

- ✅ 支持在对话过程中**实时展示 AI 的思考状态**
- ✅ 通过 `think` 事件自动处理思考状态
- ✅ 提供 `isThinking` 工具函数判断当前是否处于思考状态

![](https://pic-bed-1302552283.cos.ap-guangzhou.myqcloud.com/undefinedClipboard-20250226-073433-713.gif?imageSlim)

### ⚠️ 破坏性变动 (Breaking Changes)

#### ChatHelper 接口更新

- ChatHelper 构造函数新增 `messages` 参数，用于在 think 事件中支持思考状态展示的更新
- 回调函数 `handleClear` 必须使用 `messages.value.splice(0)` 方式清空消息，因为 `messages` 将作为引用类型传给 ChatHelper
- 回调函数 `handleReceiveMessage` 新增 `cover` 参数，支持消息内容的增量更新和全量覆盖
- 回调函数 `handleEnd` 增强错误处理，支持检测思考状态

因此，升级后，请参考以下示例代码更新您的代码：

```ts
// ChatHelper 初始化示例
const messages = ref<Message[]>([]);
const chatHelper = new ChatHelper(
  url,
  handleStart,
  handleReceiveMessage,
  handleEnd,
  handleError,
  messages.value // 新增：消息数组引用
);

// handleReceiveMessage 使用示例
const handleReceiveMessage = (
  message: string,
  id: number | string,
  cover?: boolean // 新增：控制消息更新模式
) => {
  const currentMessage = messages.value.at(-1);
  if (currentMessage?.status === MessageStatus.Loading) {
    currentMessage.content = message;
    currentMessage.status = MessageStatus.Success;
  } else if (currentMessage?.status === MessageStatus.Success) {
    currentMessage.content = cover ? message : currentMessage.content + message;
  }
};

// handleEnd 使用示例结合思考状态检测
import { isThinking } from '@blueking/ai-blueking';

const handleEnd = (id: number | string) => {
  loading.value = false;
  const currentMessage = messages.value.at(-1);
  if (
    currentMessage?.status === MessageStatus.Loading ||
    isThinking(currentMessage?.content || '')
  ) {
    currentMessage.content = '聊天内容已中断';
    currentMessage.status = MessageStatus.Error;
  }
};

// handleClear 使用示例
const handleClear = () => {
  messages.value.splice(0); // 必须使用这种方式清空消息, 不能使用 messages.value = []，否则 ChatHelper 无法感知消息数组的变化
};
```

### 其他新增功能

#### 快捷操作事件

- 新增 `shortcut-click` 事件，响应快捷操作按钮点击
- 事件返回完整的操作信息：`{ type, label, cite, prompt }`

```ts
<ai-blueking @shortcut-click="handleShortcutClick" />

const handleShortcutClick = (data: { type: string; label: string; cite: string; prompt: string }) => {
  console.log('操作类型:', data.type);
  console.log('操作标签:', data.label);
  console.log('引用内容:', data.cite);
  console.log('发送提示词:', data.prompt);
};
```

## [0.3.29] - 2024-02-26

### 修复

- 修复快捷操作按钮点击无效的问题
- 修复 AI 在回复过程中，点击清空按钮导致状态混乱问题

## [0.3.28] - 2024-02-25

### 更新

- 调整 AI 弹框默认的高度
  - 默认高度为 100% 浏览器高度

## [0.3.27] - 2024-02-24

### 修复

- popup 弹窗优化
  - 修复弹窗位置计算错误
  - 修复弹窗在 clickoutside 时不会关闭的问题

- model 窗口位置优化
  - 修复 model 窗口在屏幕大小发生变化时位置计算错误的问题

## [0.3.26] - 2024-02-20

### 新增

- Alert 提示配置增强
  - 支持传入完整的 Alert 组件配置项
  - 向下兼容原有的 string 类型配置

使用示例：

```vue
// 字符串方式（原有用法）
<AIBlueking alert="这是一条提示" />

// 对象方式（新增用法）
<AIBlueking
  :alert="{
    title: '这是一条提示',
    theme: 'warning', // 支持 'primary' | 'success' | 'warning' | 'danger'
    closable: true, // 是否可关闭
    closeText: '关闭', // 关闭按钮文字
    // ... 其他 Alert 组件支持的属性
  }"
/>
```

## [0.3.25] - 2024-02-19

### 优化

- 优化快捷操作按钮样式
  - 更新整体 UI 设计，支持快捷按钮组直接快速交互和唤起

![](https://pic-bed-1302552283.cos.ap-guangzhou.myqcloud.com/undefinedClipboard-20250214-094809-139.gif?imageSlim)

## [0.3.24] - 2024-02-14

### 新增

- 快捷操作功能
  - 支持解释和翻译两种快捷操作
  - 通过 `AIBlueking` 组件的 `quickActions` 方法调用

使用示例：

```ts
interface AIBluekingExpose {
  quickActions: (type: 'explanation' | 'translate', content: string) => void;
  setInputMessage: (val: string) => void;
}

// 解释文本
aiBlueking.value?.quickActions('explanation', '内容');
// 翻译文本
aiBlueking.value?.quickActions('translate', '内容');
```
