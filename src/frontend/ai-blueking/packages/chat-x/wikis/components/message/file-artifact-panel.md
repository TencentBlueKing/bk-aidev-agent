---
name: FileArtifactPanel 文件产物预览
slug: file-artifact-panel
kind: component
domain: message
description: 汇总当前会话全部文件产物，支持搜索、选中与分类型预览，挂载在 ChatContainer 侧栏「文件产物」Tab。
aiSummary: >
  汇总当前会话所有 AssistantMessage 的 artifacts（按 outputId 去重），支持关键词搜索、列表选中与下载；
  预览区委托 ArtifactPreviewHost：按类型走 text_from_download（html / markdown / md / txt / json）
  或 preview_url_iframe（其余类型）；download_url / preview_url 经 onArtifactClick 异步获取。
  源码位置：src/components/chat-message/assistant-message/message-artifacts/file-artifact-panel.vue。
relatedComponents:
  - slug: assistant-message
    relation: 文件产物来源于 AssistantMessage.property.artifacts
  - slug: chat-container
    relation: 面板挂载在侧栏「文件产物」Tab（固定、不可关闭），并通过 onArtifactClick 异步取链
  - slug: execution-summary
    relation: 同为 ChatContainer 侧栏 Tab 面板，交互形态一致
  - slug: message-loading
    relation: ArtifactPreviewHost 取链 / 拉取正文过程使用 MessageLoading
sinceVersion: 0.0.20
---

<script lang="ts" setup>
  import { shallowRef } from 'vue'

  import { MOCK_FILE_ARTIFACTS, mockArtifactClick } from '../../../playground/mock'
  import FileArtifactPanelComp from '../../../src/components/chat-message/assistant-message/message-artifacts/file-artifact-panel.vue'
  import { useArtifactPreviewProvider } from '../../../src/composables/use-artifact-preview'

  const demoArtifacts = MOCK_FILE_ARTIFACTS

  const activeArtifactId = shallowRef(demoArtifacts[0]?.outputId ?? '')

  // 文档站单独挂载面板时需自行提供 Provider；业务侧由 ChatContainer 注入
  useArtifactPreviewProvider({
    getOnArtifactClick: () => mockArtifactClick,
    onOpen: () => {},
  })

  const handleSelectArtifact = (id: string) => {
    activeArtifactId.value = id
  }
</script>

# FileArtifactPanel 文件产物预览

## 源码事实

- **源码位置**：`src/components/chat-message/assistant-message/message-artifacts/file-artifact-panel.vue`
- **能力域**：消息系统
- **能力说明**：汇总当前会话全部文件产物；左侧列表搜索与选中，右侧预览委托内部 `ArtifactPreviewHost`。

> **导出说明**：内部侧栏面板组件，**通常不直接使用**；由 `ChatContainer` 在「文件产物」Tab 内自动挂载。预览加载与渲染为同目录下 `artifact-preview/` 内部实现，不单独导出。

点击 AI 回复中的[文件卡片](/components/message/assistant-message)后，`ChatContainer` 侧栏会弹出固定的「文件产物」Tab，聚合展示当前会话**所有** `AssistantMessage` 的文件产物（按 `outputId` 去重），并命中被点击的文件进行预览。

面板左侧为可搜索的文件列表，右侧为预览区。通常不需要直接使用，由 `ChatContainer` 在侧栏内自动渲染。

## 核心能力

- **会话级聚合**：拍平当前会话所有 `AssistantMessage.property.artifacts`，以 `outputId` 去重后统一在一个列表内展示
- **唯一命中**：以 `outputId` 作为会话内唯一键（同 `outputId` 视为同一文件）；文件名可能重复，不可作唯一键
- **关键词搜索**：按文件名实时过滤列表
- **整块空态**：`artifacts` 为空时不渲染列表与预览区，整块展示 bkui `Exception`「暂无数据」（Tab 常驻，无数据也可正常打开侧栏）
- **异步取链**：`AIFileInfo` 本身不含 `url` / `previewUrl`，通过 `ChatContainer` 的 `onArtifactClick` 按 `outputId` 获取 `download_url` / `preview_url`（TTL 8 分钟缓存；预览重试会 `force` 刷新）
- **职责拆分**：
  - **面板本身**：列表、搜索、预览头（文件名 / 图标 / 下载）
  - **`ArtifactPreviewHost`**：按策略加载正文或预览 URL，分派到对应 renderer；展示 loading / empty / error（含重试）
- **未传 `onArtifactClick`**：下载按钮隐藏，预览区展示无数据

## 基础用法

面板**未从包入口导出**，业务侧请走下方「业务接入」；下列示例仅用于文档站 / 本地调试（与 `ExecutionSummary` 文档站写法一致：相对路径引入 + 自行挂 Provider）。

```vue
<template>
  <div style="height: 480px; border: 1px solid #dcdee5; border-radius: 8px; overflow: hidden;">
    <FileArtifactPanel
      :active-id="activeArtifactId"
      :artifacts="sessionArtifacts"
      @select="handleSelect"
    />
  </div>
</template>

<script setup lang="ts">
  import { shallowRef } from 'vue'
  import { useArtifactPreviewProvider } from '@blueking/chat-x'
  import type { AIFileInfo, SessionArtifact } from '@blueking/chat-x'
  // 内部组件：仅文档 / 调试；业务请用 ChatContainer 自动挂载
  import FileArtifactPanel from './message-artifacts/file-artifact-panel.vue'

  const sessionArtifacts: SessionArtifact[] = [
    { name: '周报.html', outputId: 'a-html', size: 10240, type: 'html' },
    { name: '说明.md', outputId: 'a-md', size: 8192, type: 'md' },
    { name: '纪要.txt', outputId: 'a-txt', size: 4096, type: 'txt' },
    { name: '配置.json', outputId: 'a-json', size: 2048, type: 'json' },
    { name: '立项.pdf', outputId: 'a-pdf', size: 204800, type: 'pdf' },
  ]

  useArtifactPreviewProvider({
    getOnArtifactClick: () => async file => {
      // 文本类返回可 fetch 的 download_url；iframe 类返回 preview_url
      const res = await api.getArtifactUrls(file.outputId)
      return { download_url: res.download_url, preview_url: res.preview_url }
    },
    onOpen: () => {},
  })

  const activeArtifactId = shallowRef(sessionArtifacts[0].outputId)
  const handleSelect = (id: string) => {
    activeArtifactId.value = id
  }
</script>
```

**渲染效果**（点击左侧列表切换类型；文本类直渲染，PDF 走 iframe。Mock 取链约 600ms）

<div class="demo">
  <div style="height: 480px; border: 1px solid #dcdee5; border-radius: 8px; overflow: hidden;">
    <FileArtifactPanelComp
      :active-id="activeArtifactId"
      :artifacts="demoArtifacts"
      @select="handleSelectArtifact"
    />
  </div>
</div>

## 业务接入（ChatContainer）

日常用法是给容器传 `messages`（含 `property.artifacts`）与 `onArtifactClick`，点击文件卡片即可打开侧栏面板：

```vue
<template>
  <ChatContainer
    v-model="input"
    :messages="messages"
    :on-artifact-click="onArtifactClick"
    @send-message="handleSend"
  />
</template>

<script setup lang="ts">
  import { ref, shallowRef } from 'vue'
  import {
    ChatContainer,
    MessageRole,
    MessageStatus,
    type AIFileInfo,
    type Message,
  } from '@blueking/chat-x'

  const input = ref('')
  const messages = shallowRef<Message[]>([
    {
      id: 'u1',
      messageId: 'u1',
      role: MessageRole.User,
      status: MessageStatus.Complete,
      content: '整理本周评审材料',
    },
    {
      id: 'a1',
      messageId: 'a1',
      uid: 'assistant-uid-1',
      role: MessageRole.Assistant,
      status: MessageStatus.Complete,
      content: '已生成评审材料，点击卡片可在侧栏预览：',
      property: {
        artifacts: [
          { name: '周报.html', outputId: 'a-html', size: 10240, type: 'html' },
          { name: '说明.md', outputId: 'a-md', size: 8192, type: 'md' },
          { name: '配置.json', outputId: 'a-json', size: 2048, type: 'json' },
          { name: '立项.pdf', outputId: 'a-pdf', size: 204800, type: 'pdf' },
        ] satisfies AIFileInfo[],
      },
    },
  ])

  const onArtifactClick = async (file: AIFileInfo) => {
    const res = await api.getArtifactUrls(file.outputId)
    return {
      download_url: res.download_url,
      preview_url: res.preview_url,
    }
  }

  const handleSend = () => {
    /* ... */
  }
</script>
```

## 触发链路

```
ArtifactFileCard（点击文件卡片）
  └─ useArtifactPreviewConsumer().openPreview({ file })
       └─ useArtifactPreviewProvider（ChatContainer 内）
            ├─ 记录命中文件 activeArtifactId = file.outputId
            └─ onOpen → addCustomTab('file-artifact') 展开并选中侧栏 Tab
                 └─ FileArtifactPanel
                      ├─ 列表 @select → setActiveArtifactId(outputId)
                      ├─ 下载 → resolveArtifactUrls + triggerArtifactDownload
                      └─ ArtifactPreviewHost
                           ├─ useArtifactPreviewLoader（策略 + fetch / 取链，防竞态）
                           └─ HtmlPreview | MarkdownPreview | TxtPreview | UrlIframePreview

容器初始化
  └─ ensureCustomTab('file-artifact') 常驻挂上（不展开侧栏）；因 order:-1 排在首位，
     未主动切换过 Tab 时会成为默认选中面板；无产物时由面板展示整块空态
```

- 文件卡片通过 `useArtifactPreviewConsumer` 注入预览上下文，无 Provider 时卡片不可点击（兜底 `undefined`）
- `ChatContainer` 通过 `useArtifactPreviewProvider` 提供上下文，并把「打开侧栏 Tab」这一副作用以 `onOpen` 注入，保持 composable 职责单一
- 侧栏「文件产物」Tab 固定不可关闭，`order: -1` 排在「执行情况」之前；**常驻不随产物有无增删**，无产物时由面板展示整块空态

## 唯一键规则

会话内以 **`outputId`** 作为文件产物唯一键：

- 同一 `outputId` 在多条消息中出现时，聚合列表去重并保留最后一次出现的文件信息
- `activeId`、列表 `:key`、`select` 事件参数均使用 `outputId`
- 文件名可能重复，**不可**作为唯一键

## 预览机制

预览由内部 `getArtifactPreviewStrategy(type)` 决定 **加载方式** 与 **渲染器**；面板不直接写死类型分支。

| 文件类型 | load | 取链字段 | renderer |
| -------- | ---- | -------- | -------- |
| `html` | `text_from_download` | `download_url` → `fetch` 正文 | `HtmlPreview`（`<iframe srcdoc>`） |
| `markdown` / `md` | `text_from_download` | 同上 | `MarkdownPreview`（`MarkdownContent`） |
| `txt` / `json` | `text_from_download` | 同上 | `TxtPreview`（`<pre>`） |
| 其余（如 `pdf` / `jpg`） | `preview_url_iframe` | `preview_url` | `UrlIframePreview`（`<iframe src>`，一般为后台转好的 PDF） |

> `md`（`AIFileType.Md`）为后台扩展名别名，与 `markdown`（`AIFileType.Markdown`）等价，共用 Markdown 直渲染。

### 加载态

| status | 表现 |
| ------ | ---- |
| `loading` | 预览区 [MessageLoading](/components/helper/message-loading) |
| `ready` | 对应 renderer 渲染 |
| `empty` | 「暂无可预览的文件」（无文件 / 未传 `onArtifactClick` / 缺所需 URL） |
| `error` | 「预览加载失败」+ 重试按钮 |

切换文件时 `useArtifactPreviewLoader` 用 `loadSeq` + `AbortController` 中断上一次 `fetch`，避免竞态覆盖。下载图标仍由面板用 bkui `Loading` spin 单独表达。

## 内部结构（不导出）

```
message-artifacts/
├── file-artifact-panel.vue          # 列表 + 下载头 + 挂载 Host
└── artifact-preview/
    ├── artifact-preview-host.vue    # 状态机 UI + 分派 renderer
    ├── preview-strategy.ts          # getArtifactPreviewStrategy
    ├── use-artifact-preview-loader.ts
    └── renderers/
        ├── html-preview.vue
        ├── markdown-preview.vue
        ├── txt-preview.vue
        └── url-iframe-preview.vue
```

## API

### Props

| 属性名    | 类型                | 必填 | 说明                                   |
| --------- | ------------------- | ---- | -------------------------------------- |
| activeId  | `string`            | ✓    | 当前命中的文件 `outputId`              |
| artifacts | `SessionArtifact[]` | ✓    | 当前会话全部文件产物（已按 `outputId` 去重） |

### Events

| 事件名 | 参数              | 说明                       |
| ------ | ----------------- | -------------------------- |
| select | `(id: string)`    | 列表内切换选中文件，参数为文件 `outputId` |

### Slots / Expose

无。

## 类型定义

```typescript
import type { AIFileInfo, SessionArtifact } from '@blueking/chat-x';

// 会话级文件产物：拍平去重后即为 AIFileInfo
type SessionArtifact = AIFileInfo;

type AIFileInfo = {
  name: string;
  outputId: string;
  size: number;
  type: AIFileType;
};
```

## 关联 Composable

预览**命中与取链**由 [useArtifactPreview](/composables/use-artifact-preview) 提供（Provider / Consumer + `ARTIFACT_PREVIEW_TOKEN`）。**正文加载与渲染**由内部 `useArtifactPreviewLoader` + `ArtifactPreviewHost` 完成，不在该 composable 内。

## 关联组件

- [AssistantMessage](/components/message/assistant-message) — 文件产物来源（`property.artifacts`）
- [ChatContainer](/components/setup/chat-container) — 侧栏「文件产物」Tab 挂载场景，提供 `onArtifactClick`
- [MessageLoading](/components/helper/message-loading) — Host 预览区异步加载态
- [ExecutionSummary](/components/agent/execution-summary) — 同为侧栏 Tab 面板
