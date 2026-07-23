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
  type IModelOption,
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

// 模型图标示例：图标为图片地址（string），贴合后端返回的 icon 字段
const DEEPSEEK_ICON =
  "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'%3E%3Ccircle cx='8' cy='8' r='7' fill='%234a6cf7'/%3E%3C/svg%3E";

// 生成贴合后端结构的模型 mock，补齐公共字段，聚焦 property（能力标签由其派生）与 description
const createMockModel = (id: number, llmName: string, extra: Partial<IModelOption> = {}): IModelOption => ({
  id,
  llm_code: llmName,
  llm_name: llmName,
  llm_type: 'chat.completion',
  max_token_size: 4096,
  space_auth_mode: 'PUBLIC',
  user_auth_mode: 'PUBLIC',
  base_model: 'hunyuan',
  icon: DEEPSEEK_ICON,
  tag_names: [],
  property: {},
  ...extra,
});

// 模型选择器 mock 数据：property 派生能力标签（图生文/深度思考/快速思考），description 作为选项 hover 提示
export const MOCK_MODELS: IModelOption[] = [
  createMockModel(1, 'hunyuan-turbos', {
    description: '混元 turbos 模型，支持视觉理解与深度思考',
    property: { max_model_len: 32000, support_thinking: true, support_vision: true },
  }),
  createMockModel(2, 'Hy3 hunyuan', {
    description: '混元 Hy3 模型，支持视觉理解与快速思考',
    property: { max_model_len: 32000, support_thinking_quick: true, support_vision: true },
  }),
  createMockModel(3, 'Deepseek - R1', {
    base_model: 'deepseek',
    description: 'DeepSeek R1 推理模型，支持深度思考',
    property: { max_model_len: 64000, support_thinking: true },
  }),
  createMockModel(4, 'Deepseek - V3', {
    base_model: 'deepseek',
    description: 'DeepSeek V3 通用模型，支持快速思考',
    property: { max_model_len: 64000, support_thinking_quick: true },
  }),
  createMockModel(5, 'GPT-4o', {
    base_model: 'openai',
    description: 'GPT-4o 通用对话模型',
  }),
  createMockModel(6, 'Legacy Model（已停用）', {
    disabled: true,
  }),
];

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

// AI 生成的文件产物（流式阶段仅含元信息；download_url / preview_url 由 onArtifactClick 异步返回）
export const MOCK_FILE_ARTIFACTS: AIFileInfo[] = [
  {
    name: '项目立项书.pdf',
    outputId: 'artifact-pdf',
    size: 245_760,
    type: AIFileType.Pdf,
  },
  {
    name: '系统配置系统配置系统配置系统配置系统配置系统配置系统配置系统配置.md',
    outputId: 'artifact-markdown',
    size: 4_096,
    type: AIFileType.Markdown,
  },
  {
    name: 'demo.json',
    outputId: 'artifact-json',
    size: 1_280,
    type: AIFileType.Json,
  },
  {
    name: '自然风光.jpg',
    outputId: 'artifact-jpg',
    size: 1_048_576,
    type: AIFileType.Jpg,
  },
  {
    name: 'dashboard_preview.html',
    outputId: 'artifact-html',
    size: 8_192,
    type: AIFileType.Html,
  },
  {
    name: '会议纪要草稿.txt',
    outputId: 'artifact-txt',
    size: 2_048,
    type: AIFileType.Txt,
  },
];

/** playground 模拟 onArtifactClick：按 outputId 异步返回 download_url / preview_url */
export const MOCK_ARTIFACT_URL_MAP: Record<string, { download_url: string; preview_url: string }> = {
  'artifact-pdf': {
    download_url: 'https://example.com/download/project.pdf',
    preview_url: 'https://mozilla.github.io/pdf.js/web/compressed.tracemonkey-pldi-09.pdf',
  },
  'artifact-markdown': {
    download_url: 'https://example.com/download/config.md',
    preview_url: 'https://mozilla.github.io/pdf.js/web/compressed.tracemonkey-pldi-09.pdf',
  },
  'artifact-json': {
    download_url: 'https://example.com/download/demo.json',
    preview_url: 'https://mozilla.github.io/pdf.js/web/compressed.tracemonkey-pldi-09.pdf',
  },
  'artifact-jpg': {
    download_url: 'https://example.com/download/scenery.jpg',
    preview_url: 'https://mozilla.github.io/pdf.js/web/compressed.tracemonkey-pldi-09.pdf',
  },
  'artifact-html': {
    download_url: 'data:text/html,<h1>dashboard preview</h1><p>mock html artifact</p>',
    preview_url: 'https://example.com/preview/dashboard.html',
  },
  'artifact-txt': {
    download_url: 'https://example.com/download/meeting.txt',
    preview_url: 'https://mozilla.github.io/pdf.js/web/compressed.tracemonkey-pldi-09.pdf',
  },
};

export const mockArtifactClick = async (file: AIFileInfo) => {
  await new Promise(resolve => setTimeout(resolve, 1400));
  return MOCK_ARTIFACT_URL_MAP[file.outputId] ?? {};
};

// 带文件产物的会话消息，用于 playground 调试 artifacts 展示
export const MOCK_ARTIFACTS_MESSAGES = [
  {
    id: 'mock-artifacts-user',
    role: MessageRole.User,
    content: '帮我把监控方案的相关文件生成出来',
    name: 'user',
    status: MessageStatus.Complete,
    messageId: 'mock-artifacts-user',
  },
  {
    id: 'mock-artifacts-assistant',
    role: MessageRole.Assistant,
    content: '收到，我已经为你设计好，请查阅',
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
