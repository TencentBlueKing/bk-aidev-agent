# 更新日志

<Changelog :versions="changelogData" />

<script>
export default {
  data() {
    return {
      changelogData: [
        {
          version: "v1.2.8",
          date: "2025-10-17",
          features: [
            "新增会话创建参数配置，优化 handleShow 和 addNewSession 方法",
            "APM 调用分析图表跳转链接调整，新增标签过滤参数",
            "新增 feedback 功能，优化 feedback 前端交互体验",
            "智能体：AI 小鲸独立生成 pip 包并集成到插件",
            "新增 iconRender 支持以自定义图标渲染，优化多个组件以使用该功能",
            "优化 markdown-viewer 组件的 cite 文本处理，新增 removeThinkingSections 工具函数以清理思考片段",
            "新增更新位置和大小的功能，优化窗口大小变化时的组件位置调整逻辑"
          ],
          improvements: [
            "更新 @blueking/ai-ui-sdk 版本到 0.1.18-beta.21，确保 @blueking/ai-blueking 依赖一致性",
            "修复 x-mavon-editor 的全局变量声明并优化用户配置参数格式",
            "新增 ISessionContent 类型导入并优化 handleUpdateSessionContent 函数的参数格式",
            "简化 render-message 组件的内容渲染逻辑"
          ]
        },
        {
          version: "v1.2.7",
          date: "2025-10-14",
          features: [
            "新增 hideDefaultTrigger 属性，支持隐藏默认的AI小鲸触发按钮，适用于需要完全自定义触发方式的场景",
            "新增 dropdownMenuConfig 属性，支持自定义会话操作下拉菜单中的功能项显示，包含重命名、自动生成命名和分享会话选项的显示控制",
            "新增 placeholder 属性，支持自定义输入框占位符文本，提供更灵活的用户提示",
            "handleShow 方法新增 forceNewSession 参数，支持创建新会话时同时打开窗口，优化用户体验",
            "handleShow 方法签名更新为 handleShow(sessionCode?: string, forceNewSession?: boolean): Promise<void>",
            "新增 updatePosition、updateSize 和 updatePositionAndSize 方法，支持动态调整AI小鲸窗口的位置和尺寸",
            "新增 drag-stop、resize-stop、dragging 和 resizing 事件，支持监听拖拽和调整大小过程中的状态",
            "历史会话面板新增时间分组，支持3天前、5天前、1周前等更精细的时间分组",
            "为 Vue2 版本添加编程式控制容器位置和大小的功能，优化 Vue2 适配器确保与 Vue3 版本功能同步"
          ],
          improvements: [
            "优化新会话创建逻辑，确保在 forceNewSession=true 时先创建会话再打开面板",
            "优化会话时间分组算法，改进历史会话管理体验",
            "新增相关时间分组的国际化支持",
            "在 useResizableContainer 组合式函数中增加拖拽和调整大小结束的回调函数",
            "requestOptions.context 支持函数返回数组，增强动态上下文配置的灵活性"
          ]
        },
        {
          version: "v1.2.6",
          date: "2025-09-18",
          important: "⚠️ <strong>重要提醒</strong>：小鲸 1.2.6 版本必须与后端 SDK 版本 1.0.0b42 或更高版本匹配使用，否则可能出现兼容性问题",
          features: [
            "新增 setCiteText 方法，支持编程式设置输入框中的引用文本",
            "群聊咨询用户名支持，在选择模式中新增 username 字段，用于群聊转人工时显示咨询用户名称",
            "动态群聊名称生成，聊天群名称根据智能体名称、会话名称和用户名自动组合生成"
          ],
          improvements: [
            "升级 @blueking/ai-ui-sdk 到 0.1.16-beta.4，获取更多底层能力支持和功能增强",
            "优化输入框样式，添加 box-sizing 属性提升样式一致性",
            "重构选择模式逻辑，移除不必要的依赖，提升代码可维护性"
          ]
        },
        {
          version: "v1.2.5",
          date: "2025-09-12",
          important: "⚠️ <strong>重要提醒</strong>：小鲸 1.2.5 版本必须与后端 SDK 版本 1.0.0b39 或更高版本匹配使用，否则可能出现兼容性问题",
          features: [
            "优化快捷操作逻辑，移除 ai-selected-box 组件，简化快捷方式点击事件的处理",
            "新增 loadRecentSessionOnMount 属性，支持组件挂载时加载最近会话，优化会话初始化体验",
            "新增 403 错误页面支持，完善权限控制和无权限访问的处理",
            "新增人工反馈功能，增强用户交互体验",
            "新增 saasUrl 请求功能，支持SaaS模式下的接口调用",
            "新增 hasSessionContents 属性，支持为无会话内容的菜单项提供 tooltip 提示",
            "新增选择模式功能，支持消息的选择和多选操作",
            "进一步完善图标字体库和视觉样式"
          ],
          improvements: [
            "重构 ESLint 配置，统一代码规范，提升代码质量",
            "新增 tsconfig.build.json 配置文件，优化 TypeScript 构建流程",
            "优化会话重命名功能，支持自动生成会话名称",
            "移除开发环境配置中的 BK_API_URL_TMPL 和 BKUI_PREFIX 变量，简化环境配置",
            "优化快捷操作过滤器逻辑，增强快捷操作的灵活性和可定制性"
          ]
        },
        {
          version: "v1.2.4",
          date: "2025-09-03",
          features: [
            "新增 beforeRequest 钩子支持，可在发送请求前对请求参数进行处理",
            "划选过滤增强，改进划选文本检测逻辑，优化在 shadow DOM 中的文本选择支持",
            "监控体验优化，优化组件的监控和错误处理机制",
            "新增 `hide` 属性，支持动态控制快捷操作表单组件的显示/隐藏",
            "当组件的 `hide` 属性设置为 `true` 时，该组件将不会在表单中显示，同时其数据也不会包含在提交的表单数据中",
            "支持根据条件动态显示/隐藏表单字段，实现更灵活的表单交互",
            "新增 `shortcutFilter` 属性，支持根据选中文本内容动态过滤快捷操作，通过 `shortcutFilter` 函数可以访问当前选中的文本，实现更智能的快捷操作显示逻辑"
          ],
          improvements: [
            "结构化引用数据支持，优化引用组件并新增结构化引用数据显示组件",
            "表单提交逻辑优化，新增处理和过滤表单数据的辅助函数"
          ],
          fixes: [
            "修复划选文本检测的时序问题，提升划选操作的响应速度和准确性",
            "修复在某些场景下快捷操作事件重复触发的问题"
          ]
        },
        {
          version: "v1.2.3",
          date: "2025-08-12",
          features: [
            "新增会话自动命名功能，首次提问后自动为会话生成标题",
            "增强快捷指令功能，支持自定义表单交互和弹窗触发后自动提交",
            "新增 `extCls` 属性，允许用户自定义组件的根元素类名，便于样式覆盖和扩展"
          ],
          improvements: [
            "优化会话管理逻辑，并新增 enableChatSession 配置项以支持禁用多会话功能",
            "优化开场白和问候语的显示逻辑",
            "更新蓝鲸插件版本依赖，提升稳定性"
          ],
          fixes: [
            "修复 Markdown 复制代码按钮的显示问题",
            "修复搜索功能失效的问题",
            "修复开场白过长导致的UI截断问题"
          ]
        },
        {
          version: "v1.2.2",
          date: "2025-08-06",
          features: [
            "新增编程式会话管理API，允许通过方法调用创建、重命名、切换和获取会话列表",
            "新增 `addNewSession`、`updateSessionName`、`switchToSession` 和 `getSessionList` 方法，增强组件可编程性",
            "新增 `initialSessionCode` 和 `autoSwitchToInitialSession` 属性，支持组件初始化时进入指定会话"
          ],
          fixes: [
            "重构并优化文档结构，将编程交互相关文档整合为“基础控制”、“会话生命周期”和“高级工作流”三个层次，提升可读性和可维护性",
            "修复会话列表在名称更新后UI不刷新的响应性问题",
            "修复切换会话时偶发的 `switchSession` 方法不存在的错误"
          ]
        },
        {
          version: "v1.2.1",
          date: "2025-07-31",
          features: [
            "修复开场白过长导致的 UI 问题",
            "优化 shortcut 快捷键功能",
            "文档错误修复"
          ],
        },
        {
          version: "v1.2.0",
          date: "2025-07-30",
          features: [
            "新增自定义表单输入功能，支持快捷指令配置自定义表单交互",
            "支持文本输入框、下拉选择框、数字输入框和多行文本域等多种表单组件",
            "优化快捷操作接口，从 <code>ShortCut</code> 升级为 <code>IShortcut</code>",
            "新增 <code>components</code> 组件配置，实现复杂的交互表单",
            "支持配置表单项自动填充选中文本",
            "引入基于上下文的快捷操作处理机制，表单数据将作为上下文直接发送到后端"
          ],
          breaking: [
            "快捷操作接口由 <code>ShortCut</code> 更改为 <code>IShortcut</code>，参见<a href='/api/types'>接口文档</a>",
            "快捷操作不再使用前端拼接 prompt 的方式处理，改为将表单数据发送到后端，<strong>需要后端进行适配</strong>"
          ]
        },
        {
          version: "v1.1.6",
          date: "2025-07-15",
          features: [
            "Markdown 渲染增强：新增完整的 Markdown 样式支持，优化代码块、表格、列表等元素的渲染效果",
            "窗口高度响应式处理：添加智能高度计算，优化问候文本的最大高度限制",
            "会话初始化优化：改进初始化逻辑，避免重复初始化并支持状态重置",
            "多实例支持：重构 sessionStore 为实例化模式，避免多个组件实例间的状态冲突",
            "新增会话初始化完成事件：支持监听 <code>session-init</code> 事件，获取会话初始化状态"
          ],
          fixes: [
            "优化代理信息显示逻辑，修复标题中可能出现的 'undefined' 问题",
            "提升 TypeScript 类型定义，增强开发体验",
            "改进会话管理逻辑，修复新增会话按钮复用空会话的问题",
            "更新 SDK 依赖至最新版本，提升兼容性和稳定性"
          ]
        },
        {
          version: "v1.1.5",
          date: "2025-07-09",
          features: [
            "URL 协议自动适配：新增智能 URL 标准化功能，自动匹配当前页面协议（HTTP/HTTPS）",
            "上下文支持：新增 `context` 配置项，支持静态对象或动态函数形式传递上下文信息",
            "协议安全优化：HTTPS 页面下自动将 HTTP API 转换为 HTTPS，提升安全性"
          ],
          improvements: [
            "优化 URL 处理逻辑，支持相对路径、绝对路径、协议相对路径的智能识别",
            "改进 TypeScript 类型定义，提升开发体验",
            "代码格式化和性能优化"
          ]
        },
        {
          version: "v1.1.2",
          date: "2025-07-08",
          features: [
            "新增 `miniPadding` 属性：支持自定义压缩状态下的边距，提供更灵活的布局控制"
          ],
          improvements: [
            "优化高度切换逻辑：恢复默认高度时使用用户设置的初始位置和尺寸，而非固定的窗口高度",
            "改进容器状态管理：更好地保持用户自定义的初始配置"
          ]
        },
        {
          version: "v1.1.1",
          date: "2025-07-08",
          features: [
            "新增 `placeholder` 属性：支持自定义输入框占位符文本，提供更灵活的用户提示",
            "输入框自动聚焦：面板打开时自动聚焦到输入框，提升用户体验",
            "新增 `focusInput` 方法：支持外部程序式聚焦输入框"
          ],
          improvements: [
            "优化 Prompt 列表显示逻辑：只有在有数据且输入包含 '/' 时才显示，避免空列表干扰",
            "改进输入框交互体验，减少不必要的界面元素显示"
          ]
        },
        {
          version: "v1.1.0",
          date: "2025-07-07",
          features: [
            "多会话管理功能：全新的会话管理体验，支持创建、切换、编辑和删除多个聊天会话",
            "动态标题显示：头部标题现在显示当前会话名称，提供更好的上下文感知",
            "图标显示控制：新增 `showHistoryIcon` 和 `showNewChatIcon` 属性，支持控制历史和新聊天图标的显示",
            "会话状态管理：优化会话初始化和切换逻辑，提供更流畅的多会话体验",
          ],
          improvements: [
            "优化会话内容加载逻辑，提供加载状态指示",
            "改进会话删除逻辑，确保删除当前会话时能够正确切换",
            "优化历史面板的交互体验和视觉设计",
            "提升会话切换的性能和稳定性"
          ],
          breaking: [
            "会话管理架构重构，内部API有所调整（对外部使用者无影响），后端 SDK 需要更新至 AIDEV 最新版"
          ]
        },
        {
          version: "v1.0.3",
          date: "2025-07-03",
          features: [
            "支持动态更新 `requestOptions` 属性，允许在运行时修改请求参数",
          ],
        },
        {
          version: "v1.0.2",
          date: "2025-06-25",
          features: [
            "新增 `nimbusSize` 属性，支持 `small`, `normal`, `large` 三种尺寸，用于调整 Nimbus 悬浮图标的大小",
            "优化 Nimbus 最小化按钮尺寸，根据 `nimbusSize` 动态调整，提升视觉协调性",
          ],
          version: "v1.1.0-beta.2",
          date: "2025-06-02",
          fixes: [
            "修复自定义输入 `textarea` 背景色异常的问题"
          ]
        },
        {
          version: "v1.0.1",
          date: "2025-05-28",
          features: [
            "新增 `disabledInput` 属性，用于控制输入框是否禁用",
            "优化输入框禁用状态的样式，提供更好的视觉反馈"
          ],
          fixes: [
            "修复了某些场景下输入组件状态管理问题"
          ]
        },
        {
          version: "v1.0.0",
          date: "2025-05-27",
          features: [
            "全新架构设计，提供更高效的组件性能",
            "增强的界面适配能力，更好地支持各种屏幕尺寸",
            "优化交互体验，提供更流畅的拖拽和调整大小功能",
            "优化可调整容器高度的逻辑，提高窗口尺寸调整的稳定性"
          ],
          breaking: [
            "不再暴露 <code>sendChat</code> 方法，请使用新的 <code>sendMessage</code> 方法",
            "预设对话内容不再支持使用 <code>defaultMessages</code> ，需要在 BKAIDev 平台配置智能体时设置，小鲸组件将从接口统一获取",
            "修改了部分事件名称和参数结构，请参考最新文档"
          ],
          fixes: [
            "修复容器高度在屏幕尺寸变化时的计算问题"
          ]
        },
        {
          version: "v0.5.6",
          date: "2025-05-20",
          fixes: [
            "修复在加载状态下仍可发送消息的问题"
          ]
        },
        {
          version: "v0.5.5",
          date: "2025-05-15",
          features: [
            "优化位置交互计算方式，提高组件定位精度"
          ],
          fixes: [
            "修复初始位置调整导致位置交互错位的问题",
            "修复Vue2部分属性不生效的问题",
            "修复组件默认宽度计算错误的问题"
          ]
        },
        {
          version: "v0.5.4",
          date: "2025-04-28",
          features: [
            "新增 `draggable` 属性，控制组件是否可拖拽",
            "新增 `defaultWidth` 属性，设置组件初始宽度",
            "新增 `defaultHeight` 属性，设置组件初始高度",
            "新增 `defaultTop` 属性，设置组件初始顶部位置",
            "新增 `defaultLeft` 属性，设置组件初始左侧位置",
          ]
        },
        {
          version: "v0.5.3",
          date: "2025-04-20",
          features: [
            "支持 `defaultMessages` 属性，可预设对话内容",
            "新增 `receive-start`、`receive-text`、`receive-end` 和 `send-message` 事件，提供完整消息传递生命周期",
            "增强 Vue2 组件的API暴露支持，同步暴露Vue3组件中的所有方法和属性",
            "完善 Vue2 与 Vue3 组件的兼容性",
            "图标系统升级，将所有图标类名从 <code>icon-*</code> 更新为 <code>bkai-*</code> 前缀",
            "新增 `title` 属性，支持自定义标题",
            "新增 `helloText` 属性，支持自定义欢迎语",
            "新增 `close` 事件，响应组件关闭",
            "支持 mermaid 图表渲染",
            "新增 <code>teleportTo</code> 属性，支持自定义传送目标元素",
            "新增 <code>defaultMinimize</code> 属性，控制 Nimbus 组件初始最小化状态",
            "支持 <code>requestOptions</code> 传递自定义选项到发送请求",
            "新增 <code>sessionContents</code> 属性，暴露当前会话内容"
          ],
          fixes: [
            "修复框选内容在输入时没有立即消失的问题",
            "修复输入框组件可能引起的 xml 攻击风险",
            "修复 <code>minimize</code> 下点击无法显示面板的问题"
          ]
        },
        {
          version: "v0.5.3-beta.6",
          date: "2025-04-16",
          features: [
            "增强 Vue2 组件的API暴露支持，同步暴露Vue3组件中的所有方法和属性",
            "完善 Vue2 与 Vue3 组件的兼容性"
          ]
        },
        {
          version: "v0.5.3-beta.5",
          date: "2025-04-15",
          features: [
            "图标系统升级，将所有图标类名从 <code>icon-*</code> 更新为 <code>bkai-*</code> 前缀",
            "优化停止生成和滚动到底部功能的图标展示"
          ]
        },
        {
          version: "v0.5.3-beta.4",
          date: "2025-04-10",
          features: [
            "新增 `title` 属性，支持自定义标题",
            "新增 `helloText` 属性，支持自定义欢迎语",
          ]
        },
        {
          version: "v0.5.3-beta.3",
          date: "2025-04-03",
          features: [
            "新增 `close` 事件，响应组件关闭"
          ]
        },
        {
          version: "v0.5.3-beta.2",
          date: "2025-04-02",
          features: [
            "支持 mermaid 图表渲染"
          ]
        },
        {
          version: "v0.5.3-beta.1",
          date: "2025-04-02",
          features: [
            "新增 <code>teleportTo</code> 属性，支持自定义传送目标元素",
            "可以将组件内容渲染到任意 DOM 位置，避免嵌套组件的样式和定位问题"
          ],
          fixes: [
            "修复框选内容在输入时没有立即消失的问题",
            "修复输入框组件可能引起的 xml 攻击风险",
            "修复 <code>minimize</code> 下点击无法显示面板的问题"
          ]
        },
        {
          version: "v0.5.2",
          date: "2025-04-01",
          features: [
            "新增 <code>defaultMinimize</code> 属性，控制 Nimbus 组件初始最小化状态",
            "支持 <code>requestOptions</code> 传递自定义选项到发送请求",
            "新增 <code>sessionContents</code> 属性，暴露当前会话内容"
          ]
        },
        {
          version: "v0.5.0",
          date: "2025-03-28",
          features: [
            "全新 UI 设计，界面彻底重构",
            "支持窗口拖拽和调整大小",
            "优化响应式设计，适应不同屏幕尺寸",
            "基础字体从 12px 调整至 14px，提升可读性",
            "新增 Nimbus 支持，内置弹出式交互",
            "新增预设提示词列表功能",
            "新增消息删除确认功能",
            "文本区域高度自适应",
            "优化消息渲染逻辑，支持更丰富的内容展示"
          ],
          breaking: [
            "组件 API 结构调整，请参考最新文档进行升级"
          ]
        },
        {
          version: "v0.4.3",
          date: "2025-03-03",
          fixes: [
            "修复参考文档 <code>preview_path</code> 字段",
            "Vue2 组件导出 <code>isThinking</code> 工具函数"
          ]
        },
        {
          version: "v0.4.2",
          date: "2025-02-28",
          fixes: [
            "修复 Vue2 组件对 <code>shortcut-click</code> 事件的响应问题"
          ]
        },
        {
          version: "v0.4.1",
          date: "2025-02-27",
          features: [
            "支持自定义快捷操作 shortcuts 配置"
          ],
          fixes: [
            "修复 popup 快捷键点击内容为空的问题",
            "修复翻译问题",
            "修复多余的控制台日志"
          ]
        },
        {
          version: "v0.4.0",
          date: "2025-02-21",
          features: [
            "支持实时展示 AI 的思考状态",
            "新增 <code>shortcut-click</code> 事件，响应快捷操作按钮点击"
          ],
          breaking: [
            "ChatHelper 构造函数新增 <code>messages</code> 参数",
            "回调函数 <code>handleClear</code> 必须使用 <code>messages.value.splice(0)</code> 方式清空消息",
            "<code>handleReceiveMessage</code> 新增 <code>cover</code> 参数",
            "<code>handleEnd</code> 增强错误处理，支持检测思考状态"
          ]
        },
        {
          version: "v0.3.29",
          date: "2025-02-26",
          fixes: [
            "修复快捷操作按钮点击无效的问题",
            "修复 AI 在回复过程中，点击清空按钮导致状态混乱问题"
          ]
        },
        {
          version: "v0.3.28",
          date: "2025-02-25",
          features: [
            "调整 AI 弹框默认高度为 100% 浏览器高度"
          ]
        },
        {
          version: "v0.3.27",
          date: "2025-02-24",
          fixes: [
            "修复 popup 弹窗位置计算错误",
            "修复弹窗在 clickoutside 时不会关闭的问题",
            "修复 model 窗口在屏幕大小发生变化时位置计算错误的问题"
          ]
        },
        {
          version: "v0.3.26",
          date: "2025-02-20",
          features: [
            "Alert 提示配置增强，支持传入完整的 Alert 组件配置项"
          ]
        },
        {
          version: "v0.3.25",
          date: "2025-02-19",
          features: [
            "优化快捷操作按钮样式，支持快捷按钮组直接快速交互和唤起"
          ]
        },
        {
          version: "v0.3.24",
          date: "2025-02-14",
          features: [
            "新增快捷操作功能，支持解释和翻译两种快捷操作",
            "通过 <code>AIBlueking</code> 组件的 <code>quickActions</code> 方法调用"
          ]
        }
      ]
    }
  }
}
</script>
