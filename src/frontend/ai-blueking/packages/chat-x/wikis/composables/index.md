# Composables 组合式函数

`@blueking/chat-x` 提供的可复用组合式函数，涵盖剪贴板、容器滚动、文本动画、键盘导航等常用交互逻辑。

## 函数列表

### 面向用户（推荐直接使用）

| 函数名                       | 说明                                                                                                                              | 文档                              |
| ---------------------------- | --------------------------------------------------------------------------------------------------------------------------------- | --------------------------------- |
| `useClipboard`               | 复制文本到剪贴板；内置 Clipboard API → `execCommand` 两级降级，自动弹出成功/失败提示                                              | [查看](./use-clipboard.md)        |
| `useContainerScrollProvider` | 消息容器滚动控制 Provider；基于 IntersectionObserver + wheel 事件管理 `isScrollBottom`、`scrollBottomHeight`、`autoScrollEnabled` | [查看](./use-container-scroll.md) |
| `useContainerScrollConsumer` | 获取父级 Provider 共享的滚动控制；在后代组件中调用 `toScrollBottom`                                                               | [查看](./use-container-scroll.md) |
| `useAnimationText`           | 流式文本动画；将文本拆分为块并逐块渐显，适用于 AI 打字机效果                                                                      | [查看](./use-animation-text.md)   |
| `useMessageGroup`            | 消息分组逻辑；将 `Message[]` 转为 `MessageGroup[]`，处理 Tool 合并、Loading 注入、执行摘要过滤和分享模式                          | [查看](./use-message-group.md)    |
| `useCustomTabProvider`       | 自定义 Tab 管理 Provider；用于 `ChatContainer` 侧边栏的 Tab 动态增删和切换                                                        | [查看](./use-custom-tab.md)       |
| `useCustomTabConsumer`       | 自定义 Tab 管理 Consumer；在后代组件中注入并操作 Tab（添加/移除/选中）                                                            | [查看](./use-custom-tab.md)       |
| `useArtifactPreviewProvider` | 文件产物预览 Provider；维护命中文件 `outputId`，通过 `onOpen` 触发侧栏「文件产物」Tab                                               | [查看](./use-artifact-preview.md) |
| `useArtifactPreviewConsumer` | 文件产物预览 Consumer；在深层文件卡片中注入，点击触发 `openPreview`                                                               | [查看](./use-artifact-preview.md) |
| `useInputMentionProvider`    | 「资源插入输入框」Provider；由持有 `ChatInput` 的容器提供 `insertMention`                                                          | [查看](./use-input-mention.md)    |
| `useInputMentionConsumer`    | 「资源插入输入框」Consumer；无 Provider（只读 / 分享态）时返回 `undefined`，调用方据此隐藏引用入口                                  | [查看](./use-input-mention.md)    |
| `useFullScreen`              | 浏览器原生全屏控制；嗅探标准/WebKit API，`isFullScreen` 与 ESC 退出同步；`ChatContainer` 侧栏全屏使用                               | [查看](./use-full-screen.md)      |
| `useParentScrolling`         | 查找最近可滚动祖先并监听 `scroll`/`scrollend`；提供 `isScrolling` 状态，常用于滚动时隐藏浮层                                      | [查看](./use-parent-scrolling.md) |
| `getScrollParent`            | 独立辅助函数；递归向上查找第一个 `overflowY` 可滚动的祖先元素                                                                     | [查看](./use-parent-scrolling.md) |

### 面向组件库内部（通常无需直接使用）

| 函数名                   | 内部使用方                    | 说明                                                                                    | 文档                                   |
| ------------------------ | ----------------------------- | --------------------------------------------------------------------------------------- | -------------------------------------- |
| `useMenuKeydown`         | `InputMenuPanel`、`ModelSelectorPanel` | 在 `window` 捕获阶段注册键盘监听，管理菜单 `activeIndex`，支持 ↑↓ 循环导航和 Enter 确认 | [查看](./use-menu-keydown.md)          |
| `useObserverVisibleList` | `ShortcutBtns`                | 基于 `ResizeObserver` + 贪心算法计算容器内可见项子集，为"更多"按钮动态预留空间          | [查看](./use-observer-visible-list.md) |
| `useGlobalConfig`        | 根容器组件                    | 向后代 provide 全局展示配置（`size` / `supportUpload` / `timezone` / `menuSources`）    | [查看](./use-global-config.md)         |
| `injectGlobalConfig`     | 任意后代组件                  | 取出全局展示配置，无 Provider 时返回 `undefined`                                        | [查看](./use-global-config.md)         |
| `useCommandSelection`    | `AiSlashInput`                | edix 编辑器的光标位置快照工具；返回 `GetCursorPosition` 命令和 `commandSelection`       | [查看](./use-command-selection.md)     |

## 引入方式

```typescript
import {
  // 剪贴板
  useClipboard,

  // 容器滚动（Provider/Consumer）
  useContainerScrollProvider,
  useContainerScrollConsumer,

  // 文本动画
  useAnimationText,

  // 消息分组
  useMessageGroup,

  // 自定义 Tab（Provider/Consumer）
  useCustomTabProvider,
  useCustomTabConsumer,

  // 文件产物预览（Provider/Consumer）
  useArtifactPreviewProvider,
  useArtifactPreviewConsumer,
  FILE_ARTIFACT_TAB_NAME,

  // 资源插入输入框（Provider/Consumer）
  useInputMentionProvider,
  useInputMentionConsumer,

  // 全屏控制
  useFullScreen,

  // 父容器滚动
  useParentScrolling,
  getScrollParent,

  // 内部：菜单键盘导航
  useMenuKeydown,

  // 内部：可见列表计算
  useObserverVisibleList,

  // 内部：全局展示配置
  useGlobalConfig,
  injectGlobalConfig,

  // 内部：edix 光标追踪
  useCommandSelection,
} from '@blueking/chat-x';
```

## 各函数速查

### useClipboard

```typescript
const { copy } = useClipboard();
copy('要复制的文本'); // 自动弹出提示，无需处理返回值
```

### useContainerScrollProvider / Consumer

```typescript
// 父组件
const { isScrollBottom, scrollBottomHeight, autoScrollEnabled, toScrollBottom, toScrollTop } =
  useContainerScrollProvider(containerRef, bottomRef);

// 子组件（inject）
const containerScroll = useContainerScrollConsumer();
containerScroll?.value?.toScrollBottom?.();
```

### useAnimationText

```typescript
const { chunks, animStyle } = useAnimationText(textRef, { immediate: false });
// chunks：分块后的文本数组；animStyle：CSS animation 样式对象
```

### useMessageGroup

```typescript
const { messageGroups, executionGroups, isShareMode, isAllSelected, onToggleShareAll, onCancelShare, onConfirmShare } =
  useMessageGroup({ keyword, messages: computed(() => props.messages), selectedUserMessages });
// messageGroups：完整消息分组；executionGroups：仅执行类消息分组
```

### useCustomTabProvider / Consumer

```typescript
// Provider（容器组件）
const { tabs, selectedTab, isCollapse, addCustomTab, ensureCustomTab, removeCustomTab, selectCustomTab } =
  useCustomTabProvider({
    onTabChange: async tab => fetchData(tab.name),
  });

// Consumer（后代组件）
const tabManager = useCustomTabConsumer();
// 展开并选中
tabManager?.addCustomTab({ name: 'detail', label: '详情', data: { component: DetailComp } });
// 仅挂载不展开；未主动切换过时选中会跟随 Tab 栏首位（order 更小者）
tabManager?.ensureCustomTab({ name: 'file-artifact', label: '文件产物', closable: false, order: -1 });
```

### useArtifactPreviewProvider / Consumer

```typescript
// Provider（ChatContainer）
const { activeArtifactId, setActiveArtifactId } = useArtifactPreviewProvider({
  onOpen: () => addCustomTab({ name: FILE_ARTIFACT_TAB_NAME, label: '文件产物', closable: false, order: -1 }),
});

// Consumer（文件卡片）
const artifactPreview = useArtifactPreviewConsumer();
artifactPreview?.openPreview({ file });
```

### useInputMentionProvider / Consumer

```typescript
// Provider（ChatContainer）
useInputMentionProvider({
  insertMention: item => chatInputRef.value?.insertMention?.(item),
});

// Consumer（文件卡片 / 侧栏产物面板）
const inputMention = useInputMentionConsumer();
inputMention?.insertMention(toArtifactMenuItem(file));
```

### useParentScrolling

```typescript
const { isScrolling, scrollParent } = useParentScrolling(elementRef);
// isScrolling：父容器是否正在滚动（300ms 定时器 + scrollend 双重重置）
// scrollParent：找到的最近可滚动祖先元素
```

### useMenuKeydown

```typescript
// window 捕获阶段自动注册，无需手动绑定 @keydown
const { activeIndex } = useMenuKeydown({ items, menuRef, onSelect });
// 模板中将 activeIndex 对应项加 .is-active 类即可
```

## 设计特点

| 特性              | 说明                                                                       |
| ----------------- | -------------------------------------------------------------------------- |
| 自动清理          | 全部使用 `onScopeDispose` 清理事件监听、Observer、定时器，无内存泄漏       |
| ShallowRef 优先   | 返回值使用 `shallowRef` 而非 `ref`，避免深层响应式开销                     |
| MaybeRef 参数     | 部分函数（如 `useParentScrolling`）接受 `MaybeRef`，支持传入普通元素或 ref |
| Provider/Consumer | 跨层级数据共享通过 Vue `provide/inject` 实现，无需 props 透传              |
