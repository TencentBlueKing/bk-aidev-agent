# AI 小鲸使用指南

## 目录

- [简介](#简介)
- [安装](#安装)
- [特性](#特性)
- [使用指南](#使用指南)
- [开发调试](#开发调试)

## 简介

AI 小鲸是一个智能对话组件,支持 Vue2/Vue3 框架,提供了丰富的交互功能和灵活的配置选项。

## 安装

```bash
npm i @blueking/ai-blueking
```

## 特性

- 支持 popup 弹框唤起
- 支持引用提问功能 
- 支持快捷提问(当前支持翻译、解释功能)
- 支持使用 `enablePopup` 属性控制弹框唤起(默认为 true)

## 使用指南

### 基础配置

#### 组件显示/隐藏控制

**注意：0.3.0 版本重大变更**

- 使用 `v-model:is-show` 绑定变量控制组件显示状态
- **不再使用 `v-if` 进行控制**

#### 消息发送回调

**注意：0.3.0 版本重大变更**

`handleSend _callback`函数现在接收一个对象参数:

```typescript
interface ISendData {
  content: string;  // 用户输入的内容
  cite?: string;    // 引用的内容(可选)
  prompt?: string;  // 使用的 prompt 模板(可选)
}
```

以下展示了如何处理新的 handleSend 回调，完整示例请参考 [Stream 模式](#stream-模式-vue3)

```typescript
const handleSend = (args: ISendData) => {
  // 记录当前消息记录
  const chatHistory = [...messages.value];

  // 添加用户消息
  messages.value.push({
    role: 'user',
    content: args.content,
    cite: args.cite,
  });

  // 根据参数构造输入内容
  const input = args.prompt 
    ? args.prompt                           // 如果有 prompt，直接使用
    : args.cite 
      ? `${args.content}: ${args.cite}`     // 如果有 cite，拼接 content 和 cite
      : args.content;                       // 否则只使用 content

  // 调用 AI 流式对话
  // 注：id 是唯一标识当前流，调用 chatHelper.stop 时需要传入
  chatHelper.stream(
    {
      inputs: {
        input,
        chat_history: chatHistory,
      },
    },
    1,
  );
};
```

### 模板渲染

#### 知识库列表渲染

可使用特定模板渲染匹配的知识库列表,示例:

```html
<section class="knowledge-tips">
  <i class="ai-blueking-icon ai-blueking-angle-up"></i>
  <span class="knowledge-summary">
    <i class="ai-blueking-icon ai-blueking-help-document"></i>
    引用 4 篇资料作为参考
  </span>
  <a href="xxx" target="_blank" class="knowledge-link">
    1. vivo 容器平台如何实现资源超卖方案
    <i class="ai-blueking-icon ai-blueking-cc-jump-link"></i>
  </a>
</section>
```

#### 交互元素渲染

AI 小鲸支持渲染可点击的交互式 HTML 元素。以下是如何实现这一功能的指南：

- **渲染可点击元素**：使用带有 `ai-clickable` 类的 HTML 元素来创建可交互的组件。点击这些元素时，会触发组件的 `ai-click` 事件，并将 `data-ai` 属性的数据传递给事件处理程序。

- **示例**：

  ```html
  <button data-ai="{ type: 'button', data: 'xxx' }" class="ai-clickable">可点击的按钮</button>
  <a data-ai="{ type: 'link', data: 'link url' }" class="ai-clickable" href="void">可点击的链接</a>
  ```

- **事件处理**：点击后，`ai-click` 事件被触发。您可以通过 `data-ai` 属性传递数据，例如：

  ```javascript
  handleCustomButtonClick(dataAIValue) {
    // 假设 'aiRef' 是组件的引用
    const val = dataAIValue; //从 data-ai 属性获取的数据'
  
    ... // 业务处理逻辑，比如以下将`data-ai`上的字符串赋值到输入框
    aiRef.value?.setInputMessage(val); 
  }
  ```

这样，业务逻辑可以根据传递的数据进行二次处理，比如将 `data-ai` 上的字符串值设置到输入框中。

### 使用示例

#### Stream 模式 (Vue3)

不同框架，组件引入方式不同，具体可参考下面的的例子。这里使用 vue3 项目为例，来展示 stream 模式交互

参考完整示例代码:

```vue
<template>
  <AIBlueking
    v-model:is-show="isShow"
    :loading="loading"
    :messages="messages"
    @clear="handleClear"
    @send="handleSend"
    @stop="handleStop"
  />
</template>

<script lang="ts" setup>
  import { ref } from 'vue';
  import AIBlueking, { ChatHelper, RoleType, MessageStatus, isThinking } from '@blueking/ai-blueking';
  import '@blueking/ai-blueking/dist/vue3/style.css';

  interface ISendData {
    content: string; // 用户输入的内容
    cite?: string;   // 引用的内容
    prompt?: string; // 使用的 prompt 模板
  }

  const loading = ref(false);
  const messages = ref([]);
  const isShow = ref(false);

  // 聊天开始
  const handleStart = (id: number | string) => {
    loading.value = true;
    messages.value.push({
      role: RoleType.Assistant,
      content: '内容正在生成中...',
      status: MessageStatus.Loading,
    });
  };

  // 接收消息
  const handleReceiveMessage = (message: string, id: number | string, cover?: boolean) => {
    const currentMessage = messages.value.at(-1);
    if (currentMessage?.status === MessageStatus.Loading) {
      // 如果是loading状态，直接覆盖
      currentMessage.content = message;
      currentMessage.status = MessageStatus.Success;
    } else if (currentMessage?.status === MessageStatus.Success) {
      // 根据 cover 参数决定是追加还是覆盖
      currentMessage.content = cover ? message : currentMessage.content + message;
    }
  };

  // 聊天结束
  const handleEnd = (id: number | string) => {
    loading.value = false;
    const currentMessage = messages.value.at(-1);
    // 在 loading 状态或思考状态下终止时，标记为错误
    if (currentMessage?.status === MessageStatus.Loading || isThinking(currentMessage?.content || '')) {
      currentMessage.content = '聊天内容已中断';
      currentMessage.status = MessageStatus.Error;
    }
  };

  // 错误处理
  const handleError = (message: string, code: string | number, id: number | string) => {
    if (message.includes('user authentication failed')) {
      // 未登录，跳转登录
      const loginUrl = new URL(process.env.BK_LOGIN_URL);
      loginUrl.searchParams.append('c_url', location.origin);
      window.location.href = loginUrl.href;
    } else {
      // 处理错误消息
      const currentMessage = messages.value.at(-1);
      currentMessage.status = MessageStatus.Error;
      currentMessage.content = message;
      loading.value = false;
    }
  };

  const prefix = process.env.BK_API_URL_TMPL.replace('{api_name}', '<网关名>').replace('http', 'https');
  const chatHelper = new ChatHelper(
    `${prefix}/prod/bk_plugin/plugin_api/assistant/`,
    handleStart,
    handleReceiveMessage,
    handleEnd,
    handleError,
    messages.value,
  );

  // 清空消息
  const handleClear = () => {
    messages.value.splice(0); // 必须使用这种方式清空消息, 不能使用 messages.value = []，否则 ChatHelper 无法感知消息数组的变化
  };

  // 发送消息
  const handleSend = (args: ISendData) => {
    // 记录当前消息记录
    const chatHistory = [...messages.value];
    // 添加一条消息
    messages.value.push({
      role: 'user',
      content: args.content,
      cite: args.cite,
    });

    // 根据参数构造输入内容
    const input = args.prompt
      ? args.prompt // 如果有 prompt，直接使用
      : args.cite
        ? `${args.content}: ${args.cite}` // 如果有 cite，拼接 content 和 cite
        : args.content; // 否则只使用 content

    // ai 消息，id是唯一标识当前流，调用 chatHelper.stop 的时候需要传入
    chatHelper.stream(
      {
        inputs: {
          input,
          chat_history: chatHistory,
        },
      },
      1,
    );
  };

  // 暂停聊天
  const handleStop = () => {
    chatHelper.stop(1);
  };
</script>
```

#### 非 Stream 模式

##### Vue3 示例:

```vue
<template>
  <AIBlueking
    :background="background"
    :head-background="headBackground"
    :loading="loading"
    :messages="messages"
    :position-limit="positionLimit"
    :prompts="prompts"
    :scroll-loading="scrollLoading"
    :scroll-loading-end="scrollLoadingEnd"
    :size-limit="sizeLimit"
    :start-position="startPosition"
    @ai-click="handleAIClick"
    @choose-prompt="handleChoosePrompt"
    @clear="handleClear"
    @close="handleClose"
    @scroll-load="handleScrollLoad"
    @send="handleSend"
    @stop="handleStop"
  />
</template>
<script setup lang="ts">
  import { type ComponentInstance, ref } from 'vue';

  import AIBlueking, { type IPrompt, type IMessage, RoleType, MessageStatus } from '@blueking/ai-blueking';

  import '@blueking/ai-blueking/dist/vue3/style.css';

  // 展示的消息，其中 time 可以不传
  const messages = ref<IMessage[]>([
    {
      content: '1+1=?',
      time: '2023-08-12 10:28',
      role: RoleType.User,
    },
    {
      content: '1+1=3',
      time: '2024-08-07 14:29',
      role: RoleType.Assistant,
      status: MessageStatus.Error,
    },
    {
      content: '不对',
      time: '2024-08-12 09:29',
      role: RoleType.User,
    },
    {
      content: '1+1=2',
      time: '2024-08-12 09:31',
      role: RoleType.Assistant,
      status: MessageStatus.Loading,
    },
    {
      content: '对了',
      time: '2024-08-13 10:20',
      role: RoleType.User,
    },
    {
      content: '好的，任务已完成',
      time: '2024-08-13 10:23',
      role: RoleType.Assistant,
    },
  ]);
  // 内置 prompt
  const prompts = [
    {
      id: 1,
      content: '帮我计算1+1的结果',
    },
    {
      id: 2,
      content: '帮我计算2+2的结果',
    },
  ];

  // 处理ai消息的loading状态
  const loading = ref(false);
  // 聊天背景色
  const background = '#f5f7fa';
  // 头部背景色
  const headBackground = 'linear-gradient(267deg, #2dd1f4 0%, #1482ff 95%)';
  // 弹框位于屏幕四边的最小距离
  const positionLimit = {
    top: 0,
    bottom: 0,
    left: 0,
    right: 0,
  };
  // 组件最小尺寸
  const sizeLimit = {
    height: 320,
    width: 400,
  };
  // 初始位置
  const startPosition = {
    top: window.innerHeight - 560,
    bottom: 0,
    left: window.innerWidth - 400,
    right: 0,
  };
  // 向上滚动加载
  const scrollLoading = ref(false);
  const scrollLoadingEnd = ref(false);
  // 组件实例
  const aiRef = ref<ComponentInstance<typeof AIBlueking>>();

  const handleClear = () => {
    console.log('trigger clear');
  };

  const handleSend = (val: string) => {
    console.log('trigger send', val);
      // args 包含:
      // - content: 用户输入的内容
      // - cite: 引用的内容(可选)
      // - prompt: 使用的 prompt 模板(可选)
  };

  const handleStop = () => {
    console.log('trigger stop');
  };

  const handleScrollLoad = () => {
    scrollLoading.value = true;
    setTimeout(() => {
      // 模拟异步请求
      messages.value.unshift(
        ...[
          {
            content: '1+1=?',
            time: '2023-08-12 9:28',
            role: RoleType.User,
          },
          {
            content: '2',
            time: '2023-08-12 9:30',
            role: RoleType.Assistant,
          },
        ],
      );
      // 设置状态
      scrollLoading.value = false;
      scrollLoadingEnd.value = true;
    }, 1000);
  };

  const handleClose = () => {
    console.log('trigger close');
  };

  const handleChoosePrompt = (prompt: IPrompt) => {
    console.log('choose prompt', prompt);
  };

  const handleAIClick = (val: string) => {
    aiRef.value?.setInputMessage(val);
  };
</script>
```

##### Vue2 示例

Vue2 下，需要安装 npm 包，里面是 vue3 资源

```bash
npm i @blueking/ai-blueking
```

```vue
<template>
  <AIBlueking
    :background="background"
    :head-background="headBackground"
    :loading="loading"
    :messages="messages"
    :position-limit="positionLimit"
    :prompts="prompts"
    :size-limit="sizeLimit"
    :start-position="startPosition"
    @choose-prompt="handleChoosePrompt"
    @clear="handleClear"
    @close="handleClose"
    @send="handleSend"
    @scroll="handleScroll"
    @stop="handleStop"
  />
</template>
<script lang="ts">
  import { ref } from 'vue';

  import AIBlueking from '@blueking/ai-blueking/vue2';
  import '@blueking/ai-blueking/dist/vue2/style.css';

  export default {
    components: {
      AIBlueking,
    },
    data() {
      return {
        messages: [
          {
            content: '你好呀',
            role: 'assistant',
          },
          {
            content: '1+1=?',
            role: 'user',
          },
          {
            content: '1+1=3',
            role: 'assistant',
            status: 'error',
          },
          {
            content: '不对',
            role: 'user',
          },
          {
            content: '1+1=2',
            role: 'assistant',
            status: 'loading',
          },
          {
            content: '对了',
            role: 'user',
          },
          {
            content: '好的，任务已完成',
            role: 'assistant',
          },
        ],
        prompts: [
          {
            id: 1,
            content: '帮我计算1+1的结果',
          },
          {
            id: 2,
            content: '帮我计算2+2的结果',
          },
        ],
        loading: false,
        background: '#f5f7fa',
        headBackground: 'linear-gradient(267deg, #2dd1f4 0%, #1482ff 95%)',
        positionLimit: {
          top: 0,
          bottom: 0,
          left: 0,
          right: 0,
        },
        sizeLimit: {
          height: 320,
          width: 400,
        },
        startPosition: {
          top: window.innerHeight - 560,
          bottom: 0,
          left: window.innerWidth - 400,
          right: 0,
        },
      };
    },
    methods: {
      handleClear() {
        console.log('trigger clear');
      },
      handleSend(val: string) {
        console.log('trigger send', val);
      },
      handleClose() {
        console.log('trigger close');
      },
      handleChoosePrompt(prompt) {
        console.log('choose prompt', prompt);
      },
      handleScroll(event: Event) {
        console.log('trigger scroll', event);
      },
      handleStop() {
        console.log('trigger stop');
      },
    },
  };
</script>
```

## 开发调试

### 环境准备

1. 安装依赖

```bash
pnpm install
```

2. 启动开发服务器

```bash
pnpm run dev
```

3. 配置 hosts，以.xxx.com 结尾的域名,以正常获取cookie （xxx.com 即与接口地址相同的域名）

```bash
# 配置 hosts
echo "127.0.0.1 local.dev.xxx.com" >> /etc/hosts
```

### Demo 运行模式

提供两种运行模式:

#### 1. 静态演示模式 (Static Demo)

- 无需配置环境变量
- 展示所有功能和配置项
- 通过 `/playground/static.vue` 查看示例

#### 2. 动态演示模式 (Dynamic Demo)

- 需要配置本地环境
- 模拟真实使用场景
- 通过 `/playground/dynamic.vue` 查看示例

详细配置说明:

##### 环境要求

1. 配置本地 hosts


2. 设置必要的变量 （不需要手动修改，playground 中已经存在）

```bash
# 网站前缀
BK_API_GATEWAY_NAME = '<网关名称>'

# 静态资源路径
BK_API_URL_TMPL = 'https://{api_name}.example.com'

# 登录地址
BK_LOGIN_URL = 'http://login.example.com'
```

3. 登录态获取

- 需要在其他蓝鲸系统 SaaS 中获取登录态
- Demo 中简化了登录相关的代码实现
- 未登录时会自动跳转到登录页面

##### 开发注意事项

1. 动态模式下的 API 调用

- 所有 API 请求都会通过配置的网关进行转发
- 需要确保网关配置正确且有访问权限

2. 错误处理

- Demo 中包含了基本的错误处理逻辑
- 未登录状态会自动跳转到登录页面
- 其他错误会在界面上显示错误信息

3. 查看示例代码

- 动态演示代码位于 `/playground/dynamic.vue`
- 包含了完整的接口调用和错误处理逻辑