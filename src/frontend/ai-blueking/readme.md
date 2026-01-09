# AI 小鲸 (AI Blueking) 使用文档

<p align="center">
  <img src="https://pic-bed-1302552283.cos.ap-guangzhou.myqcloud.com/undefinedai-logo.svg?imageSlim" alt="AI 小鲸" width="128" height="128">
</p>

<p align="center">
  <a href="https://github.com/blueking/ai-blueking"><img src="https://img.shields.io/badge/版本-1.3.2-blue" alt="版本"></a>
  <a href="./LICENSE"><img src="https://img.shields.io/badge/许可证-MIT-green" alt="许可证"></a>
</p>

## 简介

AI 小鲸是一个智能对话组件，支持 Vue2/Vue3 框架，提供丰富的交互功能和灵活的配置选项。只需简单配置，即可快速接入智能对话能力，提升应用的用户体验。

## 特性

- **实时对话**：支持流式输出，让对话更自然流畅
- **多会话管理**：支持创建、切换、管理多个聊天会话
- **内容引用**：选中文本即可快速引用并提问
- **快捷操作**：支持预设常用功能，支持自定义表单交互
- **分享功能**：支持分享会话内容，生成分享链接
- **可拖拽界面**：自由调整窗口位置和大小
- **快捷键支持**：Cmd/Ctrl + I 快速切换面板显示/隐藏
- **开箱即用**：传入 Agent 地址即可快速接入业务
- **跨框架支持**：同时支持 Vue2 和 Vue3 框架

## 安装

```bash
npm install @blueking/ai-blueking
```

或

```bash
yarn add @blueking/ai-blueking
```

## 基本使用

### Vue 3

```vue
<template>
  <div>
    <button @click="showAI">打开 AI 小鲸</button>

    <AIBlueking
      ref="aiBlueking"
      :url="apiUrl"
      @show="handleShow"
      @close="handleClose"
    />
  </div>
</template>

<script lang="ts" setup>
  import { ref } from 'vue';
  import AIBlueking from '@blueking/ai-blueking';
  import '@blueking/ai-blueking/dist/vue3/style.css';

  const aiBlueking = ref(null);
  const apiUrl = 'https://your-api-endpoint.com/assistant/';

  const showAI = () => {
    aiBlueking.value?.handleShow();
  };

  const handleShow = () => {
    console.log('AI 小鲸已显示');
  };

  const handleClose = () => {
    console.log('AI 小鲸已关闭');
  };
</script>
```

### Vue 2

```vue
<template>
  <div>
    <button @click="showAI">打开 AI 小鲸</button>

    <AIBlueking
      ref="aiBlueking"
      :url="apiUrl"
      @show="handleShow"
      @close="handleClose"
    />
  </div>
</template>

<script>
  import AIBlueking from '@blueking/ai-blueking/vue2';
  import '@blueking/ai-blueking/dist/vue2/style.css';

  export default {
    components: {
      AIBlueking,
    },
    data() {
      return {
        apiUrl: 'https://your-api-endpoint.com/assistant/',
      };
    },
    methods: {
      showAI() {
        this.$refs.aiBlueking.handleShow();
      },
      handleShow() {
        console.log('AI 小鲸已显示');
      },
      handleClose() {
        console.log('AI 小鲸已关闭');
      },
    },
  };
</script>
```

## 属性 (Props)

| 属性名                     | 类型                           | 默认值    | 描述                                                          |
| -------------------------- | ------------------------------ | --------- | ------------------------------------------------------------- |
| url                        | String                         | ''        | AI 服务接口地址，必须设置                                     |
| enablePopup                | Boolean                        | true      | 是否启用选中文本后的弹出操作窗口                              |
| shortcuts                  | IShortcut[]                    | []        | 快捷操作列表，支持自定义表单                                  |
| shortcutLimit              | Number                         | -         | 快捷操作显示数量限制                                          |
| shortcutFilter             | Function                       | -         | 快捷操作过滤函数，签名：`(shortcut, selectedText) => boolean` |
| prompts                    | String[]                       | []        | 预设提示词列表                                                |
| requestOptions             | Object                         | {}        | 自定义请求选项，可设置 headers、data、context                 |
| defaultMinimize            | Boolean                        | false     | Nimbus 组件初始是否处于最小化状态                             |
| teleportTo                 | String                         | 'body'    | 将组件传送到的 DOM 节点选择器                                 |
| draggable                  | Boolean                        | true      | 是否可拖拽                                                    |
| defaultWidth               | Number                         | -         | 默认宽度                                                      |
| defaultHeight              | Number                         | -         | 默认高度                                                      |
| defaultTop                 | Number                         | -         | 默认顶部位置                                                  |
| defaultLeft                | Number                         | -         | 默认左侧位置                                                  |
| maxWidth                   | Number \| String               | 1000      | 最大宽度                                                      |
| showHistoryIcon            | Boolean                        | true      | 是否显示历史会话图标                                          |
| showNewChatIcon            | Boolean                        | true      | 是否显示新建聊天图标                                          |
| hideDefaultTrigger         | Boolean                        | false     | 是否隐藏默认的 AI 小鲸触发按钮                                |
| hideNimbus                 | Boolean                        | false     | 是否隐藏 Nimbus 悬浮球                                        |
| hideHeader                 | Boolean                        | false     | 是否隐藏头部                                                  |
| disabledInput              | Boolean                        | false     | 是否禁用输入框                                                |
| nimbusSize                 | 'small' \| 'normal' \| 'large' | 'normal'  | Nimbus 悬浮球大小                                             |
| placeholder                | String                         | ''        | 自定义输入框占位符文本                                        |
| miniPadding                | Number                         | 0         | 压缩状态下的边距                                              |
| title                      | String                         | ''        | 自定义标题                                                    |
| helloText                  | String                         | ''        | 自定义问候语                                                  |
| extCls                     | String                         | ''        | 额外的 CSS 类名                                               |
| initialSessionCode         | String                         | ''        | 初始会话代码                                                  |
| autoSwitchToInitialSession | Boolean                        | false     | 是否自动切换到初始会话                                        |
| loadRecentSessionOnMount   | Boolean                        | false     | 组件挂载时是否加载最近会话                                    |
| dropdownMenuConfig         | Object                         | {}        | 下拉菜单配置（showRename、showAutoGenerate、showShare）       |
| showCompressionIcon        | Boolean                        | true      | 是否显示压缩图标                                              |
| showMoreIcon               | Boolean                        | true      | 是否显示更多图标                                              |
| defaultChatInputPosition   | 'bottom' \| undefined          | undefined | 默认输入框位置                                                |

## 快捷操作 (Shortcuts)

快捷操作使用 `IShortcut` 接口，支持自定义表单交互。**注意：v1.1.0 版本起，快捷操作不再使用前端拼接 prompt 的方式，而是将表单数据作为结构化数据发送到后端处理。**

### IShortcut 接口定义

```typescript
interface IShortcut {
  id: string; // 快捷操作的唯一标识符
  name: string; // 显示的操作名称
  alias?: string; // 显示别名，优先于 name 显示（v1.3.2 新增）
  icon?: string; // 图标类名（如：'bkai-icon bkai-translate'）
  iconRender?: (h) => VNode; // 自定义图标渲染函数
  mode?: 'simple' | 'advanced'; // 指令模式，默认 advanced
  hideFooter?: boolean; // 是否隐藏底部按钮区域
  enableFillBack?: boolean; // 是否在划词弹窗中显示（v1.3.2 新增）
  components: Array<{
    // 表单组件配置
    type: string; // 组件类型：'text' | 'textarea' | 'number' | 'select'
    key: string; // 表单项键名
    name?: string; // 表单项显示名称
    placeholder?: string; // 占位文本
    default?: any; // 默认值
    required?: boolean; // 是否必填
    fillBack?: boolean; // 是否将选中文本填充到该组件（v1.3.2 增强）
    fillRegx?: string | RegExp; // 用于从选中文本提取的正则表达式（v1.3.2 新增）
    rows?: number; // 输入框行数（textarea 类型）
    min?: number; // 最小值（number 类型）
    max?: number; // 最大值（number 类型）
    options?: Array<{
      // 下拉选项（select 类型）
      label: string;
      value: string | number;
    }>;
    hide?: boolean; // 是否隐藏该组件
    mode?: 'simple' | 'advanced'; // 单个组件的展示模式
    showSendButton?: boolean; // 是否显示发送按钮
  }>;
}
```

### 快捷操作配置示例

````javascript
const shortcuts = [
  {
    id: 'translate',
    name: '翻译',
    alias: '智能翻译', // v1.3.2: 显示别名而非原始名称
    icon: 'bkai-icon bkai-translate',
    enableFillBack: true, // v1.3.2: 允许在划词弹窗中显示
    components: [
      {
        type: 'textarea',
        key: 'text',
        name: '待翻译文本',
        fillBack: true, // 自动填充选中文本
        placeholder: '请输入或选中需要翻译的文本',
      },
      {
        type: 'select',
        key: 'targetLang',
        name: '目标语言',
        options: [
          { label: '中文', value: 'zh' },
          { label: '英文', value: 'en' },
          { label: '日文', value: 'jp' },
        ],
        placeholder: '请选择目标语言',
      },
    ],
  },
  {
    id: 'explain',
    name: '解释代码',
    icon: 'bkai-icon bkai-code',
    enableFillBack: true,
    components: [
      {
        type: 'textarea',
        key: 'code',
        name: '代码内容',
        fillBack: true,
        fillRegx: '```[\\s\\S]*?```|`[^`]+`', // v1.3.2: 只提取代码块内容
        placeholder: '请输入或选中需要解释的代码',
        rows: 5,
      },
    ],
  },
  {
    id: 'extract_email',
    name: '提取邮箱',
    alias: '邮箱提取器', // v1.3.2: 显示更友好的名称
    icon: 'bkai-icon bkai-email',
    enableFillBack: true,
    components: [
      {
        type: 'textarea',
        key: 'content',
        name: '文本内容',
        fillBack: true,
        fillRegx: '[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}', // v1.3.2: 只提取邮箱地址
        placeholder: '选中文本后自动提取邮箱地址',
      },
    ],
  },
];
````

### 后端接收的数据格式

```javascript
{
  "property": {
    "extra": {
      "command": "translate",  // 快捷操作 ID
      "context": [
        { "key": "text", "value": "需要翻译的文本" },
        { "key": "targetLang", "value": "en" }
      ]
    }
  }
}
```

## 事件 (Events)

| 事件名                | 参数                                                     | 描述                         |
| --------------------- | -------------------------------------------------------- | ---------------------------- |
| show                  | -                                                        | 窗口显示时触发               |
| close                 | -                                                        | 窗口关闭时触发               |
| stop                  | -                                                        | 停止生成内容时触发           |
| shortcut-click        | { shortcut: IShortcut, source: 'popup' \| 'main' }       | 点击快捷操作时触发           |
| session-initialized   | { openingRemark: string, predefinedQuestions: string[] } | 会话初始化完成时触发         |
| init-session-finished | -                                                        | 会话初始化流程完全结束时触发 |
| receive-start         | -                                                        | AI 开始接收响应时触发        |
| receive-text          | text: string                                             | 接收到文本片段时触发         |
| receive-end           | -                                                        | 响应接收完成时触发           |
| send-message          | message: string                                          | 发送消息时触发               |
| drag-stop             | { x, y, width, height }                                  | 拖拽结束时触发               |
| resize-stop           | { x, y, width, height }                                  | 调整大小结束时触发           |
| dragging              | { x, y, width, height }                                  | 拖拽过程中触发               |
| resizing              | { x, y, width, height }                                  | 调整大小过程中触发           |
| sdk-error             | { apiName, code, message, data }                         | SDK 错误时触发               |
| transfer-messages     | messageIds: string[]                                     | 转人工消息时触发             |
| share-messages        | messageIds: string[]                                     | 分享消息时触发               |

## 方法 (Methods)

| 方法名                | 参数                                            | 返回值                              | 描述                                 |
| --------------------- | ----------------------------------------------- | ----------------------------------- | ------------------------------------ |
| handleShow            | sessionCode?: string, forceNewSession?: boolean | Promise\<void\>                     | 显示窗口，可指定会话或强制创建新会话 |
| handleClose           | -                                               | void                                | 关闭窗口                             |
| handleStop            | -                                               | void                                | 停止当前正在生成的内容               |
| handleSendMessage     | message: string                                 | void                                | 发送消息                             |
| focusInput            | -                                               | void                                | 聚焦输入框                           |
| addNewSession         | sessionCode?: string                            | Promise\<ISessionEditItem\>         | 创建新会话                           |
| updateSessionName     | sessionCode: string, newName: string            | Promise\<ISessionEditItem \| null\> | 更新会话名称                         |
| switchToSession       | sessionCode: string                             | Promise\<boolean\>                  | 切换到指定会话                       |
| getSessionList        | -                                               | Promise\<any[]\>                    | 获取会话列表                         |
| setCurrentSession     | sessionCode: string                             | void                                | 设置当前会话                         |
| updatePosition        | x: number, y: number                            | void                                | 更新窗口位置                         |
| updateSize            | width: number, height: number                   | void                                | 更新窗口大小                         |
| updatePositionAndSize | x: number, y: number, w: number, h: number      | void                                | 同时更新位置和大小                   |
| updateRequestOptions  | options: any                                    | void                                | 更新请求配置                         |

## 暴露属性 (Exposed Properties)

| 属性名          | 类型                     | 描述                                           |
| --------------- | ------------------------ | ---------------------------------------------- |
| sessionContents | Ref\<ISessionContent[]\> | 当前会话的消息内容列表                         |
| agentInfo       | Ref\<IAgentInfo\>        | 智能体的配置信息，包含名称、问候语、快捷指令等 |

### agentInfo 使用示例

```vue
<template>
  <div>
    <button @click="showAgentInfo">查看智能体信息</button>
    <AIBlueking
      ref="aiBlueking"
      :url="apiUrl"
    />
  </div>
</template>

<script setup>
  import { ref } from 'vue';
  import AIBlueking from '@blueking/ai-blueking';

  const aiBlueking = ref(null);
  const apiUrl = 'https://your-api-endpoint.com/assistant/';

  const showAgentInfo = () => {
    const info = aiBlueking.value?.agentInfo;
    console.log('智能体名称:', info?.name);
    console.log('问候语:', info?.openingRemark);
    console.log('快捷指令:', info?.commands);
    console.log('会话配置:', info?.conversationSettings);
  };
</script>
```

## 高级用法

### 配置快捷操作

```vue
<template>
  <AIBlueking
    ref="aiBlueking"
    :url="apiUrl"
    :shortcuts="shortcuts"
    :shortcut-filter="shortcutFilter"
    @shortcut-click="handleShortcutClick"
  />
</template>

<script setup>
  import { ref } from 'vue';
  import AIBlueking from '@blueking/ai-blueking';
  import '@blueking/ai-blueking/dist/vue3/style.css';

  const aiBlueking = ref(null);
  const apiUrl = 'https://your-api-endpoint.com/assistant/';

  const shortcuts = [
    {
      id: 'translate',
      name: '翻译',
      icon: 'bkai-icon bkai-translate',
      components: [
        {
          type: 'textarea',
          key: 'text',
          name: '待翻译文本',
          fillBack: true,
          placeholder: '请输入或选中需要翻译的文本',
        },
        {
          type: 'select',
          key: 'targetLang',
          name: '目标语言',
          default: 'en',
          options: [
            { label: '英文', value: 'en' },
            { label: '中文', value: 'zh' },
          ],
        },
      ],
    },
  ];

  // 根据选中文本过滤快捷操作
  const shortcutFilter = (shortcut, selectedText) => {
    // 只有选中文本长度在合理范围内才显示翻译操作
    if (shortcut.id === 'translate') {
      return selectedText && selectedText.length > 0 && selectedText.length < 1000;
    }
    return true;
  };

  const handleShortcutClick = data => {
    console.log('快捷操作:', data.shortcut.name);
    console.log('来源:', data.source); // 'popup' 或 'main'
  };
</script>
```

### 多会话管理

```vue
<template>
  <div>
    <button @click="createNewSession">新建会话</button>
    <button @click="showSessionList">查看会话列表</button>

    <AIBlueking
      ref="aiBlueking"
      :url="apiUrl"
      :show-history-icon="true"
      :show-new-chat-icon="true"
      :load-recent-session-on-mount="true"
      @session-initialized="onSessionInitialized"
    />
  </div>
</template>

<script setup>
  import { ref } from 'vue';
  import AIBlueking from '@blueking/ai-blueking';
  import '@blueking/ai-blueking/dist/vue3/style.css';

  const aiBlueking = ref(null);
  const apiUrl = 'https://your-api-endpoint.com/assistant/';

  // 创建新会话并打开窗口
  const createNewSession = async () => {
    await aiBlueking.value?.handleShow(undefined, true);
  };

  // 获取会话列表
  const showSessionList = async () => {
    const list = await aiBlueking.value?.getSessionList();
    console.log('会话列表:', list);
  };

  // 切换到指定会话
  const switchSession = async sessionCode => {
    await aiBlueking.value?.switchToSession(sessionCode);
  };

  // 更新会话名称
  const renameSession = async (sessionCode, newName) => {
    await aiBlueking.value?.updateSessionName(sessionCode, newName);
  };

  const onSessionInitialized = data => {
    console.log('开场白:', data.openingRemark);
    console.log('预设问题:', data.predefinedQuestions);
  };
</script>
```

### 自定义请求配置

```vue
<template>
  <AIBlueking
    ref="aiBlueking"
    :url="apiUrl"
    :request-options="requestOptions"
  />
</template>

<script setup>
  import { computed } from 'vue';

  const apiUrl = 'https://your-api-endpoint.com/assistant/';

  // 支持静态配置
  const requestOptions = {
    headers: {
      'X-Custom-Header': 'value',
    },
    data: {
      preset: 'QA',
    },
    // context 支持静态对象或动态函数
    context: () => ({
      userId: getCurrentUserId(),
      timestamp: Date.now().toString(),
    }),
  };
</script>
```

### 编程式控制窗口

```vue
<template>
  <div>
    <button @click="moveToCorner">移动到右上角</button>
    <button @click="setLargeSize">设置大尺寸</button>

    <AIBlueking
      ref="aiBlueking"
      :url="apiUrl"
      :draggable="true"
      :default-width="400"
      :default-height="500"
      @drag-stop="onDragStop"
      @resize-stop="onResizeStop"
    />
  </div>
</template>

<script setup>
  import { ref } from 'vue';
  import AIBlueking from '@blueking/ai-blueking';

  const aiBlueking = ref(null);
  const apiUrl = 'https://your-api-endpoint.com/assistant/';

  const moveToCorner = () => {
    const x = window.innerWidth - 420;
    const y = 20;
    aiBlueking.value?.updatePosition(x, y);
  };

  const setLargeSize = () => {
    aiBlueking.value?.updateSize(600, 700);
  };

  const onDragStop = position => {
    console.log('拖拽结束:', position);
  };

  const onResizeStop = position => {
    console.log('调整大小结束:', position);
  };
</script>
```

### 隐藏默认触发器，自定义触发方式

```vue
<template>
  <div>
    <!-- 自定义触发按钮 -->
    <button
      class="my-ai-button"
      @click="openAI"
    >
      <span class="icon">🤖</span>
      打开 AI 助手
    </button>

    <AIBlueking
      ref="aiBlueking"
      :url="apiUrl"
      :hide-default-trigger="true"
      :hide-nimbus="true"
    />
  </div>
</template>

<script setup>
  import { ref } from 'vue';
  import AIBlueking from '@blueking/ai-blueking';

  const aiBlueking = ref(null);
  const apiUrl = 'https://your-api-endpoint.com/assistant/';

  const openAI = () => {
    aiBlueking.value?.handleShow();
  };
</script>
```

### 访问会话内容

```vue
<template>
  <div>
    <button @click="showSessionContents">显示会话内容</button>
    <AIBlueking
      ref="aiBlueking"
      :url="apiUrl"
    />
  </div>
</template>

<script setup>
  import { ref } from 'vue';
  import AIBlueking from '@blueking/ai-blueking';

  const aiBlueking = ref(null);
  const apiUrl = 'https://your-api-endpoint.com/assistant/';

  const showSessionContents = () => {
    const contents = aiBlueking.value?.sessionContents;
    console.log('当前会话内容:', contents);
  };
</script>
```

## 框架差异注意事项

### Vue 2 与 Vue 3 的区别

| 差异点       | Vue 3                                                | Vue 2                                                 |
| ------------ | ---------------------------------------------------- | ----------------------------------------------------- |
| 组件导入     | `import AIBlueking from '@blueking/ai-blueking'`     | `import AIBlueking from '@blueking/ai-blueking/vue2'` |
| 样式导入     | `import '@blueking/ai-blueking/dist/vue3/style.css'` | `import '@blueking/ai-blueking/dist/vue2/style.css'`  |
| 组件实例获取 | `aiBlueking.value?.handleShow()`                     | `this.$refs.aiBlueking.handleShow()`                  |
| 组件定义     | Composition API 或 Options API                       | Options API                                           |

## 常见问题

### Q: 如何实现选中文本弹出快捷操作？

A: 这是 AI 小鲸的内置功能，确保 `enablePopup` 设置为 `true`（默认值）即可。

### Q: 快捷操作表单数据如何传递给后端？

A: v1.1.0 版本起，表单数据以结构化方式发送到后端的 `property.extra.context` 字段中，后端需要根据 `command` 识别操作类型。

### Q: 如何禁用特定区域的快捷操作弹窗？

A: 在不希望弹出快捷指令的 HTML 元素上添加 `ai-blueking-hide` 属性即可。

### Q: 在 Vue 2 项目中遇到兼容性问题怎么办？

A: 确保使用正确的导入路径 `@blueking/ai-blueking/vue2` 和样式路径 `@blueking/ai-blueking/dist/vue2/style.css`。

## 许可证

[MIT 许可证](../../../LICENSE.txt)
