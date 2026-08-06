---
name: useArtifactPreview
slug: use-artifact-preview
category: composable
description: >-
  Provider/Consumer 模式的文件产物预览状态管理，用于 ChatContainer 侧栏「文件产物」Tab 的命中与切换。
  Provider 在 ChatContainer 中创建，Consumer 在深层文件卡片中注入使用。
aiSummary: >
  useArtifactPreviewProvider 维护 activeArtifactId（值为 outputId），openPreview 命中文件并触发 onOpen 打开侧栏 Tab；
  并通过 getOnArtifactClick 封装 resolveArtifactUrls（TTL 8 分钟缓存，force 可强制刷新，并发去重）；
  useArtifactPreviewConsumer 在后代注入同一套 API。SessionArtifact 即 AIFileInfo，会话内以 outputId 为唯一键。
  正文加载与分类型渲染不在本 composable，由 FileArtifactPanel 内 ArtifactPreviewHost 完成。
  FILE_ARTIFACT_TAB_NAME 标识固定「文件产物」Tab。
relatedComponents:
  - slug: chat-container
    relation: Provider 主场景，聚合 sessionArtifacts 并挂载 FileArtifactPanel
  - slug: file-artifact-panel
    relation: 侧栏面板消费 activeArtifactId 与 setActiveArtifactId；预览加载在面板内 Host
  - slug: assistant-message
    relation: 文件产物来源 property.artifacts
sinceVersion: 0.0.20
---

# useArtifactPreview 文件产物预览

> **分类**：composable

Provider/Consumer 模式的文件产物预览状态管理。Provider 在 `ChatContainer` 中创建，负责维护当前命中的文件 `outputId`；Consumer 在深层 `ArtifactFileCard` 中注入，用于点击卡片触发预览。

**职责边界**：

- **本 composable**：维护「命中文件」与「URL 解析」（TTL 缓存 + 并发去重，重试可 `force` 刷新）；打开侧栏 Tab（`addCustomTab`）由容器通过 `onOpen` 注入
- **不在本 composable**：聚合会话文件列表、渲染预览面板、按类型 fetch 正文 / iframe 展示 —— 分别由 `useMessageGroup.sessionArtifacts`、`FileArtifactPanel`、内部 `ArtifactPreviewHost` + `useArtifactPreviewLoader` 承担

## 函数签名

### useArtifactPreviewProvider

```typescript
function useArtifactPreviewProvider(options: {
  /** 读取业务侧异步取链回调（getter 保持对 props 变更敏感） */
  getOnArtifactClick?: () => OnArtifactClick | undefined;
  /** 命中文件后触发：由容器负责 addCustomTab + 展开侧栏 + 选中 Tab */
  onOpen: (outputId: string) => void;
}): {
  activeArtifactId: ShallowRef<string>;
  canResolveArtifactUrl: ComputedRef<boolean>;
  openPreview: (payload: OpenArtifactPreviewPayload) => void;
  resolveArtifactUrls: (file: AIFileInfo, options?: { force?: boolean }) => Promise<ArtifactUrlResult>;
  setActiveArtifactId: (id: string) => void;
};
```

### useArtifactPreviewConsumer

```typescript
function useArtifactPreviewConsumer():
  | undefined
  | {
      activeArtifactId: Ref<string>;
      canResolveArtifactUrl: ComputedRef<boolean>;
      openPreview: (payload: OpenArtifactPreviewPayload) => void;
      resolveArtifactUrls: (file: AIFileInfo, options?: { force?: boolean }) => Promise<ArtifactUrlResult>;
      setActiveArtifactId: (id: string) => void;
    };
```

## 使用示例

### Provider（ChatContainer）

会话级文件产物由 [`useMessageGroup`](./use-message-group) 统一聚合（`sessionArtifacts`），Provider 只负责命中与打开侧栏 Tab：

```typescript
import {
  useArtifactPreviewProvider,
  useCustomTabProvider,
  useMessageGroup,
  FILE_ARTIFACT_TAB_NAME,
} from '@blueking/chat-x';
import { t } from '@blueking/chat-x/lang';

const { addCustomTab, ensureCustomTab, removeCustomTab } = useCustomTabProvider({ /* ... */ });

// 会话级文件产物聚合已内聚在 useMessageGroup，直接消费
const { sessionArtifacts } = useMessageGroup({ keyword, messages, selectedUserMessages });

const FILE_ARTIFACT_TAB = {
  closable: false,
  label: t('文件产物'),
  name: FILE_ARTIFACT_TAB_NAME,
  order: -1,
};

// 常驻挂载：不随产物有无增删，无产物时由面板展示空态
ensureCustomTab(FILE_ARTIFACT_TAB);

const { activeArtifactId, setActiveArtifactId } = useArtifactPreviewProvider({
  getOnArtifactClick: () => props.onArtifactClick,
  // 点击文件卡片：展开侧栏并选中「文件产物」Tab
  onOpen: () => {
    addCustomTab(FILE_ARTIFACT_TAB);
  },
});

// 仅维护命中态：无产物清空，命中项失效时回落到第一个
watch(sessionArtifacts, list => {
  if (!list.length) {
    setActiveArtifactId('');
    return;
  }
  if (!list.some(item => item.outputId === activeArtifactId.value)) {
    setActiveArtifactId(list[0].outputId);
  }
}, { immediate: true });
```

### Consumer（ArtifactFileCard）

```typescript
import { useArtifactPreviewConsumer } from '@blueking/chat-x';

const artifactPreview = useArtifactPreviewConsumer();

// 有 Provider 时卡片可点击；无 Provider 时返回 undefined，卡片不可点击
const clickable = computed(() => !!props.onPreview || !!artifactPreview);

const handleCardClick = () => {
  if (props.onPreview) {
    props.onPreview(props.file);
    return;
  }
  artifactPreview?.openPreview({ file: props.file });
};
```

### 侧栏列表内切换命中文件

```typescript
// FileArtifactPanel 列表点击 → emit select(outputId) → 容器调用 setActiveArtifactId
// 右侧预览由面板内 ArtifactPreviewHost 消费 activeArtifact，自行取链并按类型渲染
<FileArtifactPanel
  :active-id="activeArtifactId"
  :artifacts="sessionArtifacts"
  @select="setActiveArtifactId"
/>
```

### 业务侧取链（ChatContainer `onArtifactClick`）

文本类预览需要可 `fetch` 的 `download_url`；iframe 类需要 `preview_url`（一般为后台转好的 PDF）：

```typescript
const onArtifactClick = async (file: AIFileInfo) => {
  const res = await api.getArtifactUrls(file.outputId);
  return {
    download_url: res.download_url,
    preview_url: res.preview_url,
  };
};
```

## 内置常量

| 常量名                    | 值                 | 说明                                      |
| ------------------------- | ------------------ | ----------------------------------------- |
| `FILE_ARTIFACT_TAB_NAME`  | `'file-artifact'`  | 「文件产物」侧栏 Tab 的固定标识，不可关闭 |
| `ARTIFACT_PREVIEW_TOKEN`  | `Symbol`           | provide/inject 注入 Token                 |

## 返回值说明

| 属性/方法名         | 类型                                      | 说明                                                                 |
| ------------------- | ----------------------------------------- | -------------------------------------------------------------------- |
| activeArtifactId    | `ShallowRef<string>`                      | 当前命中的文件 `outputId`                                            |
| canResolveArtifactUrl | `ComputedRef<boolean>`                  | 是否具备异步取链能力（有 `onArtifactClick` 时为 true，下载按钮据此显隐） |
| openPreview         | `(payload: OpenArtifactPreviewPayload) => void` | 由文件卡片触发：以 `file.outputId` 更新命中态、调用 `onOpen`   |
| resolveArtifactUrls | `(file: AIFileInfo, options?: { force?: boolean }) => Promise<ArtifactUrlResult>` | 调用 `onArtifactClick` 取链；成功结果按 `outputId` 缓存 8 分钟；`force` 绕过缓存；并发去重 |
| setActiveArtifactId | `(id: string) => void`                    | 直接设置命中文件 `outputId`；侧栏列表内切换选中时使用                |

## 类型定义

```typescript
import type { AIFileInfo, ArtifactUrlResult, OnArtifactClick } from '@blueking/chat-x';

/** 打开预览时的入参 */
type OpenArtifactPreviewPayload = {
  file: AIFileInfo;
};

/**
 * 会话级文件产物：以 outputId 为会话内唯一键（同 outputId 视为同一文件）。
 * 拍平去重后即为 AIFileInfo，此处用别名标明语义。
 */
type SessionArtifact = AIFileInfo;

/** onArtifactClick 返回值（snake_case） */
type ArtifactUrlResult = {
  download_url?: string;
  preview_url?: string;
};
```

## 唯一键规则

会话内以 **`outputId`** 作为文件产物唯一键：

- 同一 `outputId` 在多条 `AssistantMessage` 中出现时，`sessionArtifacts` 去重并保留**最后一次**出现的文件信息
- `activeArtifactId`、列表 `:key`、`select` 事件参数均使用 `outputId`
- 文件名可能重复，**不可**作为唯一键

## 完整触发链路

```
ArtifactFileCard（点击）
  └─ useArtifactPreviewConsumer().openPreview({ file })
       └─ useArtifactPreviewProvider（ChatContainer）
            ├─ activeArtifactId = file.outputId
            └─ onOpen(outputId) → addCustomTab(FILE_ARTIFACT_TAB_NAME) 展开并选中
                 └─ FileArtifactPanel（列表 + 下载头，@select → setActiveArtifactId）
                      └─ ArtifactPreviewHost（loader + 分类型 renderer）

容器初始化
  └─ ensureCustomTab(FILE_ARTIFACT_TAB_NAME) 常驻挂上（不展开侧栏）；因 order:-1 排在首位，
     未主动切换过 Tab 时会成为默认选中面板；无产物时由面板展示整块空态

sessionArtifacts 变化
  └─ 仅维护命中态（无产物清空，命中项失效回落第一个）；不增删 Tab
```

分类型预览策略见 [FileArtifactPanel 预览机制](../components/message/file-artifact-panel#预览机制)。

## 设计特点

- **职责单一**：composable 不直接调用 `useCustomTab`，侧栏 Tab 打开逻辑由 `onOpen` 注入；也不做正文 fetch / iframe 渲染
- **ShallowRef 优先**：`activeArtifactId` 使用 `shallowRef`，避免不必要的深层响应式开销
- **Consumer 兜底**：`useArtifactPreviewConsumer` 无 Provider 时返回 `undefined`，文件卡片在无容器上下文时自动不可点击
- **与 useCustomTab 协作**：点击卡片走 `addCustomTab`（展开 + 选中）；容器初始化时走 `ensureCustomTab` 常驻挂载（不展开；因 `order: -1` 在未主动切换前会成为默认选中），无产物也不移除，由面板展示空态

## 关联组件

- [ChatContainer](../components/setup/chat-container) — Provider 主场景，内置「文件产物」Tab
- [FileArtifactPanel](../components/message/file-artifact-panel) — 侧栏列表与预览 Host 挂载
- [AssistantMessage](../components/message/assistant-message) — 文件产物来源（`property.artifacts`）
- [useCustomTab](./use-custom-tab) — `addCustomTab` / `ensureCustomTab` 分工
