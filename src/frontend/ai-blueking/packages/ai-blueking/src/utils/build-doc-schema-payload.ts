/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 */

import type { TagSchema } from '@blueking/chat-x';

const hasTag = (doc: TagSchema): boolean => doc.some(line => line.some(node => node.type === 'tag'));

/**
 * 构造发给后端的 property.docSchema：原样透传编辑器文档，无标签时返回 undefined（不发）。
 *
 * 上传文件的 artifact 标签（`file` → `artifact`、接口 `name` → `label`、`path` → `value`）
 * 由 chat-x 在 onSendMessage 前注入：只有它同时持有上传响应原文与当前附件列表，
 * 能保证注入点唯一、与文档里已有标签去重，且编辑回填不会重复追加。
 */
export const buildDocSchemaPayload = (docSchema: TagSchema | undefined): TagSchema | undefined => {
  const lines = (docSchema ?? []).filter(line => line.length > 0);
  return hasTag(lines) ? lines : undefined;
};
