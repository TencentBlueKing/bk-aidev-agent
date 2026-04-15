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
/// <reference types="markdown-it" />

// 类型声明文件：将本地的 markdown-it/index.mjs 模块映射到 @types/markdown-it 的类型定义
// 这个文件为 .mjs 模块提供 TypeScript 类型支持

import type MarkdownItConstructor from 'markdown-it';

declare const MarkdownIt: typeof MarkdownItConstructor;

export default MarkdownIt;
export type { MarkdownItConstructor };
// 主包入口无这些类型的命名导出（CommonJS 为 export =，ESM 的 index 也未 re-export），
// 与官方类型定义中 lib 子模块的 default class 对齐。
export type { Options, PluginSimple, PluginWithOptions, PluginWithParams, PresetName } from 'markdown-it';
export type { default as Renderer } from 'markdown-it/lib/renderer.mjs';
export type { default as StateBlock } from 'markdown-it/lib/rules_block/state_block.mjs';
export type { default as StateInline } from 'markdown-it/lib/rules_inline/state_inline.mjs';
export type { default as Token } from 'markdown-it/lib/token.mjs';
