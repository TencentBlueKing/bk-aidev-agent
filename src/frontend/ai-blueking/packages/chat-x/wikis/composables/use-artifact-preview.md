---
name: useArtifactPreview
slug: use-artifact-preview
category: composable
description: >-
  Provider/Consumer 模式的文件产物预览状态管理，用于 ChatContainer 侧栏「文件产物」Tab 的命中与切换。
  Provider 在 ChatContainer 中创建，Consumer 在深层文件卡片中注入使用。
aiSummary: >
  useArtifactPreviewProvider 维护 activeArtifactId，openPreview 命中文件并触发 onOpen 打开侧栏 Tab；
  useArtifactPreviewConsumer 在后代注入同一套 API。buildArtifactId 用 messageUid#index#outputId 生成唯一 id。
  FILE_ARTIFACT_TAB_NAME 标识固定「文件产物」Tab。
relatedComponents:
  - slug: chat-container
    relation: Provider 主场景，聚合 sessionArtifacts 并挂载 FileArtifactPanel
  - slug: file-artifact-panel
    relation: 侧栏面板消费 activeArtifactId 与 setActiveArtifactId
  - slug: assistant-message
    relation: 文件产物来源 property.artifacts
sinceVersion: 0.0.20
---

# useArtifactPreview 文件产物预览

> **分类**：composable

Provider/Consumer 模式的文件产物预览状态管理。Provider 在 `ChatContainer` 中创建，负责维护当前命中的文件 id；Consumer 在深层 `ArtifactFileCard` 中注入，用于点击卡片触发预览。

**职责边界**：composable 只维护「命中文件」这一份数据状态；打开侧栏 Tab（`addCustomTab`）、聚合会话文件列表、渲染预览面板等副作用由 `ChatContainer` 承担，通过 `onOpen` 回调注入，避免直接依赖 `useCustomTab`。

## 函数签名

### useArtifactPreviewProvider

```typescript
function useArtifactPreviewProvider(options: {
  /** 命中文件后触发：由容器负责 addCustomTab + 展开侧栏 + 选中 Tab */
  onOpen: (artifactId: string) => void;
}): {
  activeArtifactId: ShallowRef<string>;
  openPreview: (payload: OpenArtifactPreviewPayload) => void;
  setActiveArtifactId: (id: string) => void;
};
```

### useArtifactPreviewConsumer

```typescript
function useArtifactPreviewConsumer():
  | undefined
  | {
      activeArtifactId: Ref<string>;
      openPreview: (payload: OpenArtifactPreviewPayload) => void;
      setActiveArtifactId: (id: string) => void;
    };
```

### buildArtifactId

```typescript
function buildArtifactId(messageUid: string, index: number, outputId: string): string;
// => `${messageUid}#${index}#${outputId}`
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

const { addCustomTab, removeCustomTab } = useCustomTabProvider({ /* ... */ });

// 会话级文件产物聚合已内聚在 useMessageGroup，直接消费
const { sessionArtifacts } = useMessageGroup({ keyword, messages, selectedUserMessages });

const { activeArtifactId, setActiveArtifactId } = useArtifactPreviewProvider({
  onOpen: () => {
    addCustomTab({
      closable: false,
      label: t('文件产物'),
      name: FILE_ARTIFACT_TAB_NAME,
      order: -1,
    });
  },
});

// 无文件产物时清理 Tab 与命中态
watch(sessionArtifacts, list => {
  if (!list.length) {
    removeCustomTab(FILE_ARTIFACT_TAB_NAME);
    setActiveArtifactId('');
  }
});
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
  artifactPreview?.openPreview({
    file: props.file,
    index: props.index ?? 0,
    messageUid: props.messageUid ?? '',
  });
};
```

### 侧栏列表内切换命中文件

```typescript
// FileArtifactPanel 列表点击 → emit select → 容器调用 setActiveArtifactId
<FileArtifactPanel
  :active-id="activeArtifactId"
  :artifacts="sessionArtifacts"
  @select="setActiveArtifactId"
/>
```

## 内置常量

| 常量名                    | 值                 | 说明                                      |
| ------------------------- | ------------------ | ----------------------------------------- |
| `FILE_ARTIFACT_TAB_NAME`  | `'file-artifact'`  | 「文件产物」侧栏 Tab 的固定标识，不可关闭 |
| `ARTIFACT_PREVIEW_TOKEN`  | `Symbol`           | provide/inject 注入 Token                 |

## 返回值说明

| 属性/方法名         | 类型                                      | 说明                                                                 |
| ------------------- | ----------------------------------------- | -------------------------------------------------------------------- |
| activeArtifactId    | `ShallowRef<string>`                      | 当前命中的文件 id（`messageUid#index#outputId`）                     |
| openPreview         | `(payload: OpenArtifactPreviewPayload) => void` | 由文件卡片触发：计算 id、更新命中态、调用 `onOpen`             |
| setActiveArtifactId | `(id: string) => void`                    | 直接设置命中文件 id；侧栏列表内切换选中时使用                        |

## 类型定义

```typescript
import type { AIFileInfo } from '@blueking/chat-x';

/** 打开预览时的入参：文件 + 消息内下标 + 所属消息 uid */
type OpenArtifactPreviewPayload = {
  file: AIFileInfo;
  index: number;
  messageUid: string;
};

/**
 * 会话级文件产物：在 AIFileInfo 基础上补充命中所需的唯一 id 与所属消息。
 * 同一会话可能出现多个 AssistantMessage + 同名文件，文件名不可作唯一键。
 */
type SessionArtifact = AIFileInfo & {
  artifactId: string;
  messageUid: string;
};
```

## 唯一 id 规则

同一会话可能存在多个 `AssistantMessage`，且不同消息里可能有同名文件，因此**文件名不可作为唯一键**。Provider 侧聚合与 Consumer 侧透传必须使用同一 `buildArtifactId` 规则：

```typescript
buildArtifactId('msg-a', 2, 'output-9'); // => 'msg-a#2#output-9'
```

- `messageUid`：所属 `AssistantMessage` 的 `uid`（回退 `String(id)`）
- `index`：文件在所属消息 `property.artifacts` 数组中的下标
- `outputId`：文件自身的 `AIFileInfo.outputId`

## 完整触发链路

```
ArtifactFileCard（点击）
  └─ useArtifactPreviewConsumer().openPreview({ file, index, messageUid })
       └─ useArtifactPreviewProvider（ChatContainer）
            ├─ activeArtifactId = buildArtifactId(...)
            └─ onOpen(artifactId) → addCustomTab(FILE_ARTIFACT_TAB_NAME)
                 └─ FileArtifactPanel（列表 + 预览，@select → setActiveArtifactId）
```

## 设计特点

- **职责单一**：composable 不直接调用 `useCustomTab`，侧栏 Tab 打开逻辑由 `onOpen` 注入
- **ShallowRef 优先**：`activeArtifactId` 使用 `shallowRef`，避免不必要的深层响应式开销
- **Consumer 兜底**：`useArtifactPreviewConsumer` 无 Provider 时返回 `undefined`，文件卡片在无容器上下文时自动不可点击
- **与 useCustomTab 协作**：「文件产物」Tab 通过 `addCustomTab` 按需添加（`order: -1`、`closable: false`），会话无文件产物时由容器 `removeCustomTab` 清理

## 关联组件

- [ChatContainer](../components/setup/chat-container) — Provider 主场景，内置「文件产物」Tab
- [FileArtifactPanel](../components/message/file-artifact-panel) — 侧栏预览面板
- [AssistantMessage](../components/message/assistant-message) — 文件产物来源（`property.artifacts`）
