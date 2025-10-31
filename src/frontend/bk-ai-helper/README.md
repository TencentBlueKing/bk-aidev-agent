# BK AI Helper

<p align="center">
  <img src="https://img.shields.io/npm/v/@blueking/bk-ai-helper.svg" alt="npm version" />
  <img src="https://img.shields.io/npm/dm/@blueking/bk-ai-helper.svg" alt="downloads" />
  <img src="https://img.shields.io/npm/l/@blueking/bk-ai-helper.svg" alt="license" />
</p>

蓝鲸 AI 助手组件，为表单输入提供智能填充功能。支持 Vue2 和 Vue3。

## ✨ 特性

- 🤖 **AI 智能填充**：利用 AI 自动生成表单内容
- 📝 **自定义提示词**：支持为不同场景配置专属 Prompt
- ⌨️ **快捷键支持**：Enter 发送，Shift + Enter 换行
- 🌍 **国际化**：内置中英文支持
- 🎨 **优雅交互**：Loading 状态、禁用状态、遮罩提示
- 📦 **双版本支持**：同时支持 Vue2 和 Vue3

## 📦 安装

```bash
npm install @blueking/bk-ai-helper
```

或使用 pnpm：

```bash
pnpm add @blueking/bk-ai-helper
```

## 🚀 快速开始

### Vue3 使用

```vue
<template>
  <div class="form-demo">
    <label>
      规则名称
      <BkAiHelper
        base-url="https://your-api-domain.com"
        prompt="帮我生成一个简短的规则名称"
        @response="handleResponse"
      />
    </label>
    <input
      v-model="ruleName"
      placeholder="请输入规则名称"
    />
  </div>
</template>

<script setup lang="ts">
  import { ref } from 'vue';
  import BkAiHelper from '@blueking/bk-ai-helper';
  import '@blueking/bk-ai-helper/dist/vue3/style.css';

  const ruleName = ref('');

  const handleResponse = (content: string) => {
    ruleName.value = content; // AI 响应自动填充到输入框
  };
</script>
```

### Vue2 使用

> Vue2 下，需要先安装 Vue3 资源依赖包：

```bash
npm install @blueking/bkui-library
```

```vue
<template>
  <div class="form-demo">
    <label>
      规则名称
      <bk-ai-helper
        base-url="https://your-api-domain.com"
        prompt="帮我生成一个简短的规则名称"
        @response="handleResponse"
      />
    </label>
    <input
      v-model="ruleName"
      placeholder="请输入规则名称"
    />
  </div>
</template>

<script>
  import BkAiHelper from '@blueking/bk-ai-helper/vue2';
  import '@blueking/bk-ai-helper/dist/vue2/style.css';

  export default {
    components: {
      BkAiHelper,
    },
    data() {
      return {
        ruleName: '',
      };
    },
    methods: {
      handleResponse(content) {
        this.ruleName = content;
      },
    },
  };
</script>
```

## 📖 API

### Props

| 属性名         | 类型     | 默认值                                               | 说明                                       |
| -------------- | -------- | ---------------------------------------------------- | ------------------------------------------ |
| `base-url`     | `String` | -                                                    | **必填**，AI API 基础地址                  |
| `title`        | `String` | `'帮我写'`                                           | 触发按钮文字                               |
| `form-title`   | `String` | `'规则描述'`                                         | 弹窗标题                                   |
| `placeholder`  | `String` | `'请输入规则描述（Enter 发送，Shift + Enter 换行）'` | 输入框占位符                               |
| `prompt`       | `String` | `''`                                                 | 预设的 AI 提示词，用于引导 AI 生成特定内容 |
| `form-options` | `Object` | `{}`                                                 | 传递给 BkInput 组件的额外配置              |

### Events

| 事件名      | 参数                                 | 说明                         |
| ----------- | ------------------------------------ | ---------------------------- |
| `@success`  | `(response: ChatCompletionResponse)` | 请求成功时触发，返回完整响应 |
| `@response` | `(content: string)`                  | 返回 AI 生成的文本内容       |
| `@error`    | `(error: Error)`                     | 请求失败时触发               |

## 💡 使用场景

### 场景一：填充单行输入框

```vue
<template>
  <div>
    <label>
      任务名称
      <BkAiHelper
        base-url="https://api.example.com"
        prompt="生成一个简洁的任务名称"
        @response="taskName = $event"
      />
    </label>
    <input v-model="taskName" />
  </div>
</template>
```

### 场景二：填充多行文本框

```vue
<template>
  <div>
    <label>
      规则描述
      <BkAiHelper
        base-url="https://api.example.com"
        form-title="AI 生成规则描述"
        placeholder="描述你想要生成什么样的规则描述"
        prompt="帮我生成一个详细的业务规则描述，不要多余的思考、解释，直接生成规则描述"
        title="AI 助手"
        @response="description = $event"
      />
    </label>
    <textarea
      v-model="description"
      rows="6"
    />
  </div>
</template>
```

### 场景三：完整事件监听

```vue
<template>
  <BkAiHelper
    base-url="https://api.example.com"
    @error="handleError"
    @response="handleResponse"
    @success="handleSuccess"
  />
</template>

<script setup lang="ts">
  const handleSuccess = response => {
    console.log('请求成功，完整响应:', response);
  };

  const handleError = error => {
    console.error('请求失败:', error.message);
    // 可以在这里做错误提示
  };

  const handleResponse = content => {
    console.log('AI 生成的内容:', content);
    // 自动填充到表单
  };
</script>
```

## ⌨️ 键盘快捷键

- **Enter**：发送消息
- **Shift + Enter**：换行

## 🌍 国际化

组件内置中英文支持，通过读取 Cookie `blueking_language` 自动切换语言：

- `zh-cn`：中文（默认）
- `en`：英文

你也可以手动导入语言包：

```typescript
import { t, lang, langData } from '@blueking/bk-ai-helper';

console.log(lang); // 当前语言
console.log(t('帮我写')); // 翻译函数
```

## 🎨 样式自定义

组件使用 BkUI Vue 样式体系，你可以通过以下方式自定义样式：

```css
/* 自定义触发按钮样式 */
.bk-ai-helper-title {
  color: #your-color;
}

/* 自定义弹窗样式 */
.bk-ai-helper-popover {
  width: 600px;
}
```

## 🔧 开发

```bash
# 安装依赖
pnpm install

# 开发模式
pnpm dev

# 构建外部版（开源版本，baseUrl 为空字符串）
pnpm run build:external

# 构建内部版（需要在 .env 文件中设置 AI_HELPER_BASE_URL）
pnpm run build:internal

# 生成类型定义
pnpm dts

# 清理构建产物
pnpm clean
```

### 构建说明

项目支持两种构建模式：

- **外部版** (`build:external`)：适用于开源版本，baseUrl 默认为空字符串，用户需要自行配置
- **内部版** (`build:internal`)：适用于内部版本，必须在 `.env` 文件中设置 `AI_HELPER_BASE_URL`

详细构建指南请参考 [BUILD_GUIDE.md](./BUILD_GUIDE.md)。

## 📝 API 接口格式

组件默认调用以下接口：

**请求地址：** `{baseUrl}/bk_plugin/plugin_api/chat_completion/`

**请求方法：** `POST`

**请求参数：**

```json
{
  "chat_prompts": [
    {
      "role": "user",
      "content": "用户输入的内容"
    }
  ],
  "execute_kwargs": {
    "stream": false
  }
}
```

**响应格式：**

```json
{
  "data": {
    "choices": [
      {
        "delta": {
          "content": "AI 生成的内容"
        }
      }
    ]
  }
}
```

如需自定义接口，可以 fork 本项目修改 `src/utils/api.ts` 文件。

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📄 License

MIT License

Copyright (c) 2025 Tencent BlueKing

---

Made with ❤️ by Tencent BlueKing Team
