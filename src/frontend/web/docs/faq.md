# 常见问题 (FAQ)

1.  **Q: AI 小鲸窗口如何调整大小和移动位置？**

    A: 用户可以通过鼠标拖动窗口的边缘或右下角来调整大小，拖动窗口顶部的标题栏可以移动位置。这是组件的内置交互，无需配置。

2.  **Q: 如何实现选中页面上的文本后，弹出快捷操作菜单？**

    A: 这是 AI 小鲸的核心功能之一。确保 `enablePopup` prop 设置为 `true`（这是默认值），并且您已经通过 `shortcuts` prop 配置了至少一个快捷操作。用户在页面上选中文字后，会出现一个小图标，点击即可展开菜单。

3.  **Q: 在 Vue 2 项目中使用时遇到兼容性问题或报错怎么办？**

    A: 请务必检查以下几点：
    *   确认您导入的是 Vue 2 版本的组件：`import AIBlueking from '@blueking/ai-blueking/vue2';`
    *   确认您导入的是 Vue 2 版本的样式：`import '@blueking/ai-blueking/dist/vue2/style.css';`
    *   确保您的 Vue 版本符合组件的要求（查阅组件的 `package.json` 或说明）。
    *   检查是否与其他全局库或 Polyfill 存在冲突。

4.  **Q: `url` 属性应该填什么？**

    A: `url` 属性需要指向您部署的后端 AI 服务的 HTTP(S) 接口地址。这个接口负责接收 AI 小鲸发送的请求（包含用户输入、历史记录等），调用大语言模型，并将结果返回给前端。具体地址由您的后端服务提供。

5.  **Q: 如何给发送到后端的请求添加认证信息（如 Token）？**

    A: 使用 `requestOptions` prop。您可以将 Token 添加到 `headers` 对象中，例如：
    ```javascript
    :request-options="{ headers: { 'Authorization': 'Bearer your_token' } }"
    ```
    详细说明参见 [自定义请求指南](/guide/advanced-usage/custom-requests)。

6.  **Q: 是否可以自定义快捷操作的图标？**

    A: 可以。在 `shortcuts` 配置中，为每个 shortcut 对象添加 `icon` 属性，值为您项目中图标库对应的 CSS 类名即可。例如 `icon: 'bk-icon icon-magic-hat'`。

7.  **Q: 如何获取当前的对话历史记录？**

    A: 可以通过访问组件实例的 `sessionContents` 属性来获取。这是一个只读的响应式数组，包含了当前对话的消息列表。详细说明参见 [访问会话内容指南](/guide/advanced-usage/session-access)。