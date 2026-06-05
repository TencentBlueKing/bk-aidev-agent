/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 */

import { resolveRequestValue } from '@blueking/chat-helper';
import { toValue, type MaybeRefOrGetter } from 'vue';

import type { IRequestOptions } from '../types';
import type { IUseChatHelperOptions, MaybeRequestValue, RequestData, RequestHeaders } from '@blueking/chat-helper';

const CONTEXT_META_KEYS = new Set(['context_type', '__label', '__key', '__value']);

/**
 * 将外层 requestOptions（可为 ref/computed/函数）转为 chat-helper 的 requestData。
 * 使用稳定 getter，每次请求时读取最新的 headers/data。
 */
export function buildRequestDataFromOptions(
  urlPrefix: string,
  requestOptions?: MaybeRefOrGetter<IRequestOptions | undefined>,
): IUseChatHelperOptions['requestData'] {
  const resolveHeaders = (): RequestHeaders | undefined => {
    const opts = toValue(requestOptions);
    return resolveRequestValue(opts?.headers);
  };

  const resolveData = (): RequestData | undefined => {
    const opts = toValue(requestOptions);
    return resolveRequestValue(opts?.data);
  };

  return {
    urlPrefix,
    headers: resolveHeaders as MaybeRequestValue<RequestHeaders>,
    data: resolveData as MaybeRequestValue<RequestData>,
  };
}

/**
 * 将 requestOptions.context 转为结构化数组格式（与 shortcuts property.extra.context 一致）
 *
 * 支持两种输入格式：
 * - Record<string, unknown>: 简单 KV，每个 entry 转为结构化条目
 * - Array<Record<string, unknown>>: 数组，有 __key 的条目直接透传，简单 KV 自动转换
 *
 * 转换规则：{ key: value } → { key: value, context_type: 'input', __label: key, __key: key, __value: value }
 */
export function resolveContextEntries(
  context: RequestData | Array<Record<string, unknown>> | undefined,
): Array<Record<string, unknown>> {
  if (!context) return [];

  // Record<string, unknown> 格式
  if (!Array.isArray(context)) {
    return Object.entries(context).map(([key, value]) => ({
      [key]: value,
      context_type: 'input',
      __label: key,
      __key: key,
      __value: value,
    }));
  }

  // Array<Record<string, unknown>> 格式
  return context.map(item => {
    // 已有 __key 的结构化条目 → 直接透传
    if (item.__key) return item;

    // 简单 KV → 取第一个非元数据 key 做转换
    const entries = Object.entries(item).filter(([k]) => !CONTEXT_META_KEYS.has(k));
    if (entries.length === 0) return item;

    const [key, value] = entries[0];
    return {
      ...item,
      [key]: value,
      context_type: item.context_type ?? 'input',
      __label: item.__label ?? key,
      __key: item.__key ?? key,
      __value: item.__value ?? value,
    };
  });
}

/**
 * 解析 requestOptions.context（支持 ref/computed/函数），返回结构化数组
 */
export function resolveRequestOptionsContext(
  requestOptions?: MaybeRefOrGetter<IRequestOptions | undefined>,
): Array<Record<string, unknown>> {
  const opts = toValue(requestOptions);
  const raw = resolveRequestValue(opts?.context);
  return resolveContextEntries(raw as RequestData | Array<Record<string, unknown>> | undefined);
}

/**
 * 将 requestOptions.context 合并到 message property 中
 *
 * 统一处理：从 getter 获取 requestOptions → 解析 context → 合并到 property
 * 消除了 doSendMessage 和 handleUserShortcutConfirm 中的重复逻辑
 *
 * @param property 原始消息 property（可能已有 shortcut context）
 * @param getRequestOptions 返回最新 requestOptions 的 getter
 * @returns 合并后的 property，无 context 时返回原 property
 */
export function applyRequestOptionsContext(
  property: Record<string, unknown> | undefined,
  getRequestOptions?: () => IRequestOptions | undefined,
): Record<string, unknown> | undefined {
  if (!getRequestOptions) return property;
  const opts = getRequestOptions();
  const contextRaw = opts?.context;
  if (!contextRaw) return property;
  const contextEntries = resolveContextEntries(contextRaw as RequestData | Array<Record<string, unknown>>);
  if (contextEntries.length === 0) return property;
  return mergePropertyContext(property, contextEntries);
}

/**
 * 将 requestOptions 的 context 合并到 message property 中
 *
 * 合并策略：
 * - requestOptions context 条目追加到 shortcut context 之后
 * - key 冲突时（以 __key 判断），requestOptions 的条目覆盖已有的
 */
export function mergePropertyContext(
  property: Record<string, unknown> | undefined,
  contextEntries: Array<Record<string, unknown>>,
): Record<string, unknown> {
  if (contextEntries.length === 0) return property ?? {};

  const existing = (property ?? {}) as Record<string, unknown>;
  const extra = (existing.extra ?? {}) as Record<string, unknown>;
  const existingContext = (extra.context ?? []) as Array<Record<string, unknown>>;

  // 收集 requestOptions 中的 keys，用于去重
  const requestKeys = new Set(contextEntries.map(e => e.__key).filter(Boolean));

  // 保留不冲突的 shortcut context 条目
  const filteredContext = existingContext.filter(e => {
    const key = e.__key;
    return !key || !requestKeys.has(key);
  });

  return {
    ...existing,
    extra: {
      ...extra,
      context: [...filteredContext, ...contextEntries],
    },
  };
}
