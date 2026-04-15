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
import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';

import { getComponentDoc, getComponentDocSchema } from './tools/get-component-doc.js';
import { listComponents, listComponentsSchema } from './tools/list-components.js';
import { searchDocs, searchDocsSchema } from './tools/search-docs.js';

export function createServer(): McpServer {
  const server = new McpServer({
    name: 'chat-x',
    version: '0.1.0',
  });

  server.tool(
    'list_components',
    '列出 @blueking/chat-x 文档索引中的全部条目：原子/分子组件、composables、指令、插件、类型、工具、edix、i18n、图标、主题等；支持按文档分类与组件功能域筛选，并返回 aiSummary',
    listComponentsSchema,
    async args => listComponents(args),
  );

  server.tool(
    'get_component_doc',
    '按 slug 获取对应 Wiki 文档全文（含 AI 摘要区块与清洗后的正文）；覆盖组件、composable、指令、插件、类型等所有已编入索引的条目',
    getComponentDocSchema,
    async args => getComponentDoc(args),
  );

  server.tool(
    'search_docs',
    '在 @blueking/chat-x 已生成文档中全文检索（含名称、描述、aiSummary、关联组件 relation、正文），返回匹配条目与上下文片段',
    searchDocsSchema,
    async args => searchDocs(args),
  );

  return server;
}
