# Changelog

## Unreleased

### Breaking Changes

- 用户消息的富文本文档从 `property.extra.docSchema` 移至 `property.docSchema`，与 `extra` 同级；发送、编辑回填及编辑确认后的持久化需使用新字段位置。

- + 号「添加」分组只保留内置「文件」项；移除「图片」项、`MenuItemType` 的 `'image'`，以及导出常量 `IMAGE_UPLOAD_ACCEPT`。图片与其它允许类型都通过「文件」入口（`accept` / `DEFAULT_UPLOAD_ACCEPT`）选择。

### Added

- `ChatInput` / `ChatContainer` 新增 `deleteFile(file: Partial<UploadFile>)` 事件（模板监听 `@delete-file`）：取消输入框附件时携带 `id` 等文件信息，供业务方调用删除接口；UI 立即移除附件，不等待接口结果，成功或失败均不恢复附件。
- Playground 新增上传、删除及本地文件下载 mock，上传响应包含 `id` / `path`；补充已上传文件和无 `outputId` 的历史附件示例，支持验证引用、预览及菜单过滤行为。

### Changed

- `@` / `+` 的会话文件只收集具有 `outputId` 的条目，不再回退到 URL 或文件名；手动传入的 `artifact.id` 必须使用文件 `outputId`。
- 上传响应 `path` 映射为附件 `outputId`，上传成功后即可引用、预览；发送时保留该身份，待发送附件、用户消息附件与助手产物共用侧栏预览和下载流程。

- 单文件上传大小限制放宽为严格小于 45 MB（`45 * 1024 * 1024` 字节），文件选择、拖拽、粘贴及 `FileUploadBtn` 共用此限制，大小提示同步更新。

### Fixed

- 修复仅含 `id` 的回填附件无法取消的问题，删除时优先按文件 `id` 匹配。
- 带 `outputId` 的图片附件在缩略图失效后仍可打开产物预览；取消或发送附件后，同步清理待发送文件的菜单与预览数据。

## 0.0.52-beta.1 (2026-09-03)

输入区资源引用能力重构：`/` `@` `\` 与左下角 `+` 共用统一菜单；选中资源以 Mention 标签插入，发送后可还原、编辑可回填；会话产物支持从消息卡片 / 侧栏引用进输入框。

### Breaking Changes

- `ChatContainer` / `ChatInput` 的 `prompts`、`resources`、`skills` 合并为统一数据源 `menuSources: IInputMenuItem[]`，按 `type` 分发到不同触发方式：
  - `/` → `skill` / `mcp` / `tool`
  - `@` → `knowledgebase` / `doc` / `artifact`
  - `\` → `prompt`
  - `+` → 以上全部，并在支持上传时附带内置「文件」「图片」项
- 移除 `IAiSlashMenuItem` / `IAiSlashGroupItem` / `ISkillListItem`，改用 `IInputMenuItem`、`MenuItemType`、`MenuTrigger`
- 移除组件 `AiSlashEditor`、`AiSlashMenu`、`AiSkillList`、`AiPromptList`
- 消息工具栏默认不再提供「引用」（整段 cite）；改为按资源引用（Mention 标签）
- `onSendMessage` 第二参数为编辑器文档 `docSchema: TagSchema`，用于还原已选资源标签；`content` 仍是纯文本，不改后端契约

迁移示例：

```ts
import type { IInputMenuItem } from '@blueking/chat-x';

const menuSources = shallowRef<IInputMenuItem[]>([
  { id: 'skill-ops', name: '运维 Skill', type: 'skill' },
  { id: 'kb-ops', name: '运维知识库', type: 'knowledgebase' },
  { id: 'prompt-code', name: '写代码', type: 'prompt', content: '帮我写一段代码' },
]);
```

```vue
<ChatContainer
  :messages="messages"
  :menu-sources="menuSources"
  :on-send-message="handleSendMessage"
/>
```

### Added

- **统一资源菜单**：`InputMenuPanel` + `useInputMenu` + `useMenuTrigger`；分组默认展示 4 条，超出折叠为「更多 +N」；组内无数据时不渲染该分组
- **+ 号聚合菜单**：新增 `AddMenuBtn`，点击唤起全部资源分组；「添加」分组内置「文件」「图片」两项，共用同一套上传校验与 `onUpload`。「图片」打开系统选择器时临时使用 `IMAGE_UPLOAD_ACCEPT`
- **上传常量**：导出 `IMAGE_UPLOAD_ACCEPT`（与 `ALLOWED_UPLOAD_EXTENSIONS.image` 同源）；入队校验仍走 `accept` / `DEFAULT_UPLOAD_ACCEPT`
- **Mention 标签**：`MentionTag` / `MentionText`；选中后以「图标 + 蓝色名称」内联插入；有描述时 hover 气泡；会话产物标签可点击打开侧栏预览
- **发送还原 / 编辑回填**：用户消息 `property.extra.docSchema` 保存富文本文档；仅含 tag 时走结构化渲染，历史纯文本消息表现不变
- **会话产物引用**：消息区文件卡片、侧栏产物预览可一键把文件以标签插入输入框（只读 / 分享态隐藏入口）
- **自动收集会话产物**：`collectMessageArtifacts` 从助手 `artifacts` 与用户附件收集；业务未自行传入 `artifact` 时自动拼进 `@` 菜单
- **跨层插入**：`useInputMention` provide/inject，任意深度组件可 `insertMention`
- **用户消息折叠**：`CollapsibleContent`，正文最高 200px，超出展示「显示更多 / 收起」
- **ResourceIcon**：菜单项与标签共用类型默认图标（远程图失效回退内置图标；产物按文件后缀推导）；新增 `image` → `ImageUploadIcon`、`prompt` → `PromptIcon`
- npm 包发布 `skills/` 目录，供 Agent 消费 chat-x 组件文档

### Changed

- placeholder 按实际可用 `type` 按需展示 `/` `@` `\` 提示行，没有对应资源时不提示
- 已插入的标签不再出现在菜单中，避免重复选中
- 编辑用户消息时优先用 `docSchema` 回填，并在输入框挂载后聚焦到末尾
- `IModelOption.icon` 支持 URL 字符串或 Vue 组件
- 全屏外 tippy 默认 `appendTo: document.body`

### Removed

- 旧 slash 菜单实现及 `resourceTypeMap` 类型色板
- 默认消息工具中的 cite（复制 / 重新生成 / 分享、复制 / 编辑 / 删除 保留）
