# 更新日志

<Changelog :versions="changelogData" />

<script>
export default {
  data() {
    return {
      changelogData: [
        {
          version: "0.5.5-beta.2",
          date: "2025-05-09",
          fixed: [
            "修复 初始位置调整导致位置交互错位的问题"
            "修复 Vue2 部分属性不生效的问题"
          ]
        }
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