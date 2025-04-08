# AI 小鲸 (AI Blueking) 使用文档

<p align="center">
  <img src="./ai-logo.svg" alt="AI 小鲸" width="128" height="128">
</p>

<p align="center">
  <a href="https://github.com/blueking/ai-blueking"><img src="https://img.shields.io/badge/版本-0.5.2-blue" alt="版本"></a>
  <a href="./LICENSE"><img src="https://img.shields.io/badge/许可证-MIT-green" alt="许可证"></a>
</p>


## 简介

AI 小鲸是一个智能对话组件，支持 Vue2/Vue3 框架，提供丰富的交互功能和灵活的配置选项。只需简单配置，即可快速接入智能对话能力，提升应用的用户体验。

## 特性

- **实时对话**：支持流式输出，让对话更自然流畅
- **内容引用**：选中文本即可快速引用并提问
- **快捷操作**：支持预设常用功能和提示词
- **可拖拽界面**：自由调整窗口位置和大小
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
    AIBlueking
  },
  data() {
    return {
      apiUrl: 'https://your-api-endpoint.com/assistant/'
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
    }
  }
};
</script>
```

## 属性 (Props)

| 属性名 | 类型 | 默认值 | 描述 |
|--------|------|--------|------|
| url | String | '' | AI 服务接口地址，必须设置 |
| enablePopup | Boolean | true | 是否启用选中文本后的弹出操作窗口 |
| shortcuts | Array | [...] | 快捷操作列表 |
| prompts | Array | [] | 预设提示词列表 |
| requestOptions | Object | {} | 自定义请求选项，可设置headers和data属性，分别合并到请求头和请求体 |
| defaultMinimize | Boolean | false | 控制 Nimbus 组件初始是否处于最小化状态 |
| teleportTo | String | 'body' | 指定将 AI 小鲸组件传送到的 DOM 节点，默认为 body 元素 |
| sessionContents | Array | [] | 暴露当前会话内容，可用于外部访问和操作 |

### shortcuts 格式示例

```javascript
[
  {
    label: '解释',
    key: 'explanation',
    prompt: '解释一下内容： {{ SELECTED_TEXT }}',
    icon: 'icon-explanation'
  },
  {
    label: '翻译',
    key: 'translate',
    prompt: '翻译一下内容： {{ SELECTED_TEXT }}',
    icon: 'icon-translate'
  }
]
```

### prompts 格式示例

```javascript
[
  '请概括这段内容的主要观点',
  '请帮我分析这段文字中的问题',
  '请用简单的语言解释这个概念'
]
```

## 事件 (Events)

| 事件名 | 参数 | 描述 |
|--------|------|------|
| show | - | AI 小鲸窗口显示时触发 |
| close | - | AI 小鲸窗口关闭时触发 |
| stop | - | 停止生成内容时触发 |
| shortcut-click | shortcut: ShortCut | 点击快捷操作时触发，返回所点击的快捷操作对象 |

## 方法 (Methods)

| 方法名 | 参数 | 返回值 | 描述 |
|--------|------|--------|------|
| handleShow | - | - | 显示 AI 小鲸窗口 |
| handleStop | - | - | 停止当前正在生成的内容 |
| sendChat | options: {message, cite, shortcut} | - | 发送消息到 AI 小鲸 |
| handleShortcutClick | shortcut: ShortCut | - | 处理快捷操作点击 |

## 高级用法

### Vue 3 快捷操作演示

```vue
<template>
  <div>
    <div class="article">
      <h3>AI 技术的发展与应用</h3>
      <p>{{ articleContent }}</p>
    </div>
    
    <div class="quick-actions">
      <button @click="quickActions('解释', '解释一下这段内容：', articleTitle)">
        解释标题
      </button>
      <button @click="quickActions('翻译', '翻译成英文：', articleTitle)">
        翻译标题
      </button>
    </div>
    
    <AIBlueking ref="aiBlueking" :url="apiUrl" />
  </div>
</template>

<script lang="ts" setup>
import { ref } from 'vue';
import AIBlueking from '@blueking/ai-blueking';
import '@blueking/ai-blueking/dist/vue3/style.css';

const aiBlueking = ref(null);
const apiUrl = 'https://your-api-endpoint.com/assistant/';
const articleTitle = 'AI 技术的发展与应用';
const articleContent = '人工智能技术在近年来取得了突飞猛进的发展...';

const quickActions = (label, promptPrefix, cite) => {
  aiBlueking.value?.handleShow();
  
  aiBlueking.value?.sendChat({
    message: label,
    cite,
    shortcut: {
      label,
      key: label.toLowerCase(),
      prompt: `${promptPrefix} {{ SELECTED_TEXT }}`,
      icon: 'icon-explanation'
    }
  });
};
</script>
```

### Vue 2 快捷操作演示

```vue
<template>
  <div>
    <div class="article">
      <h3>AI 技术的发展与应用</h3>
      <p>{{ articleContent }}</p>
    </div>
    
    <div class="quick-actions">
      <button @click="quickActions('解释', '解释一下这段内容：', articleTitle)">
        解释标题
      </button>
      <button @click="quickActions('翻译', '翻译成英文：', articleTitle)">
        翻译标题
      </button>
    </div>
    
    <AIBlueking ref="aiBlueking" :url="apiUrl" />
  </div>
</template>

<script>
import AIBlueking from '@blueking/ai-blueking/vue2';
import '@blueking/ai-blueking/dist/vue2/style.css';

export default {
  components: {
    AIBlueking
  },
  data() {
    return {
      apiUrl: 'https://your-api-endpoint.com/assistant/',
      articleTitle: 'AI 技术的发展与应用',
      articleContent: '人工智能技术在近年来取得了突飞猛进的发展...'
    };
  },
  methods: {
    quickActions(label, promptPrefix, cite) {
      
      this.$refs.aiBlueking.handleShow(); // 显示AI小鲸
      
      this.$refs.aiBlueking.sendChat({ // 主动调用发送消息
        message: label,
        cite,
        shortcut: {
          label,
          key: label.toLowerCase(),
          prompt: `${promptPrefix} {{ SELECTED_TEXT }}`
        }
      });
    }
  }
};
</script>
```

### Vue 3 自定义提示词

```vue
<template>
  <AIBlueking
    ref="aiBlueking"
    :url="apiUrl"
    :prompts="customPrompts"
  />
</template>

<script lang="ts" setup>
import { ref } from 'vue';
import AIBlueking from '@blueking/ai-blueking';
import '@blueking/ai-blueking/dist/vue3/style.css';

const aiBlueking = ref(null);
const apiUrl = 'https://your-api-endpoint.com/assistant/';

const customPrompts = [
  '我给一段文字，概括文字的主题和主要观点，找出支持主题的关键事实、论据或观点，使用中文回答。',
  '假设你是一名关系型数据库专家，后续的对话我会直接描述我想要的查询效果，请告诉我如何写对应的SQL查询，并解释它，如果有多个版本的SQL，以MySQL数据库为主。',
  '你是一名经验丰富的前端开发工程师，请帮我解决以下问题...'
];
</script>
```

### Vue 3 设置 Nimbus 初始最小化状态

```vue
<template>
  <AIBlueking
    ref="aiBlueking"
    :url="apiUrl"
    :default-minimize="true"
  />
</template>

<script lang="ts" setup>
import { ref } from 'vue';
import AIBlueking from '@blueking/ai-blueking';
import '@blueking/ai-blueking/dist/vue3/style.css';

const aiBlueking = ref(null);
const apiUrl = 'https://your-api-endpoint.com/assistant/';
</script>
```

### Vue 3 自定义传送目标元素

```vue
<template>
  <div>
    <div id="ai-container"></div>
    <AIBlueking
      ref="aiBlueking"
      :url="apiUrl"
      teleport-to="#ai-container"
    />
  </div>
</template>

<script lang="ts" setup>
import { ref } from 'vue';
import AIBlueking from '@blueking/ai-blueking';
import '@blueking/ai-blueking/dist/vue3/style.css';

const aiBlueking = ref(null);
const apiUrl = 'https://your-api-endpoint.com/assistant/';
</script>
```

### Vue 3 自定义请求选项

```vue
<template>
  <AIBlueking
    ref="aiBlueking"
    :url="apiUrl"
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

这将使得发送请求时，会携带 `preset` 参数，headers 的数据会合并到请求头中，请求体数据会合并到请求体中:
```diff
{
  inputs: {},
  chat_history: [],
  input: 'xxx',
+  preset: "QA"
}
```

### Vue 3 访问会话内容

```vue
<template>
  <AIBlueking ref="aiBlueking" :url="apiUrl" />
  <button @click="showSessionContents">显示会话内容</button>
</template>

<script lang="ts" setup>
import { ref } from 'vue';
import AIBlueking from '@blueking/ai-blueking';
import '@blueking/ai-blueking/dist/vue3/style.css';

const aiBlueking = ref<InstanceType<typeof AIBlueking>>();
const apiUrl = 'https://your-api-endpoint.com/assistant/';

const showSessionContents = () => {
const sessionContents = aiBlueking.value?.sessionContents;
  console.log('当前会话内容:', sessionContents);
}
</script>

### Vue 2 自定义请求选项

```vue
<template>
  <AIBlueking
    ref="aiBlueking"
    :url="apiUrl"
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

### Vue 2 访问会话内容

```vue
<template>
  <AIBlueking ref="aiBlueking" :url="apiUrl" />
  <button @click="showSessionContents">显示会话内容</button>
</template>

<script>
import AIBlueking from '@blueking/ai-blueking/vue2';
import '@blueking/ai-blueking/dist/vue2/style.css';

export default {
  components: {
    AIBlueking
  },
  data() {
    return {
      apiUrl: 'https://your-api-endpoint.com/assistant/'
    };
  },
  methods: {
    showSessionContents() {
      const sessionContents = this.$refs.aiBlueking.sessionContents;
      console.log('当前会话内容:', sessionContents);
    }
  }
};
</script>
```

### Vue 2 自定义提示词

```vue
<template>
  <AIBlueking
    ref="aiBlueking"
    :url="apiUrl"
    :prompts="customPrompts"
  />
</template>

<script>
import AIBlueking from '@blueking/ai-blueking/vue2';
import '@blueking/ai-blueking/dist/vue2/style.css';

export default {
  components: {
    AIBlueking
  },
  data() {
    return {
      apiUrl: 'https://your-api-endpoint.com/assistant/',
      customPrompts: [
        '我给一段文字，概括文字的主题和主要观点，找出支持主题的关键事实、论据或观点，使用中文回答。',
        '假设你是一名关系型数据库专家，后续的对话我会直接描述我想要的查询效果，请告诉我如何写对应的SQL查询，并解释它，如果有多个版本的SQL，以MySQL数据库为主。',
        '你是一名经验丰富的前端开发工程师，请帮我解决以下问题...'
      ]
    };
  }
};
</script>
```

### Vue 2 设置 Nimbus 初始最小化状态

```vue
<template>
  <AIBlueking
    ref="aiBlueking"
    :url="apiUrl"
    :default-minimize="true"
  />
</template>

<script>
import AIBlueking from '@blueking/ai-blueking/vue2';
import '@blueking/ai-blueking/dist/vue2/style.css';

export default {
  components: {
    AIBlueking
  },
  data() {
    return {
      apiUrl: 'https://your-api-endpoint.com/assistant/'
    };
  }
};
</script>
```

### Vue 2 自定义传送目标元素

```vue
<template>
  <div>
    <div id="ai-container"></div>
    <AIBlueking
      ref="aiBlueking"
      :url="apiUrl"
      teleport-to="#ai-container"
    />
  </div>
</template>

<script>
import AIBlueking from '@blueking/ai-blueking/vue2';
import '@blueking/ai-blueking/dist/vue2/style.css';

export default {
  components: {
    AIBlueking
  },
  data() {
    return {
      apiUrl: 'https://your-api-endpoint.com/assistant/'
    };
  }
};
</script>
```

## 框架差异注意事项

### Vue 2 与 Vue 3 的区别

1. **引入方式不同**：
   - Vue 3: `import AIBlueking from '@blueking/ai-blueking'`
   - Vue 2: `import AIBlueking from '@blueking/ai-blueking/vue2'`

2. **样式引入不同**：
   - Vue 3: `import '@blueking/ai-blueking/dist/vue3/style.css'`
   - Vue 2: `import '@blueking/ai-blueking/dist/vue2/style.css'`

3. **组件实例获取**：
   - Vue 3: 通过 ref 值获取，如 `aiBlueking.value?.handleShow()`
   - Vue 2: 通过 $refs 获取，如 `this.$refs.aiBlueking.handleShow()`

4. **组件定义方式**：
   - Vue 3: 使用 Composition API 或 Options API
   - Vue 2: 使用 Options API

## 通用注意事项

1. 必须设置有效的 `url` 属性，指向您的 AI 服务接口
2. 为了获得最佳体验，建议将 AI 小鲸放在全局组件中，以便在应用的任何地方都能访问
3. 快捷操作中的提示词模板使用 `{{ SELECTED_TEXT }}` 作为选中文本的占位符
4. Vue 2 中导入的是 `@blueking/ai-blueking/vue2`，而非根路径

## 示例项目

可以参考 `packages/ai-blueking/playground/dynamic-demo.vue` 了解更多使用示例。

## 常见问题

1. **Q: AI 小鲸窗口如何调整大小？**  
   A: 用户可以通过拖动窗口边缘或右下角来调整窗口大小。

2. **Q: 如何实现选中文本弹出快捷操作？**  
   A: 这是 AI 小鲸的内置功能，设置 `enablePopup` 为 true 即可启用。

3. **Q: 在 Vue 2 项目中使用时遇到兼容性问题怎么办？**  
   A: 确保正确导入 Vue 2 版本的组件和样式，路径分别为 `@blueking/ai-blueking/vue2` 和 `@blueking/ai-blueking/dist/vue2/style.css`。

## 贡献指南

如需为小鲸组件做贡献，请遵循以下步骤：

1. Fork 本仓库
2. 创建您的特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交您的更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启一个 Pull Request

## 许可证

[MIT 许可证](../../../LICENSE.txt) 