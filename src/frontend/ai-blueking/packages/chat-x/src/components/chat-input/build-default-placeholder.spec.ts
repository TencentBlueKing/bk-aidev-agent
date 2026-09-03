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

import { describe, expect, it } from 'vitest';

import { buildDefaultPlaceholder } from './build-default-placeholder';

describe('buildDefaultPlaceholder', () => {
  it('三种能力都有时按设计稿顺序拼接完整中文提示', () => {
    expect(
      buildDefaultPlaceholder({
        isEn: false,
        hasSlashMenu: true,
        hasPromptMenu: true,
        hasAtMenu: true,
      }),
    ).toBe(`输入 "/" 唤出 Skill，工具，MCP
输入 "@" 唤出会话产物，知识库
输入 "\\" 唤出 Prompt
通过 Shift + Enter 进行换行输入`);
  });

  it('仅有 / 菜单时只保留对应行和换行提示', () => {
    expect(
      buildDefaultPlaceholder({
        isEn: false,
        hasSlashMenu: true,
        hasPromptMenu: false,
        hasAtMenu: false,
      }),
    ).toBe(`输入 "/" 唤出 Skill，工具，MCP
通过 Shift + Enter 进行换行输入`);
  });

  it('三种能力都没有时只保留换行提示', () => {
    expect(
      buildDefaultPlaceholder({
        isEn: false,
        hasSlashMenu: false,
        hasPromptMenu: false,
        hasAtMenu: false,
      }),
    ).toBe('通过 Shift + Enter 进行换行输入');
  });

  it('仅有 @ 菜单时只保留对应行和换行提示', () => {
    expect(
      buildDefaultPlaceholder({
        isEn: false,
        hasSlashMenu: false,
        hasPromptMenu: false,
        hasAtMenu: true,
      }),
    ).toBe(`输入 "@" 唤出会话产物，知识库
通过 Shift + Enter 进行换行输入`);
  });

  it('仅有 Prompt 菜单时只保留对应行和换行提示', () => {
    expect(
      buildDefaultPlaceholder({
        isEn: false,
        hasSlashMenu: false,
        hasPromptMenu: true,
        hasAtMenu: false,
      }),
    ).toBe(`输入 "\\" 唤出 Prompt
通过 Shift + Enter 进行换行输入`);
  });

  it('三种能力都有时拼接完整英文提示', () => {
    expect(
      buildDefaultPlaceholder({
        isEn: true,
        hasSlashMenu: true,
        hasPromptMenu: true,
        hasAtMenu: true,
      }),
    ).toBe(`Input "/" to trigger Skill, tool and MCP
Input "@" to trigger conversation files and knowledge base
Input "\\" to trigger prompt
Use Shift + Enter to enter a new line`);
  });

  it('英文环境下无能力时只保留换行提示', () => {
    expect(
      buildDefaultPlaceholder({
        isEn: true,
        hasSlashMenu: false,
        hasPromptMenu: false,
        hasAtMenu: false,
      }),
    ).toBe('Use Shift + Enter to enter a new line');
  });
});
