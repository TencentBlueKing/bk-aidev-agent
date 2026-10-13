---
aside: false
---

# Header 与插槽

AIBlueking 的面板头部可以通过两个插槽扩展：`#headerLeft` 位于标题区与工具栏之间，适合放环境标签、版本标识；`#headerActions` 位于右侧工具栏，在会话操作（新建 / 历史）之后、窗口控制（压缩 / 关闭）之前，适合放业务工具按钮。`showHistoryIcon` 只控制内置历史图标，与自定义图标互不影响。

<ClientOnly>
  <DemoEnvBar />
</ClientOnly>

## 头部插槽

<ClientOnly>
  <RecipeHeaderSlots />
</ClientOnly>

::: tip
- 工具按钮请放 `#headerActions`，不要塞进 `#headerLeft`：两者不在同一排，图标尺寸与 hover 样式也不同。
- 自定义图标带上 `bkai-icon` 类名，即可与内置图标保持一致的尺寸与悬停效果。
:::

## 渲染模式 renderMode

<ClientOnly>
  <RecipeRenderMode />
</ClientOnly>

## 相关文档

- [UI 定制](/guide/core-features/ui-customization)：主题、尺寸、插槽完整列表
- [消息分享](/guide/core-features/sharing)：分享模式下的对话查看
- [AIBlueking 组件 API](/api/ai-blueking/aiblueking)
