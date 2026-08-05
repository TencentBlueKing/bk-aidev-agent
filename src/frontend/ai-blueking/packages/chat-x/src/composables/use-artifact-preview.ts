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

import { type ComputedRef, type Ref, computed, inject, provide, shallowRef } from 'vue';

import type { AIFileInfo, ArtifactUrlResult, OnArtifactClick } from '../ag-ui/types/file';

/** 文件产物预览 Provider/Consumer 通信 token */
export const ARTIFACT_PREVIEW_TOKEN = Symbol('ARTIFACT_PREVIEW_TOKEN');

/** 文件产物侧栏 Tab 的保留唯一标识（固定 Tab，不可关闭） */
export const FILE_ARTIFACT_TAB_NAME = 'file-artifact';

/** 临时链接缓存有效期（短于后端 token 常见 10 分钟时效） */
export const ARTIFACT_URL_CACHE_TTL_MS = 8 * 60 * 1000;

export type OpenArtifactPreviewPayload = {
  /** 被点击的文件 */
  file: AIFileInfo;
};

/** resolveArtifactUrls 可选参数 */
export type ResolveArtifactUrlsOptions = {
  /** 为 true 时跳过 TTL 缓存，强制重新取链（如预览重试） */
  force?: boolean;
};

/**
 * 会话级文件产物：以 outputId 为会话内唯一键（同 outputId 视为同一文件）。
 * 拍平去重后即为 AIFileInfo，此处用别名标明语义。
 */
export type SessionArtifact = AIFileInfo;

type ArtifactPreviewContext = {
  /** 当前命中的文件 outputId */
  activeArtifactId: Ref<string>;
  /** 是否具备异步取链能力（有 onArtifactClick 时下载按钮可见） */
  canResolveArtifactUrl: ComputedRef<boolean>;
  /** 由文件卡片触发：命中文件并弹出/切换到文件产物侧栏 */
  openPreview: (payload: OpenArtifactPreviewPayload) => void;
  /** 解析 download_url / preview_url：TTL 内复用缓存；force 时强制刷新；并发去重 */
  resolveArtifactUrls: (file: AIFileInfo, options?: ResolveArtifactUrlsOptions) => Promise<ArtifactUrlResult>;
  /** 直接设置命中文件 outputId（侧栏列表内切换用） */
  setActiveArtifactId: (id: string) => void;
};

type ArtifactUrlCacheEntry = {
  expiresAt: number;
  urls: ArtifactUrlResult;
};

/** 通过临时 <a> 触发浏览器下载 */
export const triggerArtifactDownload = (url: string, fileName: string) => {
  const link = document.createElement('a');
  link.href = url;
  link.download = fileName;
  link.target = '_blank';
  link.rel = 'noopener';
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
};

/**
 * 文件产物预览 Provider（在 ChatContainer 内使用）。
 * 维护「命中文件」状态，并封装 onArtifactClick 取链（TTL 缓存 + 并发去重）；
 * 打开侧栏 Tab 的副作用由外部 onOpen 注入。
 */
export const useArtifactPreviewProvider = (options: {
  /** 读取业务侧异步取链回调（用 getter 保持对 props 变更敏感） */
  getOnArtifactClick?: () => OnArtifactClick | undefined;
  /** 命中文件后触发：由容器负责 addCustomTab + 展开侧栏 + 选中 Tab */
  onOpen: (outputId: string) => void;
}) => {
  const activeArtifactId = shallowRef('');
  // 成功结果按 outputId 缓存，带过期时间
  const urlCache = new Map<string, ArtifactUrlCacheEntry>();
  // 进行中的请求，避免同文件并发重复打接口
  const inflight = new Map<string, Promise<ArtifactUrlResult>>();

  const canResolveArtifactUrl = computed(() => !!options.getOnArtifactClick?.());

  const setActiveArtifactId = (id: string) => {
    activeArtifactId.value = id;
  };

  const openPreview = (payload: OpenArtifactPreviewPayload) => {
    const id = payload.file.outputId;
    activeArtifactId.value = id;
    options.onOpen(id);
  };

  const resolveArtifactUrls = async (
    file: AIFileInfo,
    resolveOptions?: ResolveArtifactUrlsOptions,
  ): Promise<ArtifactUrlResult> => {
    const key = file.outputId;

    if (resolveOptions?.force) {
      urlCache.delete(key);
    } else {
      const cached = urlCache.get(key);
      if (cached && cached.expiresAt > Date.now()) {
        return cached.urls;
      }
    }

    const pending = inflight.get(key);
    if (pending) {
      return pending;
    }

    const onArtifactClick = options.getOnArtifactClick?.();
    if (!onArtifactClick) {
      return {};
    }

    const request = onArtifactClick(file)
      .then(result => {
        const urls = result ?? {};
        urlCache.set(key, {
          expiresAt: Date.now() + ARTIFACT_URL_CACHE_TTL_MS,
          urls,
        });
        inflight.delete(key);
        return urls;
      })
      .catch(error => {
        inflight.delete(key);
        throw error;
      });

    inflight.set(key, request);
    return request;
  };

  provide<ArtifactPreviewContext>(ARTIFACT_PREVIEW_TOKEN, {
    activeArtifactId,
    canResolveArtifactUrl,
    openPreview,
    resolveArtifactUrls,
    setActiveArtifactId,
  });

  return {
    activeArtifactId,
    canResolveArtifactUrl,
    openPreview,
    resolveArtifactUrls,
    setActiveArtifactId,
  };
};

/** 文件产物预览 Consumer（在深层文件卡片中使用），无 Provider 时返回 undefined 兜底 */
export const useArtifactPreviewConsumer = () =>
  inject<ArtifactPreviewContext | undefined>(ARTIFACT_PREVIEW_TOKEN, undefined);
