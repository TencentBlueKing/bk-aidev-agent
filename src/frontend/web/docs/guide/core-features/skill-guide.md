# Skill 指引：借助 Vibe Coding 快速接入 AI 小鲸

<script setup>
import { getRuntimeGlobal } from '../../.vitepress/theme/utils/runtime-globals'

const aidevUrl = getRuntimeGlobal('BK_AIDEV_URL')
</script>

除了阅读本文档站手动集成，你还可以通过 AIDev **Skill 市场** 获取 `ai-blueking-guide` Skill，在 AI IDE 中以 **Vibe Coding** 的方式完成 AI 小鲸组件的接入——让 AI 帮你写集成代码，**Skill 的内容等同于本文档站**。

## 什么是 Skill？

Skill 是 AIDev 平台提供的可复用知识包，包含特定领域的最佳实践、代码模板和指导说明。将 Skill 下载到 AI IDE 后，AI 助手便能基于 Skill 中的知识来理解你的需求，并生成高质量的集成代码。

`ai-blueking-guide` Skill 内置了 AI 小鲸组件的完整开发指南，涵盖 ChatBot / AIBlueking 组件的使用方式、各集成模式的代码模板、API 参考以及常见场景的最佳实践。

## 获取 Skill

### 1. 前往 AIDev 主站

<a v-if="aidevUrl" :href="aidevUrl" target="_blank">前往 AIDev 平台主站</a>
<span v-else>请联系平台管理员获取 AIDev 主站地址。</span>

### 2. 在 Skill 市场搜索

进入 **服务市场** → **Skill 市场**，在右上角的搜索框中输入英文名 `ai-blueking-guide` 进行搜索，如图所示：

![Skill 市场搜索 ai-blueking-guide](/images/guide/ai-blueking-skill.png)

- **① 英文名**：在搜索框输入 `ai-blueking-guide` 搜索
- **② 下载**：找到「小鲸开发指南」Skill 后，点击 **下载** 按钮

### 3. 在 AI IDE 中使用

下载 Skill 后，在支持 Skill 的 AI IDE 中即可使用。AI 助手将自动加载 Skill 中的知识，你只需用自然语言描述需求，例如：

> "帮我在当前项目中接入 AI 小鲸浮窗组件，使用 Vue 3"

> "我需要一个嵌入式的 ChatBot 聊天面板，支持快捷指令和会话管理"

> "参考 ai-blueking-guide 给我生成一个完整的 AI 助手页面"

AI 助手会根据 Skill 中的指南，结合你的项目上下文，自动生成符合最佳实践的集成代码。

## Vibe Coding 工作流

借助 Skill 的 Vibe Coding 工作流如下：

1. **描述需求** — 用自然语言告诉 AI 你想要的集成效果
2. **AI 生成代码** — AI 根据 Skill 知识生成组件代码、样式引入、配置等
3. **预览与调整** — 在本地运行查看效果，继续与 AI 对话微调
4. **完成集成** — 确认效果后提交代码，完成接入

::: tip 推荐搭配
建议先浏览本文档的 [快速开始](/guide/quick-start) 了解基本概念，再结合 Skill 进行 Vibe Coding，效果更佳。
:::
