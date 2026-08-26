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
  it('三种能力都有时拼接完整中文提示', () => {
    expect(
      buildDefaultPlaceholder({
        isEn: false,
        hasSkills: true,
        hasPrompts: true,
        hasResources: true,
      }),
    ).toBe(`输入 "/" 唤出 Skill
输入 "\\" 唤出 Prompt
输入 "@" 唤出 工具和 MCP
通过 Shift + Enter 进行换行输入`);
  });

  it('仅有 Skill 时只保留 Skill 行和换行提示', () => {
    expect(
      buildDefaultPlaceholder({
        isEn: false,
        hasSkills: true,
        hasPrompts: false,
        hasResources: false,
      }),
    ).toBe(`输入 "/" 唤出 Skill
通过 Shift + Enter 进行换行输入`);
  });

  it('三种能力都没有时只保留换行提示', () => {
    expect(
      buildDefaultPlaceholder({
        isEn: false,
        hasSkills: false,
        hasPrompts: false,
        hasResources: false,
      }),
    ).toBe('通过 Shift + Enter 进行换行输入');
  });

  it('三种能力都有时拼接完整英文提示', () => {
    expect(
      buildDefaultPlaceholder({
        isEn: true,
        hasSkills: true,
        hasPrompts: true,
        hasResources: true,
      }),
    ).toBe(`Input "/" to trigger skill
Input "\\" to trigger prompt
Input "@" to trigger tool and MCP
Use Shift + Enter to enter a new line`);
  });

  it('英文环境下无能力时只保留换行提示', () => {
    expect(
      buildDefaultPlaceholder({
        isEn: true,
        hasSkills: false,
        hasPrompts: false,
        hasResources: false,
      }),
    ).toBe('Use Shift + Enter to enter a new line');
  });
});
