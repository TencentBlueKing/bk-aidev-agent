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

/** 对话上传允许的扩展名（含点），分类仅用于 tooltip 展示 */
export const ALLOWED_UPLOAD_EXTENSIONS = {
  image: ['.gif', '.jpeg', '.jpg', '.png', '.webp'],
  document: ['.doc', '.docx', '.ppt', '.pptx', '.xls', '.xlsx', '.pdf', '.epub', '.mobi', '.csv'],
  text: [
    '.txt',
    '.md',
    '.rst',
    '.log',
    '.json',
    '.xml',
    '.yaml',
    '.yml',
    '.toml',
    '.ini',
    '.conf',
    '.html',
    '.css',
    '.scss',
    '.sql',
  ],
  code: [
    '.py',
    '.js',
    '.jsx',
    '.ts',
    '.tsx',
    '.vue',
    '.java',
    '.go',
    '.c',
    '.cpp',
    '.h',
    '.hpp',
    '.cs',
    '.php',
    '.rb',
    '.rs',
    '.kt',
    '.swift',
    '.sh',
    '.bash',
  ],
} as const;

/** 系统文件选择框 / 校验共用的默认 accept */
export const DEFAULT_UPLOAD_ACCEPT = Object.values(ALLOWED_UPLOAD_EXTENSIONS).flat().join(',');
