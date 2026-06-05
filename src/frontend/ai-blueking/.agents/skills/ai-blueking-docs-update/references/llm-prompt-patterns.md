# LLM / 系统提示词文档模式

适用于：模型输出格式由前端解析（自定义代码块、蓝鲸行内富文本、特定 JSON 结构等）。

## 两层层级（必须在文档中写清）

| 配置位置 | 读者 | 文档中的章节名建议 |
| --- | --- | --- |
| AIDev **系统提示词 / Agent 指令** | 平台配置者、提示词工程师 | 「配置 LLM / 系统提示词」 |
| 前端 `prompts` prop、`/` 菜单 | 集成开发者、终端用户快捷提问 | 见 [提示词与资源](/guide/core-features/prompts) |

**禁止混为一谈**：`prompts` 不能替代系统提示词里的格式约束。

## 推荐页面结构（独立指南页）

1. `::: info 版本要求` — 最低组件版本
2. **语法 / 协议** — 表格 + 简短示例
3. **与 HTML / 旧行为的关系** — 明确不支持什么
4. **配置 LLM / 系统提示词** — 编号要点 + **完整可复制** `text` 代码块（用户给的模板尽量原文保留）
5. **与前端 prompts 的区别** — 对照表
6. **相关文档** — 链到 chat-interaction、prompts、changelog

## 系统提示词模板代码块

使用 ` ```text ` 而非 `markdown`，避免 VitePress 二次渲染示例中的 `::bk::` 等标记：

````markdown
### 示例：撤离通知类内容

```text
请帮我生成【撤离通知】类内容，要求：

1. 标题使用红色加粗样式，使用蓝鲸行内富文本语法（不要用 HTML 标签）：
   ::bk{color=red; bold}标题内容:/bk::

2. 正文须包含：撤离原因、范围、时间……

3. 结束标记固定为 `:/bk::`，正文中不要出现该字面量。

4. 不要输出完整 HTML 页面结构。
```
````

## 需同步更新的关联页

| 页面 | 更新内容 |
| --- | --- |
| `guide/core-features/chat-interaction.md` | 「内容渲染」列表增加一条 + 链接 |
| `guide/core-features/prompts.md` | 一段说明系统提示词与 prompts 配合 |
| `api/chat-x/components.md` | ContentRender / Markdown 相关 props 说明 |
| `faq.md` | 一条「为什么 HTML 不生效」类问答 |
| `changelog.md` | 新功能 + 变更 + 文档链接 |

## 从实现反推文档

1. 读插件/解析器源文件顶部注释（如 `markdown-bk-inline-style.ts`）。
2. 将**白名单键、结束标记、禁止项**写入文档表。
3. 从 wikis 复制示例时可精简，但语法必须与实现一致。

## 参考实现页

主站已落地范例：

- `src/frontend/web/docs/guide/core-features/markdown-inline-style.md`

自定义组件块范例：

- `src/frontend/web/docs/guide/core-features/custom-message-rendering.md`
- Skill `ai-blueking-dev/references/custom-message-rendering.md`
