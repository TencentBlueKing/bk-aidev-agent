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

export interface BuildDefaultPlaceholderOptions {
  /** 是否有 `@` 可唤出的资源（知识库、会话产物） */
  hasAtMenu: boolean;
  /** 是否有 `\` 可唤出的 Prompt */
  hasPromptMenu: boolean;
  /** 是否有 `/` 可唤出的能力（Skill、工具、MCP） */
  hasSlashMenu: boolean;
  isEn: boolean;
}

/**
 * 设计稿标注：智能体没有对应的资源或配置时，不显示对应的提示文案。
 */
export function buildDefaultPlaceholder(options: BuildDefaultPlaceholderOptions): string {
  const { isEn, hasSlashMenu, hasPromptMenu, hasAtMenu } = options;
  const lines: string[] = [];

  if (hasSlashMenu) {
    lines.push(isEn ? 'Input "/" to trigger Skill, tool and MCP' : '输入 "/" 唤出 Skill，工具，MCP');
  }
  if (hasAtMenu) {
    lines.push(isEn ? 'Input "@" to trigger conversation files and knowledge base' : '输入 "@" 唤出会话产物，知识库');
  }
  if (hasPromptMenu) {
    lines.push(isEn ? 'Input "\\" to trigger prompt' : '输入 "\\" 唤出 Prompt');
  }
  lines.push(isEn ? 'Use Shift + Enter to enter a new line' : '通过 Shift + Enter 进行换行输入');

  return lines.join('\n');
}
