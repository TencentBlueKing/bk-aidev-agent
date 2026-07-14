---
name: FileArtifactPanel 文件产物预览
slug: file-artifact-panel
kind: component
domain: message
description: 汇总当前会话全部文件产物，支持搜索、选中与 HTML / PDF 预览，挂载在 ChatContainer 侧栏「文件产物」Tab。
aiSummary: >
  汇总当前会话所有 AssistantMessage 的 artifacts，支持关键词搜索、列表选中与预览；
  HTML 走 fetch + iframe srcdoc 渲染，其余类型直接用 previewUrl（后台转好的 PDF）iframe 展示。
  源码位置：src/components/chat-message/assistant-message/message-artifacts/file-artifact-panel.vue。
relatedComponents:
  - slug: assistant-message
    relation: 文件产物来源于 AssistantMessage.property.artifacts
  - slug: chat-container
    relation: 面板挂载在侧栏「文件产物」Tab（固定、不可关闭）
  - slug: execution-summary
    relation: 同为 ChatContainer 侧栏 Tab 面板，交互形态一致
sinceVersion: 0.0.20
---

# FileArtifactPanel 文件产物预览

## 源码事实

- **源码位置**：`src/components/chat-message/assistant-message/message-artifacts/file-artifact-panel.vue`
- **能力域**：消息系统
- **能力说明**：汇总当前会话全部文件产物，支持搜索、选中与 HTML / PDF 预览。

> **能力域**：消息系统

点击 AI 回复中的[文件卡片](/components/message/assistant-message)后，`ChatContainer` 侧栏会弹出固定的「文件产物」Tab，聚合展示当前会话**所有** `AssistantMessage` 的文件产物，并命中被点击的文件进行预览。

面板左侧为可搜索的文件列表，右侧为预览区。通常不需要直接使用，由 `ChatContainer` 在侧栏内自动渲染。

## 核心能力

- **会话级聚合**：拍平当前会话所有 `AssistantMessage.property.artifacts`，统一在一个列表内展示
- **唯一命中**：同一会话可能出现多个消息 + 同名文件，文件名不可作唯一键，统一用 `messageUid#消息内下标#outputId` 生成全局唯一 id
- **关键词搜索**：按文件名实时过滤列表
- **分类型预览**：
  - **HTML**：前端 `fetch(file.url)` 拉取 HTML 字符串，用 `<iframe srcdoc>` 渲染，带加载 / 失败重试态
  - **其余类型**：`previewUrl` 是后台转换好的 PDF 链接，直接作为 `<iframe src>` 展示
- **下载**：列表项与预览头部均可下载源文件（`file.url`）

## 触发链路

```
ArtifactFileCard（点击文件卡片）
  └─ useArtifactPreviewConsumer().openPreview({ file, index, messageUid })
       └─ useArtifactPreviewProvider（ChatContainer 内）
            ├─ 记录命中文件 activeArtifactId
            └─ onOpen → addCustomTab('file-artifact') 展开并选中侧栏 Tab
                 └─ FileArtifactPanel（渲染列表 + 预览）
```

- 文件卡片通过 `useArtifactPreviewConsumer` 注入预览上下文，无 Provider 时卡片不可点击（兜底 `undefined`）
- `ChatContainer` 通过 `useArtifactPreviewProvider` 提供上下文，并把「打开侧栏 Tab」这一副作用以 `onOpen` 注入，保持 composable 职责单一（只维护命中文件这一份状态）
- 侧栏「文件产物」Tab 固定不可关闭，`order: -1` 排在「执行情况」之前；会话切换或无文件产物时自动移除

## 唯一 id 规则

同一会话可能存在多个 `AssistantMessage`，且不同消息里可能有同名文件，因此**文件名不可作为唯一键**。统一由 `buildArtifactId` 生成：

```typescript
import { buildArtifactId } from '@blueking/chat-x';

// messageUid#消息内下标#outputId
buildArtifactId('msg-a', 2, 'output-9'); // => 'msg-a#2#output-9'
```

Provider 侧聚合与文件卡片侧透传必须使用同一规则，保证命中一致。

## 预览机制

| 文件类型 | 预览字段 | 渲染方式 |
| -------- | -------- | -------- |
| `html`   | `file.url` | `fetch(url)` 拿到 HTML 字符串 → `<iframe srcdoc>` 渲染，切换文件会中断上一次请求避免竞态 |
| 其余     | `file.previewUrl` | 后台已转换为 PDF，直接 `<iframe src="previewUrl">` 展示 |

## API

### Props

| 属性名    | 类型                | 必填 | 说明                                   |
| --------- | ------------------- | ---- | -------------------------------------- |
| activeId  | `string`            | ✓    | 当前命中的文件 id（`messageUid#index#outputId`） |
| artifacts | `SessionArtifact[]` | ✓    | 当前会话全部文件产物                   |

### Events

| 事件名 | 参数              | 说明                       |
| ------ | ----------------- | -------------------------- |
| select | `(id: string)`    | 列表内切换选中文件，参数为文件 `artifactId` |

## 类型定义

```typescript
import type { AIFileInfo, SessionArtifact } from '@blueking/chat-x';

// 会话级文件产物：在 AIFileInfo 基础上补充命中所需字段
type SessionArtifact = AIFileInfo & {
  artifactId: string; // 全局唯一 id：messageUid#index#outputId
  messageUid: string; // 所属 AssistantMessage 的 uid
};
```

## 关联 Composable

预览状态由 [useArtifactPreview](/composables/use-artifact-preview) 提供，Provider / Consumer 通过 `ARTIFACT_PREVIEW_TOKEN` 通信。容器侧 `useArtifactPreviewProvider` 维护 `activeArtifactId` 并通过 `onOpen` 打开侧栏 Tab；文件卡片侧 `useArtifactPreviewConsumer` 触发 `openPreview`。

## 关联组件

- [AssistantMessage](/components/message/assistant-message) — 文件产物来源（`property.artifacts`）
- [ChatContainer](/components/setup/chat-container) — 侧栏「文件产物」Tab 挂载场景
- [ExecutionSummary](/components/agent/execution-summary) — 同为侧栏 Tab 面板
