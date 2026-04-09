# 主题

`@blueking/chat-x` 支持通过 CSS 变量和样式覆盖来自定义主题。

## 文档

| 文档                   | 说明               |
| ---------------------- | ------------------ |
| [主题配置](./theme.md) | 详细的主题配置指南 |

## 快速开始

### 覆盖样式

```scss
// 自定义输入框样式
.chat-input-container .chat-input {
  background: #fafafa;
  border-radius: 12px;
}

// 自定义消息样式
.ai-user-message-content {
  background-color: #e3f2fd;
}
```

### 暗色主题

```scss
.dark-theme {
  .chat-input-container .chat-input {
    background: #2d2d2d;
  }

  .ai-markdown-content .ai-markdown-body {
    color: #e0e0e0;
  }
}
```

更多详细信息请查看 [主题配置](./theme.md)。
