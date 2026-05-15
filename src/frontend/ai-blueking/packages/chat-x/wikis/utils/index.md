# 工具函数

`@blueking/chat-x` 提供了一些工具函数，用于处理 Markdown、Cookie 等常见操作。

## 函数列表

| 函数名                   | 说明                   |
| ------------------------ | ---------------------- |
| `completeMarkdown`       | Markdown 语法补全      |
| `completeMarkdownSyntax` | 流式 Markdown 语法补全 |
| `getCookieByName`        | 获取 Cookie 值         |

## Markdown 语法补全

### completeMarkdownSyntax

用于流式输入时自动补全未闭合的 Markdown 语法：

````typescript
import { completeMarkdownSyntax } from '@blueking/chat-x';

// 补全未闭合的代码块
const incomplete = '```javascript\nconst a = 1;';
const completed = completeMarkdownSyntax(incomplete);
// => '```javascript\nconst a = 1;\n```'

// 补全未闭合的粗体
const incomplete2 = '这是 **粗体';
const completed2 = completeMarkdownSyntax(incomplete2);
// => '这是 **粗体**'
````

### 支持补全的语法

| 语法     | 示例            | 补全结果             |
| -------- | --------------- | -------------------- |
| 代码块   | ` ```js\ncode ` | ` ```js\ncode\n``` ` |
| 行内代码 | `` `code ``     | `` `code` ``         |
| 粗体     | `**bold`        | `**bold**`           |
| 斜体     | `*italic`       | `*italic*`           |
| 删除线   | `~~strike`      | `~~strike~~`         |
| 链接     | `[text](`       | `[text](#)`          |
| 图片     | `![alt](`       | `![alt](#)`          |

## Cookie 工具

### getCookieByName

获取指定名称的 Cookie 值：

```typescript
import { getCookieByName } from '@blueking/chat-x';

// 获取语言设置
const lang = getCookieByName('blueking_language');
console.log(lang); // 'zh-cn' 或 'en'

// 获取不存在的 Cookie 返回 null
const notExist = getCookieByName('not_exist');
console.log(notExist); // null
```

## 使用示例

### 流式渲染时补全 Markdown

````vue
<template>
  <MarkdownContent
    :content="completedContent"
    :status="MessageStatus.Streaming"
  />
</template>

<script setup lang="ts">
  import { computed, ref } from 'vue';
  import { MarkdownContent, MessageStatus, completeMarkdownSyntax } from '@blueking/chat-x';

  const rawContent = ref('');

  // 自动补全未闭合的语法
  const completedContent = computed(() => {
    return completeMarkdownSyntax(rawContent.value);
  });

  // 模拟流式输入
  const simulateStreaming = async () => {
    const text = '```javascript\nconst greeting = "Hello";\nconsole.log(greeting);\n```';
    for (const char of text) {
      await new Promise(r => setTimeout(r, 50));
      rawContent.value += char;
    }
  };
</script>
````

### 根据语言设置切换显示

```typescript
import { getCookieByName } from '@blueking/chat-x';

const lang = getCookieByName('blueking_language');
const isEnglish = lang === 'en';

const greeting = isEnglish ? 'Hello' : '你好';
```

## 注意事项

1. `completeMarkdownSyntax` 主要用于流式渲染场景
2. 语法补全不会修改原始内容，只返回补全后的副本
3. `getCookieByName` 在服务端渲染时需要注意 `document` 不可用
