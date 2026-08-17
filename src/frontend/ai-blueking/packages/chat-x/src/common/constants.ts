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

import { t } from '../lang/lang';

import type { IToolBtn } from '../types';

/**
 * 全局 chat-x 组件 Z-Index
 */
export const CHAT_Z_INDEX = 9999;

/**
 * 编辑器组件 Z-Index
 */
export const EDITOR_Z_INDEX = CHAT_Z_INDEX + 1;

/**
 * 编辑器菜单 Z-Index
 */
export const EDITOR_MENU_Z_INDEX = EDITOR_Z_INDEX + 1;

/**
 * 快捷指令菜单 Z-Index
 */
export const SHORTCUT_MENU_Z_INDEX = EDITOR_MENU_Z_INDEX + 1;

/**
 * 划选弹窗 Z-Index
 */
export const SELECTION_Z_INDEX = SHORTCUT_MENU_Z_INDEX + 1;

/**
 * 消息工具
 */
export const CONST_MESSAGE_TOOLS = [
  {
    description: t('复制'),
    id: 'copy',
    name: t('复制'),
  },
  {
    description: t('引用'),
    id: 'cite',
    name: t('引用'),
  },
  {
    description: t('重新生成将清空下文内容'),
    id: 'rebuild',
    name: t('重新生成'),
  },
  {
    description: t('分享'),
    id: 'share',
    name: t('分享'),
  },
] as IToolBtn[];

export const CONST_USER_MESSAGE_TOOLS = [
  {
    description: t('复制'),
    id: 'copy',
    name: t('复制'),
  },
  {
    description: t('引用'),
    id: 'cite',
    name: t('引用'),
  },
  {
    description: t('编辑'),
    id: 'edit',
    name: t('编辑'),
  },
  {
    description: t('删除'),
    id: 'delete',
    name: t('删除'),
  },
] as IToolBtn[];

/**
 * 更新工具
 */
export const CONST_UPDATE_TOOLS = [
  {
    description: t('点赞'),
    id: 'like',
    name: t('点赞'),
  },
  {
    description: t('不满意'),
    id: 'unlike',
    name: t('不满意'),
  },
  {
    description: t('删除'),
    id: 'delete',
    name: t('删除'),
  },
] as IToolBtn[];

export const MAX_UPLOAD_FILES = 3; // 最大上传文件数量

export const MAX_UPLOAD_FILE_SIZE = 2.4 * 1024 * 1024; // 最大上传文件大小 2.5MB

/**
 * 默认上传文件类型：图片 + Markdown / Word 等常见文档
 * 遵循 `<input accept>` 规范，仅影响系统文件选择框过滤
 */
export const DEFAULT_UPLOAD_ACCEPT = [
  'image/*',
  '.md',
  '.markdown',
  '.doc',
  '.docx',
  '.txt',
  '.pdf',
  '.ppt',
  '.pptx',
  '.xls',
  '.xlsx',
  '.csv',
].join(',');

/**
 * 关键词高亮类名
 */
export const HIGHLIGHT_KEYWORD_CLASS_NAME = 'ai-is-keyword';

export enum RenderMode {
  Chat = 'chat',
  Share = 'share',
  Test = 'test',
}

export const LOADING_MESSAGE_ID = '__loading__';
