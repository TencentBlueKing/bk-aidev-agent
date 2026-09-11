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
 * 附件与 artifact 标签的互转。
 *
 * 上传附件既以文件卡片展示，也要以标签形式进入文档（业务方据此把已选资源发给后端）。
 * 注入与剥离必须共用同一套 value 口径，否则发送时补上的标签在回显时剥不掉，就会重复展示。
 */
import type { AIFileInfo } from '../ag-ui/types/file';
import type { TagSchema } from '../types/input';

type TagLine = TagSchema[number];
type TagNode = TagLine[number];
type ArtifactTagNode = Extract<TagNode, { type: 'tag' }>;

/** 附件的最小身份契约，`Partial<UploadFile>` 与 `BinaryInputContent` 均可直接传入 */
export type ArtifactIdentityLike = {
  id?: string;
  outputId?: string;
};

const isArtifactTag = (node: TagNode): node is ArtifactTagNode =>
  node.type === 'tag' && node.data.type === 'artifact';

/**
 * 文件转 artifact 标签节点：`label` 取展示名（上传接口 `name`），
 * `value` 取文件身份（上传接口 `path`，即产物 `outputId`）。
 */
export const toArtifactTagNode = (file: AIFileInfo): ArtifactTagNode =>
  ({
    type: 'tag',
    data: {
      type: 'artifact',
      label: file.name,
      value: file.outputId,
      icon: '',
      description: '',
    },
  }) as ArtifactTagNode;

/**
 * 发送前把待发送附件补成一行 artifact 标签。
 *
 * 编辑回填的文档可能已含同一文件的标签（上次发送时注入的），按 value 去重避免重复追加。
 */
export const appendArtifactTags = (doc: TagSchema, files: readonly AIFileInfo[]): TagSchema => {
  const existing = new Set(
    doc
      .flat()
      .filter(isArtifactTag)
      .map(node => node.data.value),
  );
  const tags = files.filter(file => file.outputId && !existing.has(file.outputId)).map(toArtifactTagNode);
  return tags.length ? [...doc, tags] : doc;
};

/**
 * 消息回显与编辑回填前，去掉已由附件卡片承载的 artifact 标签，避免同一文件重复展示。
 *
 * 历史消息经 chat-helper 转换后只剩 `id`，因此 `id` 与 `outputId` 都参与匹配。
 */
export const omitArtifactTags = (doc: TagSchema, files: readonly ArtifactIdentityLike[]): TagSchema => {
  const identifiers = new Set(
    files.flatMap(file => [file.outputId, file.id]).filter((value): value is string => !!value),
  );
  if (!identifiers.size) {
    return doc;
  }
  const lines: TagLine[] = [];
  for (const line of doc) {
    const kept = line.filter(node => !(isArtifactTag(node) && identifiers.has(node.data.value)));
    // 整行只有被剥掉的标签时不留空行，否则回显会多出一个换行
    if (kept.length === 0 && line.length > 0) {
      continue;
    }
    lines.push(kept);
  }
  return lines;
};
