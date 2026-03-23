# 文档插图待办清单

本文件列出所有需要补充截图/架构图的位置，按优先级排序。完成后在对应条目打勾。

> **图片存放建议**：`docs/public/images/` 目录下，按模块分子目录（如 `guide/`、`demos/`）。
> **引用格式**：`![描述](/images/guide/xxx.png)`
> **Excalidraw 图**已生成在 `docs/excalidraw/` 目录下，可用 [excalidraw.com](https://excalidraw.com) 打开编辑后导出 PNG/SVG。

---

## 架构 & 概览（高优先级）

- [x] **1. 三层架构关系图** ✅ `excalidraw/architecture-layers.excalidraw`
  - 文件：[guide/introductions.md](/guide/introductions)
  - 位置：`三层模块化架构` 说明处（约第 5-9 行）
  - 内容：chat-x（UI 层）/ chat-helper（SDK 层）/ ai-blueking（业务层）三层关系图
  - 👉 打开 excalidraw.com → 导入文件 → 导出 PNG → 放入 `docs/public/images/guide/`

- [ ] **2. 三种集成模式对比**
  - 文件：[guide/introductions.md](/guide/introductions)
  - 位置：`三种集成模式` 表格上方（约第 42 行）
  - 内容：ChatBot 独立模式 vs AIBlueking 完整面板 vs 原子组装，三种形态并排对比
  - 建议形式：产品截图拼图（3 张并排）

- [x] **3. 数据流全景图** ✅ `excalidraw/data-flow.excalidraw`
  - 文件：[guide/architecture](/guide/architecture)
  - 位置：`数据流` 章节（约第 39 行）
  - 内容：用户输入 → Manager → chat-helper → SSE → AGUIProtocol → 响应式 ref → UI 渲染
  - 👉 打开 excalidraw.com → 导入文件 → 导出 PNG → 放入 `docs/public/images/guide/`

- [x] **4. 初始化状态机流程图** ✅ `excalidraw/bootstrap-state-machine.excalidraw`
  - 文件：[guide/internals/chat-bootstrap](/guide/internals/chat-bootstrap)
  - 位置：`BootstrapPhase 状态机` 章节（约第 41 行）
  - 内容：IDLE → LOADING_AGENT → LOADING_SESSION → READY，以及各阶段到 ERROR 的分支
  - 👉 打开 excalidraw.com → 导入文件 → 导出 PNG → 放入 `docs/public/images/guide/`

---

## Excalidraw 流程图 & 架构图（新增）

- [x] **12. 包选择决策树** ✅ `excalidraw/package-decision-tree.excalidraw`
  - 文件：[api/overview.md](/api/overview)
  - 位置：`我该用哪个包？` 章节（约第 17-32 行）
  - 内容：根据需求选择 AIBlueking / ChatBot / chat-x+chat-helper 的决策树
  - 👉 打开 excalidraw.com → 导入文件 → 导出 PNG → 放入 `docs/public/images/api/`

- [x] **13. 包依赖关系图** ✅ `excalidraw/package-dependencies.excalidraw`
  - 文件：[api/overview.md](/api/overview)
  - 位置：`包依赖关系` 章节（约第 87-91 行）
  - 内容：ai-blueking 依赖 chat-x（UI 渲染）和 chat-helper（数据通信），两者互不依赖
  - 👉 打开 excalidraw.com → 导入文件 → 导出 PNG → 放入 `docs/public/images/api/`

- [x] **14. 迁移三层架构说明** ✅ `excalidraw/migration-three-layers.excalidraw`
  - 文件：[guide/migration-2.0.md](/guide/migration-2.0)
  - 位置：`三层架构说明` 章节（约第 18-26 行）
  - 内容：ai-blueking（体验层）→ chat-x（交互层）→ chat-helper（数据层）三层堆叠图
  - 👉 打开 excalidraw.com → 导入文件 → 导出 PNG → 放入 `docs/public/images/guide/`

- [x] **15. 完整事件流** ✅ `excalidraw/event-flow.excalidraw`
  - 文件：[guide/internals/event-system.md](/guide/internals/event-system)
  - 位置：`完整事件流示例` 章节（约第 240-262 行）
  - 内容：用户点击发送 → InputArea → ChatBusinessManager → ComponentManager → useEventBridge → 父组件
  - 👉 打开 excalidraw.com → 导入文件 → 导出 PNG → 放入 `docs/public/images/guide/`

- [x] **16. 消息发送流程** ✅ `excalidraw/message-send-flow.excalidraw`
  - 文件：[guide/core-features/chat-interaction.md](/guide/core-features/chat-interaction)
  - 位置：`消息发送流程` 章节（约第 9-17 行）
  - 内容：用户输入 → ChatBot → ChatBusinessManager → agentModule.chat → AGUIProtocol → UI 刷新
  - 👉 打开 excalidraw.com → 导入文件 → 导出 PNG → 放入 `docs/public/images/guide/`

- [x] **17. 分享流程** ✅ `excalidraw/share-flow.excalidraw`
  - 文件：[guide/core-features/sharing.md](/guide/core-features/sharing)
  - 位置：`分享流程` 章节（约第 11-22 行）
  - 内容：点击分享 → 进入选择模式 → 勾选消息 → 确认 → ShareBusinessManager → 复制链接
  - 👉 打开 excalidraw.com → 导入文件 → 导出 PNG → 放入 `docs/public/images/guide/`

- [x] **18. 分享内部协调流程** ✅ `excalidraw/share-coordination.excalidraw`
  - 文件：[guide/core-features/sharing.md](/guide/core-features/sharing)
  - 位置：`内部协调流程` 章节（约第 129-141 行）
  - 内容：Header/MessageTools → ComponentManager → UIStateManager → ChatBot → ShareBusinessManager → useEventBridge
  - 👉 打开 excalidraw.com → 导入文件 → 导出 PNG → 放入 `docs/public/images/guide/`

- [x] **19. 会话自动加载行为** ✅ `excalidraw/session-autoload.excalidraw`
  - 文件：[guide/core-features/session-management.md](/guide/core-features/session-management)
  - 位置：`autoLoad` 章节（约第 32-42 行）
  - 内容：ChatBot onMounted → initialize → loadRecentSession → 智能选择会话（三种分支）
  - 👉 打开 excalidraw.com → 导入文件 → 导出 PNG → 放入 `docs/public/images/guide/`

- [x] **20. 会话初始化时序** ✅ `excalidraw/session-init-sequence.excalidraw`
  - 文件：[guide/core-features/session-management.md](/guide/core-features/session-management)
  - 位置：`自动加载行为` 章节（约第 124-135 行）
  - 内容：创建 ChatHelper → 并行请求 getAgentInfo+getSessions → loadRecentSession → 选择/创建会话 → session-initialized
  - 👉 打开 excalidraw.com → 导入文件 → 导出 PNG → 放入 `docs/public/images/guide/`

- [x] **21. Manager 依赖关系图** ✅ `excalidraw/manager-dependencies.excalidraw`
  - 文件：[guide/internals/manager-pattern.md](/guide/internals/manager-pattern)
  - 位置：`依赖关系图` 章节（约第 62-70 行）
  - 内容：ComponentManager 为根，下辖 5 个 Manager 及各自依赖的模块
  - 👉 打开 excalidraw.com → 导入文件 → 导出 PNG → 放入 `docs/public/images/guide/`

- [x] **22. 消息属性数据流** ✅ `excalidraw/message-property-flow.excalidraw`
  - 文件：[guide/internals/message-property.md](/guide/internals/message-property)
  - 位置：`数据流` 章节（约第 129-147 行）
  - 内容：UI 构建 property → ChatBusinessManager → agentModule.chat → HTTP POST → 后端处理
  - 👉 打开 excalidraw.com → 导入文件 → 导出 PNG → 放入 `docs/public/images/guide/`

- [x] **23. 引用数据流总结** ✅ `excalidraw/content-reference-flow.excalidraw`
  - 文件：[guide/core-features/content-referencing.md](/guide/core-features/content-referencing)
  - 位置：`引用数据流总结` 章节（约第 193-225 行）
  - 内容：UI 层（setCiteText/handleSendMessage/handleShortcutSubmit）→ ChatBusinessManager → 后端 API 接收
  - 👉 打开 excalidraw.com → 导入文件 → 导出 PNG → 放入 `docs/public/images/guide/`

- [x] **24. AiSelection 划词工作流** ✅ `excalidraw/ai-selection-workflow.excalidraw`
  - 文件：[guide/core-features/content-referencing.md](/guide/core-features/content-referencing)
  - 位置：`工作流程` 章节（约第 164-173 行）
  - 内容：用户选中文本 → Popup 检测 → 弹出图标 → 展开操作列表 → 选择指令 → 构建 property → 发送
  - 👉 打开 excalidraw.com → 导入文件 → 导出 PNG → 放入 `docs/public/images/guide/`

- [x] **25. AIBlueking 内部结构** ✅ `excalidraw/aiblueking-structure.excalidraw`
  - 文件：[guide/integration-modes/aiblueking-floating.md](/guide/integration-modes/aiblueking-floating)
  - 位置：`内部结构` 章节（约第 119-126 行）
  - 内容：AIBlueking 包含 Nimbus、DraggableContainer（AIHeader + ChatBot）、AiSelection 的层级结构
  - 👉 打开 excalidraw.com → 导入文件 → 导出 PNG → 放入 `docs/public/images/guide/`

---

## 核心功能截图（中优先级）

- [ ] **5. 快捷操作 — 按钮 + 表单弹出效果**
  - 文件：[guide/core-features/shortcuts](/guide/core-features/shortcuts)
  - 位置：`IShortcutComponent 表单组件` 章节上方（约第 38 行）
  - 内容：输入框上方的快捷按钮条 + 点击后弹出的表单面板
  - 建议形式：产品截图（2 张：按钮条 + 表单展开）

- [ ] **6. 会话管理下拉**
  - 文件：[guide/core-features/session-management](/guide/core-features/session-management)
  - 位置：`会话列表` 章节（约第 97 行）
  - 内容：AIBlueking Header 中的会话管理下拉菜单（新建、历史列表、切换）
  - 建议形式：产品截图

- [ ] **7. 划词选择弹窗**
  - 文件：[guide/core-features/content-referencing](/guide/core-features/content-referencing)
  - 位置：`AiSelection 划词弹窗` 章节（约第 96 行）
  - 内容：页面上选中文字后弹出的快捷操作浮窗
  - 建议形式：产品截图

- [ ] **8. 分享多选模式**
  - 文件：[guide/core-features/sharing](/guide/core-features/sharing)
  - 位置：`分享流程` 说明后（约第 9-22 行）
  - 内容：消息列表进入多选模式，勾选消息的 UI 效果
  - 建议形式：产品截图

- [ ] **9. 主题自定义对比**
  - 文件：[guide/core-features/ui-customization](/guide/core-features/ui-customization)
  - 位置：`CSS 变量` 章节（约第 32 行）
  - 内容：默认主题 vs 自定义主题（改过颜色/圆角等）的对比效果
  - 建议形式：对比截图（左右或上下）

---

## 集成模式 & Demo 截图（较低优先级）

- [ ] **10. Nimbus 悬浮球 + 面板展开**
  - 文件：[guide/integration-modes/aiblueking-floating](/guide/integration-modes/aiblueking-floating)
  - 位置：`Nimbus 浮球` 章节（约第 56 行）
  - 内容：页面右下角悬浮球 → 点击展开完整面板的过程
  - 建议形式：产品截图（折叠态 + 展开态，可用箭头连接）

- [ ] **11. 完整面板整体效果**
  - 文件：[demos/full-panel](/demos/full-panel)
  - 位置：页面顶部在线体验区上方
  - 内容：AIBlueking 完整面板的整体效果（Header + 消息区 + 输入区 + 快捷操作）
  - 建议形式：产品截图

---

## 操作步骤

### 已生成的 Excalidraw 图（1、3、4、12-25）

1. 打开 [excalidraw.com](https://excalidraw.com)
2. 菜单 → Open → 选择 `docs/excalidraw/` 下的 `.excalidraw` 文件
3. 按需微调后，Export → PNG（2x）
4. 存入 `docs/public/images/guide/` 对应目录
5. 在 md 文件对应位置插入 `![描述](/images/guide/xxx.png)`

### 需要产品截图的（2、5-11）

1. 本地启动文档站或产品环境
2. 截图对应功能区域
3. 存入 `docs/public/images/` 对应目录
4. 在 md 文件对应位置插入图片引用

完成一项后回到本文件打勾即可。
