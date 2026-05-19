/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 */

import { isRef, unref } from 'vue';

/** 请求头键值对 */
export type RequestHeaders = Record<string, string>;

/** 请求体附加数据键值对 */
export type RequestData = Record<string, unknown>;

/**
 * 支持延迟求值的请求配置值：
 * - 普通对象
 * - 零参函数（可返回对象、ref、computed）
 * - Ref / ComputedRef / MaybeRef
 */
export type MaybeRequestValue<T> = T | (() => MaybeRequestValue<T>);

function isVueRef(value: unknown): value is { value: unknown } {
  return isRef(value);
}

/**
 * 解析请求配置值，在每次请求前调用以读取最新值。
 * 递归展开函数、ref、computed，直到得到最终对象或原始值。
 */
export function resolveRequestValue<T>(value: MaybeRequestValue<T> | undefined): T | undefined {
  if (value === undefined || value === null) {
    return undefined;
  }

  let current: unknown = value;
  const maxDepth = 32;
  let depth = 0;

  while (depth < maxDepth) {
    depth += 1;

    if (typeof current === 'function') {
      current = (current as () => unknown)();
      continue;
    }

    if (isVueRef(current)) {
      current = unref(current);
      continue;
    }

    break;
  }

  if (depth >= maxDepth) {
    console.warn('[chat-helper] resolveRequestValue: exceeded max unwrap depth');
  }

  return current as T | undefined;
}
