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

/**
 * 文件分类：图标兜底与预览渲染策略的共同依据。
 * - code：可交给 highlight.js 渲染的源码 / 配置文件
 * - text：纯文本，直接按原文展示
 * - binary：无法在前端直接解析，统一交由后端 preview_url 预览
 */
export type AIFileKind = 'binary' | 'code' | 'html' | 'image' | 'markdown' | 'text';

/** 分类 → 扩展名清单；此处未登记的扩展名一律按 binary 兜底 */
const FILE_KIND_GROUPS: Record<Exclude<AIFileKind, 'binary'>, string[]> = {
  code: [
    'bash',
    'c',
    'cfg',
    'cjs',
    'conf',
    'cpp',
    'cs',
    'css',
    'dart',
    'dockerfile',
    'dockerignore',
    'editorconfig',
    'env',
    'gitignore',
    'go',
    'h',
    'hpp',
    'ini',
    'java',
    'js',
    'json',
    'jsonc',
    'jsx',
    'kt',
    'less',
    'lua',
    'makefile',
    'mjs',
    'php',
    'ps1',
    'py',
    'r',
    'rb',
    'rs',
    'scala',
    'scss',
    'sh',
    'sql',
    'swift',
    'tex',
    'toml',
    'ts',
    'tsx',
    'vue',
    'xml',
    'yaml',
    'yml',
    'zsh',
  ],
  html: ['htm', 'html'],
  image: ['jpeg', 'jpg', 'png', 'svg'],
  markdown: ['markdown', 'md'],
  text: ['rst', 'txt'],
};

const FILE_KIND_MAP = new Map<string, AIFileKind>(
  Object.entries(FILE_KIND_GROUPS).flatMap(([kind, extensions]) =>
    extensions.map(extension => [extension, kind as AIFileKind] as const),
  ),
);

/**
 * 归一化文件类型标识：优先取后台下发的 type，缺省时回退文件名。
 * 统一转小写并截取最后一段扩展名；无扩展名的文件（Dockerfile / Makefile）直接返回文件名本身。
 */
export const normalizeFileExtension = (type?: string, name?: string): string => {
  const raw = (type || name || '').trim().toLowerCase();
  const lastDot = raw.lastIndexOf('.');
  return lastDot > -1 ? raw.slice(lastDot + 1) : raw;
};

/** 解析文件分类；未登记的扩展名按 binary 兜底 */
export const resolveFileKind = (type?: string, name?: string): AIFileKind =>
  FILE_KIND_MAP.get(normalizeFileExtension(type, name)) ?? 'binary';
