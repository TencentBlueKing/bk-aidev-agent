# 更新日志

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
  <AIBlueking :teleport-to="#ai-container"/>
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
  <AIBlueking :default-minimize="true"/> <!-- Nimbus 组件初始以最小化状态显示 -->
</template>
```

### 支持 Chat 接口添加自定义参数

- 支持 `requestOptions` 传递自定义选项到发送请求
```html
<template>
<AIBlueking :request-options="{
    headers: {
      preset: 'QA',
    },
    data: {
      preset: 'QA',
    },
  }"/>
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

<script setup lang="ts">
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
  messages.value  // 新增：消息数组引用
);

// handleReceiveMessage 使用示例
const handleReceiveMessage = (
  message: string,
  id: number | string,
  cover?: boolean  // 新增：控制消息更新模式
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
  if (currentMessage?.status === MessageStatus.Loading || isThinking(currentMessage?.content || '')) {
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
    theme: 'warning',    // 支持 'primary' | 'success' | 'warning' | 'danger'
    closable: true,      // 是否可关闭
    closeText: '关闭',   // 关闭按钮文字
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
