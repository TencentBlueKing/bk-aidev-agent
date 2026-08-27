/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 */
import type { IToolBtn } from '../types';

/**
 * 按 id 合并工具列表：以内置列表为基底，同 id 覆盖（字段级合并）、新 id 追加，其余保留；
 * 最后过滤掉标记 hidden 的项，实现「隐藏内置按钮」（如 { id: 'share', hidden: true }）。
 */
export const mergeToolsById = (base: IToolBtn[], extra?: IToolBtn[]): IToolBtn[] => {
  if (!extra?.length) return base;
  const merged = base.map(tool => {
    const override = extra.find(item => item.id === tool.id);
    return override ? { ...tool, ...override } : tool;
  });
  const appended = extra.filter(item => !base.some(tool => tool.id === item.id));
  return [...merged, ...appended].filter(tool => !tool.hidden);
};
