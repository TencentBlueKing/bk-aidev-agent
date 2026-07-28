/* eslint-disable @typescript-eslint/consistent-type-assertions */
/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台 (BlueKing PaaS):
 *
 * ---------------------------------------------------
 * Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
 * documentation files (the "Software"), to deal in the Software without restriction, including without limitation
 * the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and
 * to permit persons to whom the Software is furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all copies or substantial portions of
 * the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
 * THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
 * CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
 * IN THE SOFTWARE.
 */

import {
  // type AssistantMessage,
  type AIFileInfo,
  type IAiSlashMenuItem,
  // type InfoMessage,
  type Message,
  type Shortcut,
  type UserMessage,
  AIBluekingIcon,
  AIFileType,
  APPROVAL_STATUS,
  // CopyIcon,
  DeleteIcon,
  InterruptReason,
  MessageRole,
  MessageStatus,
  ShareIcon,
  t,
} from '../src';

export const MOCK_SHORTCUTS = [
  {
    id: 'ai-chat',
    name: t('问问小鲸'),
    icon: () => AIBluekingIcon,
    components: [
      {
        id: 'ai-chat-input',
        type: 'input',
        formItemProps: { label: '提示词' },
        props: {
          placeholder: '请输入提示词',
          onChange: (value: string) => {
            console.log('Input changed:', value);
          },
        },
      },
      {
        id: 'ai-chat-select',
        type: 'select',
        formItemProps: { label: '模型' },
        props: {
          options: [
            { label: '模型1', value: 'model1' },
            { label: '模型2', value: 'model2' },
            { label: '模型3', value: 'model3' },
          ],
        },
      },
    ],
  },
  {
    id: 'ai-copy',
    name: t('复制'),
    icon: 'https://example.com/icons/agent_command/default.png',
  },
  {
    id: 'ai-share',
    name: t('分享'),
    icon: () => ShareIcon,
  },
  {
    id: 'ai-translate',
    name: '翻译',
  },
  {
    id: 'ai-delete',
    name: t('删除'),
    icon: () => DeleteIcon,
  },
  {
    id: 'ai-quote',
    name: t('引用'),
  },
  {
    id: 'ai-like',
    name: '点赞',
  },
  {
    id: 'ai-unlike',
    name: '不满意',
  },
] as Shortcut[];

// ---------------------------------------------------------------------------
// 文件产物 Mock（元信息 + 正文；download_url / preview_url 由 onArtifactClick 异步返回）
// txt / markdown / html：Blob URL，供前端 fetch 后原生渲染
// pdf / jpg：仍走 preview_url iframe（后台转 pdf 的模拟）
// ---------------------------------------------------------------------------

/** txt：纯文本预览正文 */
export const MOCK_ARTIFACT_TXT_CONTENT = `蓝鲸可观测平台 · 周例会纪要（草稿）
时间：2026-07-21 14:00–15:30
地点：线上会议（腾讯会议）
主持人：张明 | 记录人：李华

一、上周回顾
1. 告警收敛规则已上线，P1 告警量下降约 35%。
2. 日志查询慢查询优化：冷热分层已完成灰度，平均查询耗时从 8.2s 降至 2.6s。
3. Agent 侧文件产物预览联调阻塞项：markdown / txt 需前端直渲染，不再依赖 preview_url。

二、本周计划
1. 完成文件产物侧栏预览（html / txt / markdown）验收。
2. 推进「监控大盘 HTML 报告」导出模板评审。
3. 补齐 JSON 配置产物的 schema 校验与下载埋点。

三、风险与依赖
- PDF 转码服务高峰期偶发超时，需确认 SLA（负责人：王强，本周五前给结论）。
- 设计稿标注与主题变量对齐仍有 3 处待确认。

四、待办
[ ] 前端：txt / markdown 预览联调 — 李华 / 07-28
[ ] 后端：download_url 鉴权时效文档 — 赵磊 / 07-29
[ ] 产品：导出报告字段清单 — 陈静 / 07-30

备注：本稿仅供内部同步，正式纪要将在会后 24h 内发布到 iWiki。
`;

/** markdown：MarkdownContent 预览正文 */
export const MOCK_ARTIFACT_MARKDOWN_CONTENT = `# 蓝鲸可观测 · 系统配置说明

> 适用版本：chat-x ≥ 0.0.47｜更新：2026-07-28

## 1. 概述

本文档描述 Agent 产出**文件产物**时，前端侧栏预览与下载的配置约定。流式阶段消息仅携带文件元信息；真实链接通过 \`onArtifactClick\` 异步获取。

## 2. 预览策略

| 文件类型 | 加载方式 | 渲染 |
| --- | --- | --- |
| \`html\` | \`download_url\` → fetch | iframe \`srcdoc\` |
| \`txt\` | \`download_url\` → fetch | 浏览器纯文本（\`pre\`） |
| \`markdown\` | \`download_url\` → fetch | 项目 \`MarkdownContent\` |
| \`json\` | \`download_url\` → fetch | 纯文本（同 txt） |
| \`pdf\` / \`jpg\` | \`preview_url\` | iframe（后台转 PDF） |

## 3. 接入示例

\`\`\`ts
const onArtifactClick = async (file: AIFileInfo) => {
  const res = await api.getArtifactUrls(file.outputId);
  return {
    download_url: res.download_url,
    preview_url: res.preview_url,
  };
};
\`\`\`

## 4. 注意事项

1. **鉴权**：\`download_url\` / \`preview_url\` 建议带短时效签名，避免直链泄露。
2. **竞态**：侧栏切换文件时需中断上一次 fetch，防止旧内容覆盖。
3. **安全**：HTML 预览使用 \`srcdoc\`，勿将不可信脚本注入到宿主页面。

## 5. 检查清单

- [x] Pdf 预览可用
- [x] Html 直渲染
- [ ] Txt / Markdown 直渲染验收
- [ ] 下载埋点与失败重试

---

如有疑问请联系 **可观测前端小组**。
`;

/** html：iframe srcdoc 预览正文 */
export const MOCK_ARTIFACT_HTML_CONTENT = `<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <title>监控大盘周报</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; margin: 24px; color: #1d2126; }
    h1 { font-size: 20px; margin: 0 0 8px; }
    .meta { color: #979ba5; font-size: 12px; margin-bottom: 20px; }
    .cards { display: flex; gap: 12px; flex-wrap: wrap; }
    .card { flex: 1; min-width: 140px; padding: 16px; background: #f5f7fa; border-radius: 8px; }
    .card strong { display: block; font-size: 24px; color: #3a84ff; margin-top: 8px; }
    table { width: 100%; border-collapse: collapse; margin-top: 20px; font-size: 13px; }
    th, td { border: 1px solid #dcdee5; padding: 8px 10px; text-align: left; }
    th { background: #f0f1f5; }
  </style>
</head>
<body>
  <h1>业务监控大盘 · 周报预览</h1>
  <p class="meta">统计周期：2026-07-14 ~ 2026-07-20｜生成时间：2026-07-21 09:12</p>
  <div class="cards">
    <div class="card">P1 告警<strong>42</strong></div>
    <div class="card">平均恢复时长<strong>18 min</strong></div>
    <div class="card">可用性<strong>99.95%</strong></div>
  </div>
  <table>
    <thead><tr><th>服务</th><th>错误率</th><th>P99 延迟</th><th>状态</th></tr></thead>
    <tbody>
      <tr><td>aidev-agent</td><td>0.12%</td><td>320ms</td><td>正常</td></tr>
      <tr><td>chat-gateway</td><td>0.08%</td><td>180ms</td><td>正常</td></tr>
      <tr><td>artifact-preview</td><td>1.40%</td><td>1.2s</td><td>关注</td></tr>
    </tbody>
  </table>
</body>
</html>`;

/** json：配置样例正文（与 txt 相同，fetch 后纯文本预览） */
export const MOCK_ARTIFACT_JSON_CONTENT = `{
  "service": "bk-observe-agent",
  "env": "prod",
  "alert": {
    "p1_threshold": 5,
    "mute_window_min": 30,
    "channels": ["wecom", "email"]
  },
  "dashboard": {
    "refresh_sec": 60,
    "panels": ["error_rate", "latency_p99", "saturation"]
  }
}
`;

export const MOCK_FILE_ARTIFACTS: AIFileInfo[] = [
  {
    name: '可观测平台立项说明书.pdf',
    outputId: 'artifact-pdf',
    size: 245_760,
    type: AIFileType.Pdf,
  },
  {
    name: '文件产物预览-系统配置说明.md',
    outputId: 'artifact-markdown',
    size: MOCK_ARTIFACT_MARKDOWN_CONTENT.length,
    type: AIFileType.Markdown,
  },
  {
    name: '告警策略配置.json',
    outputId: 'artifact-json',
    size: MOCK_ARTIFACT_JSON_CONTENT.length,
    type: AIFileType.Json,
  },
  {
    name: '机房巡检现场照片.jpg',
    outputId: 'artifact-jpg',
    size: 1_048_576,
    type: AIFileType.Jpg,
  },
  {
    name: '监控大盘周报.html',
    outputId: 'artifact-html',
    size: MOCK_ARTIFACT_HTML_CONTENT.length,
    type: AIFileType.Html,
  },
  {
    name: '周例会纪要-0721.txt',
    outputId: 'artifact-txt',
    size: MOCK_ARTIFACT_TXT_CONTENT.length,
    type: AIFileType.Txt,
  },
];

type MockArtifactUrl = {
  download_url?: string;
  preview_url?: string;
};

/** 仅 iframe 类型需要的静态 preview_url；文本类 download_url 运行时用 Blob 生成 */
const MOCK_ARTIFACT_STATIC_URL: Record<string, MockArtifactUrl> = {
  'artifact-pdf': {
    download_url: 'https://example.com/download/observe-project.pdf',
    preview_url: 'https://mozilla.github.io/pdf.js/web/compressed.tracemonkey-pldi-09.pdf',
  },
  'artifact-json': {},
  'artifact-jpg': {
    download_url: 'https://picsum.photos/seed/bk-observe/1200/800.jpg',
    preview_url: 'https://mozilla.github.io/pdf.js/web/compressed.tracemonkey-pldi-09.pdf',
  },
  'artifact-markdown': {},
  'artifact-html': {},
  'artifact-txt': {},
};

const MOCK_TEXT_ARTIFACT_BODY: Record<string, { body: string; mime: string }> = {
  'artifact-html': { body: MOCK_ARTIFACT_HTML_CONTENT, mime: 'text/html' },
  'artifact-json': { body: MOCK_ARTIFACT_JSON_CONTENT, mime: 'application/json' },
  'artifact-markdown': { body: MOCK_ARTIFACT_MARKDOWN_CONTENT, mime: 'text/markdown' },
  'artifact-txt': { body: MOCK_ARTIFACT_TXT_CONTENT, mime: 'text/plain' },
};

/** 缓存 Blob URL，避免重复 createObjectURL */
const mockArtifactBlobUrlCache = new Map<string, string>();

const getMockTextDownloadUrl = (outputId: string) => {
  const cached = mockArtifactBlobUrlCache.get(outputId);
  if (cached) {
    return cached;
  }
  const item = MOCK_TEXT_ARTIFACT_BODY[outputId];
  if (!item) {
    return undefined;
  }
  const url = URL.createObjectURL(new Blob([item.body], { type: `${item.mime};charset=utf-8` }));
  mockArtifactBlobUrlCache.set(outputId, url);
  return url;
};

/** 兼容旧导出名：静态映射 + 文本类占位（真实 download_url 见 mockArtifactClick） */
export const MOCK_ARTIFACT_URL_MAP: Record<string, MockArtifactUrl> = MOCK_ARTIFACT_STATIC_URL;

export const mockArtifactClick = async (file: AIFileInfo): Promise<MockArtifactUrl> => {
  await new Promise(resolve => setTimeout(resolve, 600));
  const staticUrls = MOCK_ARTIFACT_STATIC_URL[file.outputId] ?? {};
  const textDownloadUrl = getMockTextDownloadUrl(file.outputId);
  return {
    ...staticUrls,
    ...(textDownloadUrl ? { download_url: textDownloadUrl } : {}),
  };
};

// 带文件产物的会话消息，用于 playground 调试 artifacts 展示
export const MOCK_ARTIFACTS_MESSAGES = [
  {
    id: 'mock-artifacts-user',
    role: MessageRole.User,
    content: '帮我把本周监控方案相关的产出文件都整理出来，方便评审。',
    name: 'user',
    status: MessageStatus.Complete,
    messageId: 'mock-artifacts-user',
  },
  {
    id: 'mock-artifacts-assistant',
    role: MessageRole.Assistant,
    content:
      '已为你生成一组评审材料：立项 PDF、配置说明 Markdown、告警 JSON、巡检照片、大盘周报 HTML，以及周例会纪要 TXT。可点击卡片在侧栏预览或下载。',
    name: 'react_agent',
    status: MessageStatus.Complete,
    messageId: 'mock-artifacts-assistant',
    property: {
      artifacts: MOCK_FILE_ARTIFACTS,
    },
  },
] as Message[];

export const MOCK_USER_MESSAGE = {
  id: '1',
  role: MessageRole.User,
  content:
    'Hello, how are you?Hello, how are you?Hello, how are you?Hello, how are you?Hello, how are you?Hello, how are you?Hello, how are you?Hello, how are you?Hello, how are you?Hello, how are you?Hello, how are you?Hello, how are you?Hello, how are you?Hello, how are you?Hello, how are you?',
  messageId: '1',
  status: MessageStatus.Complete,
} as UserMessage;

// @ 资源列表
export const MOCK_RESOURCES = [
  {
    type: 'tool',
    name: '工具1撒旦法收到了客服',
    id: 'tool1',
    icon: 'icon-tool1',
  },
  {
    type: 'shortcut',
    name: '快捷1撒旦法收到',
    id: 'shortcut1',
    icon: 'icon-shortcut1',
  },
  {
    type: 'doc',
    name: '文档1',
    id: 'doc1',
    icon: 'icon-doc1',
  },
  {
    type: 'mcp',
    name: 'MCP1',
    id: 'mcp1',
    icon: 'icon-mcp1',
  },
  {
    type: 'tool',
    name: '工具2',
    id: 'tool2',
    icon: 'icon-tool2',
  },

  {
    type: 'shortcut',
    name: '快捷2',
    id: 'shortcut2',
    icon: 'icon-shortcut2',
  },

  {
    type: 'doc',
    name: '文档2',
    id: 'doc2',
    icon: 'icon-doc2',
  },
] as IAiSlashMenuItem[];
// @ 提示词列表
export const MOCK_PROMPTS = ['你好', '你好啊', '你好啊', '你好啊', '你好啊', '你好啊', '你好啊', '你好啊', '你好啊'];

export const MOCK_MARKDOWN_CONTENT = `
---
__Advertisement :)__

- __[pica](https://nodeca.github.io/pica/demo/)__ - high quality and fast image
  resize in browser.
- __[babelfish](https://github.com/nodeca/babelfish/)__ - developer friendly
  i18n with plurals support and easy syntax.

You will like those projects!

---

# h1 Heading 8-)
## h2 Heading
### h3 Heading
#### h4 Heading
##### h5 Heading
###### h6 Heading


## Horizontal Rules

___

---

***


## Typographic replacements

Enable typographer option to see result.

(c) (C) (r) (R) (tm) (TM) (p) (P) +-

test.. test... test..... test?..... test!....

!!!!!! ???? ,,  -- ---

"Smartypants, double quotes" and 'single quotes'


## Emphasis

**This is bold text**

__This is bold text__

*This is italic text*

_This is italic text_

~~Strikethrough~~


## Blockquotes


> Blockquotes can also be nested...
>> ...by using additional greater-than signs right next to each other...
> > > ...or with spaces between arrows.


## Lists

Unordered

+ Create a list by starting a line with \`+\`, \`-\`, or \`*\`
+ Sub-lists are made by indenting 2 spaces:
  - Marker character change forces new list start:
    * Ac tristique libero volutpat at
    + Facilisis in pretium nisl aliquet
    - Nulla volutpat aliquam velit
+ Very easy!

Ordered

1. Lorem ipsum dolor sit amet
2. Consectetur adipiscing elit
3. Integer molestie lorem at massa


1. You can use sequential numbers...
1. ...or keep all the numbers as \`1.\`

Start numbering with offset:

57. foo
1. bar


## Code

Inline \`code\`

Indented code

    // Some comments
    line 1 of code
    line 2 of code
    line 3 of code


Block code "fences"

\`\`\`
Sample text here...
\`\`\`

Syntax highlighting

\`\`\` js
var foo = function (bar) {
  return bar++;
};

console.log(foo(5));
\`\`\`

## Tables

| Option | Description |
| ------ | ----------- |
| data   | path to data files to supply the data that will be passed into templates. |
| engine | engine to be used for processing templates. Handlebars is the default. |
| ext    | extension to be used for dest files. |

Right aligned columns

| Option | Description |
| ------:| -----------:|
| data   | path to data files to supply the data that will be passed into templates. |
| engine | engine to be used for processing templates. Handlebars is the default. |
| ext    | extension to be used for dest files. |


## Links

[link text](http://dev.nodeca.com)

[link with title](http://nodeca.github.io/pica/demo/ "title text!")

Autoconverted link https://github.com/nodeca/pica (enable linkify to see)


## Images

![Minion](https://octodex.github.com/images/minion.png)
![Stormtroopocat](https://octodex.github.com/images/stormtroopocat.jpg "The Stormtroopocat")

Like links, Images also have a footnote style syntax

![Alt text][id]

With a reference later in the document defining the URL location:

[id]: https://octodex.github.com/images/dojocat.jpg  "The Dojocat"


## Plugins

The killer feature of \`markdown-it\` is very effective support of
[syntax plugins](https://www.npmjs.org/browse/keyword/markdown-it-plugin).


### [Emojies](https://github.com/markdown-it/markdown-it-emoji)

> Classic markup: :wink: :cry: :laughing: :yum:
>
> Shortcuts (emoticons): :-) :-( 8-) ;)

see [how to change output](https://github.com/markdown-it/markdown-it-emoji#change-output) with twemoji.


### [Subscript](https://github.com/markdown-it/markdown-it-sub) / [Superscript](https://github.com/markdown-it/markdown-it-sup)

- 19^th^
- H~2~O


### [<ins>](https://github.com/markdown-it/markdown-it-ins)

++Inserted text++


### [<mark>](https://github.com/markdown-it/markdown-it-mark)

==Marked text==


### [Footnotes](https://github.com/markdown-it/markdown-it-footnote)

Footnote 1 link[^first].

Footnote 2 link[^second].

Inline footnote^[Text of inline footnote] definition.

Duplicated footnote reference[^second].

[^first]: Footnote **can have markup**

    and multiple paragraphs.

[^second]: Footnote text.


### [Definition lists](https://github.com/markdown-it/markdown-it-deflist)

Term 1

:   Definition 1
with lazy continuation.

Term 2 with *inline markup*

:   Definition 2

        { some code, part of Definition 2 }

    Third paragraph of definition 2.

_Compact style:_

Term 1
  ~ Definition 1

Term 2
  ~ Definition 2a
  ~ Definition 2b


### [Abbreviations](https://github.com/markdown-it/markdown-it-abbr)

This is HTML abbreviation example.

It converts "HTML", but keep intact partial entries like "xxxHTMLyyy" and so on.

*[HTML]: Hyper Text Markup Language

### [Custom containers](https://github.com/markdown-it/markdown-it-container)

::: warning
*here be dragons*
:::
              `;

export const MOCK_MESSAGES = [
  {
    id: 'cbba21f14f7847d98ff3240e69ef5c07',
    role: 'user',
    content: '检查一下 itsm 工单1234的状态',
    name: 'user',
    status: 'completed',
    messageId: 'cbba21f14f7847d98ff3240e69ef5c07',
  },
  // {
  //   id: 'cbba21f14f7847d98ff3240e69ef5c07',
  //   role: 'custom',
  //   content: {
  //     content: '这是自定义内容',
  //     id: 'cbba21f14f7847d98ff3240e69ef5c07',
  //     name: 'custom',
  //     slot: 'custom-slot',
  //   },
  //   name: 'custom',
  //   status: 'completed',
  //   messageId: 'cbba21f14f7847d98ff3240e69ef5c07',
  // },
  {
    status: 'completed',
    id: 'lc_run--019b7205-65ad-7c70-b504-ca80d8cd0efa',
    role: 'reasoning',
    content: [
      '用户想要检查ITSM工单1234的状态。我需要调用check_itsm_ticket_v2工具，并将ticket_num参数设为"1234"。现在就开始执行。',
    ],
    messageId: 'lc_run--019b7205-65ad-7c70-b504-ca80d8cd0efa',
  },
  {
    id: 'lc_run--019b7205-65ad-7c70-b504-ca80d8cd0efa',
    role: 'assistant',
    content: '\n\n',
    name: 'react_agent',
    toolCalls: [
      {
        id: 'call_8e651617efb44152af988a5c',
        type: 'function',
        function: {
          name: 'check_itsm_ticket_v2',
          arguments: '{"ticket_num": "1234"}',
        },
      },
    ],
    status: 'completed',
    messageId: 'lc_run--019b7205-65ad-7c70-b504-ca80d8cd0efa',
  },
  {
    id: '6287d811-590f-4c96-bc8f-36a5cf6cd558',
    role: 'activity',
    activityType: 'chat',
    content: [{ name: '', url: '' }],
    status: 'completed',
    messageId: '6287d811-590f-4c96-bc8f-36a5cf6cd558',
  },
  {
    id: 'e737ddd2-d13a-4a6d-8650-2490163c607b',
    role: 'tool',
    content:
      '{"id": "1234", "title": "\\u5de5\\u53551234", "description": "\\u6d4b\\u8bd5\\u5de5\\u5355\\u4e00\\u4e8c\\u4e09", "status": "open"}',
    toolCallId: 'call_8e651617efb44152af988a5c',
    status: 'completed',
    messageId: 'e737ddd2-d13a-4a6d-8650-2490163c607b',
  },
  {
    status: 'completed',
    id: 'lc_run--019b7205-6bb3-79a0-81ec-48e5fcb8fea0',
    role: 'reasoning',
    content: [
      '根据查询结果，ITSM工单1234的状态是：**open（开启）**。\n\n工单详情：\n- 工单号：1234\n- 标题：工单1234\n- 描述：测试工单一二三\n- 状态：open',
    ],
    messageId: 'lc_run--019b7205-6bb3-79a0-81ec-48e5fcb8fea0',
  },
  {
    id: 'lc_run--019b7205-6bb3-79a0-81ec-48e5fcb8fea0',
    role: 'assistant',
    content: '',
    name: 'react_agent',
    status: 'completed',
    messageId: 'lc_run--019b7205-6bb3-79a0-81ec-48e5fcb8fea0',
  },
  {
    id: 'mock-revoked-approval-user',
    role: MessageRole.User,
    content: '查看一下已经撤销的算法方案评审单',
    name: 'user',
    status: MessageStatus.Complete,
    messageId: 'mock-revoked-approval-user',
  },
  {
    id: 'mock-revoked-approval-assistant',
    role: MessageRole.Assistant,
    content: '该第三方审批单据已撤销，当前无需继续审批：',
    name: 'react_agent',
    status: MessageStatus.Complete,
    messageId: 'mock-revoked-approval-assistant',
  },
  {
    id: 'mock-revoked-approval-interrupt',
    role: MessageRole.Interrupt,
    content: {
      message: '',
      outcome: {
        type: 'interrupt',
        interrupts: [
          {
            id: 'mock-revoked-approval-interrupt-item',
            reason: InterruptReason.AIDevToolApproval,
            toolCallId: 'mock-revoked-approval-tool-call',
            metadata: {
              ticket: {
                approvers: [],
                sn: 'REV-2026-04-24-002',
                status: APPROVAL_STATUS.REVOKED,
                submit_time: '2026-04-24 14:30:15',
                title: '算法方案评审单',
                url: 'https://example.com/ticket/REV-2026-04-24-002',
              },
            },
          },
        ],
      },
    },
    status: MessageStatus.Complete,
    messageId: 'mock-revoked-approval-interrupt',
  },
];
