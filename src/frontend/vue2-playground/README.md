# AI 小鲸 Vue2 Playground

这是一个用于测试 AI 小鲸组件在 Vue2 环境下使用的示例工程。

## 功能特点

- 使用 Vue2 环境
- 集成 AI 小鲸组件
- 提供基本的交互演示
- 展示组件功能和事件

## 快速开始

确保您已安装 Node.js 和 PNPM。

```bash
# 安装依赖
pnpm install

# 启动开发服务器
pnpm run serve
```

## 使用方法

1. 点击"显示 AI 小鲸"按钮打开 AI 小鲸对话窗口
2. 使用"发送消息"按钮发送测试消息
3. 使用"停止生成"按钮可以停止 AI 回复生成
4. 尝试点击组件内部的快捷操作按钮测试功能

## 示例代码

```vue
<ai-blueking
  ref="aiBlueking"
  :url="aiUrl"
  :title="'AI 小鲸 Vue2 测试'"
  :shortcuts="shortcuts"
  @close="onClose"
  @show="onShow"
  @stop="onStop"
  @shortcut-click="onShortcutClick"
/>
```

要访问组件方法：

```js
this.$refs.aiBlueking.handleShow(); // 显示对话框
this.$refs.aiBlueking.handleStop(); // 停止生成
this.$refs.aiBlueking.handleSendMessage('测试消息'); // 发送消息
```

## 注意事项

- 需要在 `.env.development` 配置正确的 AI 接口地址才能正常工作
- Vue2 版本的组件通过 `@blueking/ai-blueking/vue2` 导入
- 请确保 AI 小鲸组件版本与文档一致 