# 迁移到 1.0 版本

本指南将帮助你将应用从 AI 小鲸 0.x 版本顺利迁移到 1.0 版本。

::: danger 重要依赖升级提醒
aidev_agent 必须同步升级到 1.0.0b1 或更高版本！

不兼容的 aidev_agent 版本将导致组件无法正常工作。更新 1.0 后，小鲸大部分的代码不需要做任何改动，但是有以下变化需要了解。
:::

## 主要变更概览

1.0 版本是一次重大更新，虽然保持了 API 的基本兼容性，但内部实现进行了优化，特别是在与蓝鲸AI平台（AIDev）的集成方面有显著变化：

- 开场白和预设对话内容从智能体配置接口获取，这意味着原来使用 `defaultMessages` 属性的需要去除，具体参考[预设对话内容](/guide/advanced-usage/default-messages.md)
- 依赖更新：必须同步升级 AI-SDK，版本不匹配将导致组件无法正常使用
- 整体架构优化，提供更流畅的用户体验

## 详细变更清单

### 1. 预设对话内容获取方式变更

在 0.x 版本中，预设对话由前端通过 `defaultMessages` 属性设置。而在 1.0 版本中，开场白和预设对话内容将从智能体配置接口直接获取，无需前端设置。

```vue
<!-- 0.x 版本：前端设置预设对话 -->
<AIBlueking :default-messages="[
  { role: 'user', content: '你好' },
  { role: 'assistant', content: '您好！有什么我可以帮助您的吗？' }
]"/>

<!-- 1.0 版本：无需设置，从智能体配置获取 -->
<AIBlueking :url="apiUrl" />
```

### 2. 开场白、预设问题与提示词整合

1.0 版本的开场白文本将从智能体配置的接口获取

1.0 版本中，从智能体配置接口获取的预设问题(`predefinedQuestions`)会与前端提供的提示词(`prompts`)合并展示。

```vue
<!-- 1.0 版本：prompts会与智能体配置的predefinedQuestions合并 -->
<AIBlueking :url="apiUrl" :prompts="['如何使用...', '帮我解释...']" />
```

### 3. 依赖版本要求

1.0 版本小鲸必须同步升级 aidev_agent >= 1.0.0b1。版本不匹配将导致组件无法正常使用。

```bash
# 安装新版 AI 小鲸组件
npm install @blueking/ai-blueking@^1.0.0
```

### 4. 方法名称保持一致

1.0 版本保持了大部分API方法名称不变，并添加了一些新的方法，方便编程控制，主要暴露的方法包括：

- `handleShow`: 显示AI小鲸窗口
- `handleClose`: 关闭AI小鲸窗口
- `handleStop`: 停止内容生成
- `handleSendMessage`: 发送消息
- `handleShortcutClick`: 模拟点击快捷操作
- `handleDelete`: 删除消息
- `handleRegenerate`: 重新生成消息
- `handleResend`: 重新发送消息
- ` updateRequestOptions`: 更新 `requestOptions` 

### 5. 会话初始化流程变更

在 1.0 版本中，会话初始化会自动获取智能体的配置信息，包括开场白、预设问题等：

```javascript
// 内部会话初始化流程（用户无需手动调用）
const initSession = async () => {
  // 创建会话...
  
  // 获取智能体配置信息
  const { conversationSettings, promptSetting } = await getAgentInfoApi()
  openingRemark.value = conversationSettings?.openingRemark || ''
  predefinedQuestions.value = conversationSettings?.predefinedQuestions || []
  
  // 应用预设角色提示词
  if (promptSetting?.content?.length) {
    await handleCompleteRole(sessionCode.value, promptSetting.content)
  }
};
```

## 迁移步骤

1. **更新依赖包**：
   ```bash
   # 更新 AI 小鲸组件 (务必确保 aidev_agent >= 1.0.0b1)
   npm install @blueking/ai-blueking@^1.0.0
   ```

2. **移除预设对话设置**：
   ```html
   <!-- 0.x 版本 -->
   <AIBlueking 
     :url="apiUrl"
     :default-messages="myDefaultMessages"
   />
   
   <!-- 1.0 版本：移除default-messages，从接口获取 -->
   <AIBlueking :url="apiUrl" />
   ```

3. **确保url属性正确设置**，这是获取智能体配置的关键：
   ```vue
   <AIBlueking :url="'https://your-agent-api-endpoint'" />
   ```

4. **保持事件处理器不变**，事件名称保持兼容：
   ```vue
   <AIBlueking
     @show="onShow"
     @close="onClose"
     @stop="onStop"
     @shortcut-click="onShortcutClick"
     @receive-start="onReceiveStart"
     @receive-text="onReceiveText"
     @receive-end="onReceiveEnd"
     @send-message="onSendMessage"
   />
   ```

5. **调整方法调用方式**，确保使用正确的方法名：
   ```javascript
   // 0.x和1.0版本均可用
   aiBlueking.value.handleShow();
   aiBlueking.value.handleStop();
   aiBlueking.value.handleSendMessage('你好');
   ```

## 智能体配置说明

1.0 版本需要在蓝鲸AI平台（AIDev）上正确配置智能体，以便组件能够获取必要的配置信息：

1. **开场白配置**：在智能体配置页面设置 `openingRemark` 字段
2. **预设问题配置**：在智能体配置页面设置 `predefinedQuestions` 字段
3. **预设角色配置**：在智能体配置页面设置 `promptSetting.content` 字段

如果未提供这些配置，组件将使用默认值和前端提供的配置。

## 常见问题

### 1. 开场白或预设问题未显示

检查智能体配置是否正确，以及URL是否正确指向了有效的智能体API端点。

### 2. 如何查看完整会话内容

可以通过组件实例的`sessionContents`属性获取当前会话的完整内容：

```javascript
const contents = aiBlueking.value.sessionContents;
console.log('当前会话内容:', contents);
```

### 3. 组件显示白屏或功能异常

检查 aidev_agent 版本是否正确升级到 1.0.0b1 或更高版本。不兼容的版本是导致大多数问题的主要原因。


## 联系与支持

如果在迁移过程中遇到任何问题，请联系我们的技术支持团队或在 GitHub 仓库提交 Issue。 