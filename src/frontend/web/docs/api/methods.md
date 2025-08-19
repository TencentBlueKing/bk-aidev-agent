# Methods

可以通过组件实例调用的方法列表。

::: warning 版本变更提示
1.0版本优化了内部实现，但保持了API的基本一致性，方便用户平滑升级。
:::

## 方法列表

| 方法名                          | 参数                                                                                                                  | 返回值          | 描述                                                                                                  |
| ------------------------------- | --------------------------------------------------------------------------------------------------------------------- | --------------- | ----------------------------------------------------------------------------------------------------- |
| `handleShow()`                  | -                                                                                                                     | `void`          | 主动显示 AI 小鲸窗口。                                                                                |
| `handleClose()`                 | -                                                                                                                     | `void`          | 关闭 AI 小鲸窗口。                                                                                    |
| `handleStop()`                  | -                                                                                                                     | `void`          | 停止当前正在进行的 AI 内容生成（流式输出）。                                                          |
| `handleSendMessage(message)`    | `message: string`                                                                                                     | `void`          | 发送消息到 AI 小鲸，可用于编程式触发对话。                                                            |
| `handleShortcutClick(shortcut)` | `shortcut: IShortcut`                                                                                                 | `void`          | 模拟点击快捷操作按钮，可用于编程式触发快捷操作。                                                      |
| `handleDelete(index)`           | `index: number`                                                                                                       | `void`          | 删除指定索引位置的消息。                                                                              |
| `handleRegenerate(index)`       | `index: number`                                                                                                       | `void`          | 重新生成指定索引位置的消息。                                                                          |
| `handleResend(index, options)`  | `index: number, options: {message: string, cite: string}`                                                             | `void`          | 重发指定索引位置的消息，可修改消息内容和引用内容。                                                    |
| `initSession()`                 | -                                                                                                                     | `Promise<void>` | 初始化会话，获取开场白和预设问题。                                                                    |
| `updateRequestOptions(options)` | `options: { url?: string; headers?: Record<string, string>; data?: any; context?: Array<{key: string, value: any}> }` | `void`          | 动态更新请求选项，可以修改API地址或请求参数。对于需要在运行时切换智能体或修改请求参数的场景非常有用。 |
| `updateRequestOptions(options)` | `options: { url?: string; headers?: Record<string, string>; data?: any; context?: Array<Object> }`                    | `void`          | 动态更新请求选项，可以修改API地址或请求参数。对于需要在运行时切换智能体或修改请求参数的场景非常有用。 |
| `focusInput()`                  | -                                                                                                                     | `void`          | **v1.1.1新增** 程序式聚焦输入框。可用于在特定时机主动聚焦到输入框，提升用户体验。                     |
| `addNewSession(sessionCode?)`   | `sessionCode?: string`                                                                                               | `Promise<ISessionEditItem>` | **v1.2.2新增** 创建一个新的聊天会话并返回会话信息。可选参数 sessionCode 用于指定会话代码，如果不提供则自动生成。 |
| `updateSessionName(sessionCode, newName)` | `sessionCode: string, newName: string`                                                                              | `Promise<ISessionEditItem>` | **v1.2.2新增** 更新指定会话的名称。 |
| `switchToSession(sessionCode)`  | `sessionCode: string`                                                                                                 | `Promise<void>` | **v1.2.2新增** 切换到指定代码的会话。 |
| `getSessionList()`              | -                                                                                                                     | `Promise<ISessionEditItem[]>` | **v1.2.2新增** 获取当前会话列表。 |

::: danger 已废弃方法
以下方法在相应版本中已被移除:

- `sendChat(options)` (v1.0.0): 已被 `handleSendMessage(options)` 替代
- `initSession()` (v1.1.0): 会话初始化现在自动处理，无需手动调用
  :::

## 调用示例

:::code-group

```vue [Vue 3]
<template>
  <AIBlueking ref="aiBlueking" :url="apiUrl" />
  <button @click="show">显示</button>
  <button @click="stop">停止生成</button>
  <button @click="send">发送消息</button>
  <button @click="focus">聚焦输入框</button>
</template>

<script lang="ts" setup>
  import { ref } from "vue"
  import { AIBlueking } from "@blueking/ai-blueking"

  const aiBlueking = ref(null)
  const apiUrl = "..."

  const show = () => aiBlueking.value?.handleShow()
  const stop = () => aiBlueking.value?.handleStop()
  const send = () => {
    aiBlueking.value?.handleSendMessage("你好，这是一条测试消息")
  }
  const focus = () => aiBlueking.value?.focusInput()
</script>
```

```vue [Vue 2]
<template>
  <div>
    <AIBlueking ref="aiBlueking" :url="apiUrl" />
    <button @click="show">显示</button>
    <button @click="stop">停止生成</button>
    <button @click="send">发送消息</button>
    <button @click="focus">聚焦输入框</button>
  </div>
</template>

<script>
  import { AIBlueking } from "@blueking/ai-blueking/vue2"

  export default {
    components: { AIBlueking },
    data: () => ({ apiUrl: "..." }),
    methods: {
      show() {
        this.$refs.aiBlueking.handleShow()
      },
      stop() {
        this.$refs.aiBlueking.handleStop()
      },
      send() {
        this.$refs.aiBlueking.handleSendMessage("你好，这是一条测试消息")
      },
      focus() {
        this.$refs.aiBlueking.focusInput()
      },
    },
  }
</script>
```

:::

## 动态更新请求选项

使用`updateRequestOptions`方法可以在运行时动态修改请求选项，例如切换API地址或添加自定义请求头：

```vue
<template>
  <AIBlueking ref="aiBlueking" :url="apiUrl" />
  <div class="controls">
    <button @click="switchAgent('agent1')">切换到智能体1</button>
    <button @click="switchAgent('agent2')">切换到智能体2</button>
    <button @click="addCustomHeader">添加自定义请求头</button>
  </div>
</template>

<script setup>
  import { ref } from "vue"
  import { AIBlueking } from "@blueking/ai-blueking"

  const aiBlueking = ref(null)
  const apiUrl = "https://api.example.com/agent1"

  // 切换不同的智能体API地址 （直接修改 AIblueking 的 url 参数也可以实现）
  const switchAgent = (agentId) => {
    const newUrl = `https://api.example.com/${agentId}`
    aiBlueking.value?.updateRequestOptions({
      url: newUrl,
    })

    // 可选：重新初始化会话以获取新智能体的配置
    aiBlueking.value?.initSession()
  }

  // 添加自定义请求头
  const addCustomHeader = () => {
    aiBlueking.value?.updateRequestOptions({
      headers: {
        "X-Custom-Header": "custom-value",
        Authorization: "Bearer your-token",
      },
      // 1.1版本可以添加context参数
      context: [{ language: "javascript" }, { scenario: "code_review" }],
    })
  }
</script>
```

## 触发快捷操作

您可以通过`handleShortcutClick`方法编程式地触发快捷操作：

```vue
<template>
  <AIBlueking ref="aiBlueking" :url="apiUrl" :shortcuts="shortcuts" />
  <button @click="triggerExplain">解释代码</button>
</template>

<script setup>
  import { ref } from 'vue';
  import { AIBlueking, type IShortcut } from '@blueking/ai-blueking';

  const aiBlueking = ref(null);
  const apiUrl = '...';

  const shortcuts = [
    {
      id: 'explain',
      name: '解释代码',
      icon: 'bkai-code',
      components: [
        {
          type: 'textarea',
          key: 'code',
          label: '代码内容',
          fillBack: true
        }
      ]
    }
  ];

  const triggerExplain = () => {
    // 找到对应ID的快捷操作
    const shortcut = shortcuts.find(s => s.id === 'explain');
    if (!shortcut) return;

    // 手动设置要填充的文本
    const textComponent = shortcut.components.find(c => c.fillBack);
    if (textComponent) {
      textComponent.selectedText = 'function example() { console.log("Hello World"); }';
    }

    // 显示AI小鲸窗口
    aiBlueking.value?.handleShow();

    // 触发快捷操作
    aiBlueking.value?.handleShortcutClick(shortcut);
  };
</script>
```

## 获取会话内容

组件实例暴露了`sessionContents`属性，可以获取当前会话的全部内容。

```vue
<template>
  <AIBlueking ref="aiBlueking" :url="apiUrl" />
  <button @click="getContents">获取会话内容</button>
</template>

<script setup>
  import { ref } from "vue"
  import { AIBlueking } from "@blueking/ai-blueking"

  const aiBlueking = ref(null)

  const getContents = () => {
    const contents = aiBlueking.value?.sessionContents
    console.log("当前会话内容:", contents)
  }
</script>
```

## 编程式会话管理

v1.2.2版本新增了编程式会话管理功能，允许通过组件实例方法创建、重命名和切换会话：

```vue
<template>
  <AIBlueking ref="aiBlueking" :url="apiUrl" />
  <div>
    <button @click="createAndRenameSession">创建并重命名会话</button>
    <button @click="switchToFirstSession">切换到第一个会话</button>
  </div>
</template>

<script setup>
  import { ref } from "vue"
  import { AIBlueking } from "@blueking/ai-blueking"

  const aiBlueking = ref(null)

  // 创建新会话并重命名
  const createAndRenameSession = async () => {
    try {
      // 1. 创建新会话
      const newSession = await aiBlueking.value?.addNewSession()
      
      // 2. 重命名会话
      if (newSession?.sessionCode) {
        await aiBlueking.value?.updateSessionName(newSession.sessionCode, "我的新会话")
        
        // 3. 切换到新会话
        await aiBlueking.value?.switchToSession(newSession.sessionCode)
      }
    } catch (error) {
      console.error("会话操作失败:", error)
    }
  }

  // 切换到第一个会话
  const switchToFirstSession = async () => {
    try {
      // 获取会话列表（需要通过其他方式获取，这里仅为示例）
      // 假设我们已经获取到了会话列表 sessionList
      const sessionList = [] // 实际使用中需要获取真实的会话列表
      
      if (sessionList.length > 0) {
        await aiBlueking.value?.switchToSession(sessionList[0].sessionCode)
      }
    } catch (error) {
      console.error("切换会话失败:", error)
    }
  }
</script>
```

更完整的使用示例请参见 [会话生命周期管理指南](/guide/advanced-usage/session-lifecycle)。